#!/usr/bin/env python3
"""Bulk insert samples from recentsamples.csv into LabTrack via REST API.

Reads the CSV, groups rows by Lot number, and creates lots (standard or
parent with sublots) plus their test results through the LabTrack API.

Usage:
    python scripts/bulk_insert_samples.py              # live run
    python scripts/bulk_insert_samples.py --dry-run    # preview only
"""

import argparse
import csv
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8009/api/v1"
CSV_PATH = Path(__file__).resolve().parent.parent.parent / "recentsamples.csv"

AUTH_CREDENTIALS = {
    "username": "admin",
    "password": "admin123",
}

# CSV column -> (test_type name, unit)
TEST_COLUMN_MAP: dict[str, tuple[str, str]] = {
    "Total Plate Count": ("Total Plate Count", "CFU/g"),
    "Yeast/Mold": ("Yeast & Mold", "CFU/g"),
    "E. Coli": ("Escherichia coli", "Present/Absent"),
    "Salmonella": ("Salmonella spp.", "Present/Absent"),
    "Gluten": ("Gluten", "ppm"),
    "Arsenic": ("Arsenic", "ppm"),
    "Cadmium": ("Cadmium", "ppm"),
    "Lead": ("Lead", "ppm"),
    "Mercury": ("Mercury", "ppm"),
}

# Columns to ignore when building test results
IGNORED_COLUMNS = {"Staphylococcus aureus", "Total Coliform Count"}

# Brand aliases: CSV brand name -> DB brand name
BRAND_ALIASES: dict[str, str] = {
    "Myos": "MyosMD",
    "Strive": "Strive Nutrition",
}

# Product name aliases: (CSV brand, CSV product) -> DB product_name
PRODUCT_NAME_ALIASES: dict[tuple[str, str], str] = {
    ("Strive", "Freemilk Premix"): "Freemilk Premix",
}


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date(raw: str) -> str | None:
    """Parse mixed date formats into ISO 'YYYY-MM-DD' strings.

    Handles:
        - "2026-01-30 00:00:00" (datetime with time component)
        - "2/3/26"              (M/D/YY, two-digit year)
        - Empty/whitespace      (returns None)
    """
    raw = raw.strip()
    if not raw:
        return None

    # Try ISO-like datetime first: "2026-01-30 00:00:00"
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try short date: "2/3/26"
    try:
        dt = datetime.strptime(raw, "%m/%d/%y")
        # Python interprets 2-digit years 00-68 as 2000-2068, 69-99 as 1969-1999.
        # All our data is 2020s so this works correctly.
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    print(f"  WARNING: Could not parse date '{raw}', skipping")
    return None


# ---------------------------------------------------------------------------
# CSV loading and data fixes
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> list[dict[str, str]]:
    """Read the CSV and apply data fixes before returning rows."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cleaned: list[dict[str, str]] = []
    for row in rows:
        lot_value = row.get("Lot", "").strip()

        # Skip rows with empty Lot column
        if not lot_value:
            brand = row.get("Brand", "")
            product = row.get("Product", "")
            print(f"  Skipping row with empty Lot: {brand} {product}")
            continue

        # Fix duplicate RefID: row where RefID=260300005 AND Lot=26031
        ref_id = row.get("RefID", "").strip()
        if ref_id == "260300005" and lot_value == "26031":
            row["RefID"] = "260330005"
            print("  Applied fix: RefID 260300005 in Lot 26031 -> 260330005")

        # Normalize "20 serving" -> "20 servings"
        size = row.get("Size", "").strip()
        if size == "20 serving":
            row["Size"] = "20 servings"

        cleaned.append(row)

    return cleaned


def group_by_lot(rows: list[dict[str, str]]) -> OrderedDict[str, list[dict[str, str]]]:
    """Group rows by the Lot column, preserving insertion order."""
    groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in rows:
        lot = row["Lot"].strip()
        groups.setdefault(lot, []).append(row)
    return groups


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

class LabTrackClient:
    """Thin wrapper around LabTrack REST API calls."""

    def __init__(self, base_url: str, dry_run: bool = False):
        self.base_url = base_url
        self.dry_run = dry_run
        self.session = requests.Session()
        self.token: str | None = None

    def login(self) -> None:
        """Authenticate and store the bearer token."""
        if self.dry_run:
            print("[DRY RUN] Would authenticate as admin")
            return

        resp = self.session.post(
            f"{self.base_url}/auth/login",
            data=AUTH_CREDENTIALS,
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        self.session.headers["Authorization"] = f"Bearer {self.token}"
        print("Authenticated successfully.\n")

    def fetch_products(self) -> dict[tuple[str, str, str | None], int]:
        """Fetch all products and return a lookup dict keyed by (brand, product_name, flavor)."""
        if self.dry_run:
            print("[DRY RUN] Would fetch product catalog")
            return {}

        resp = self.session.get(
            f"{self.base_url}/products",
            params={"page_size": 500},
        )
        resp.raise_for_status()
        data = resp.json()

        lookup: dict[tuple[str, str, str | None], int] = {}
        for p in data["items"]:
            key = (p["brand"], p["product_name"], p.get("flavor"))
            lookup[key] = p["id"]

        print(f"Loaded {len(lookup)} products from catalog.\n")
        return lookup

    def _post(self, path: str, json_body: dict[str, Any]) -> dict[str, Any] | None:
        """POST helper with error handling. Returns response JSON or None on failure."""
        if self.dry_run:
            return None

        resp = self.session.post(f"{self.base_url}{path}", json=json_body)
        if not resp.ok:
            detail = ""
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            print(f"  ERROR {resp.status_code} on POST {path}: {detail}")
            return None
        return resp.json()

    def create_lot(self, payload: dict[str, Any]) -> int | None:
        """Create a lot and return its ID, or None on failure."""
        result = self._post("/lots", payload)
        if result:
            return result["id"]
        return None

    def create_sublots_bulk(self, lot_id: int, sublots: list[dict[str, Any]]) -> int:
        """Create sublots in bulk. Returns count created."""
        result = self._post(f"/lots/{lot_id}/sublots/bulk", {"sublots": sublots})
        if result:
            return len(result)
        return 0

    def create_test_results_bulk(
        self, lot_id: int, results: list[dict[str, Any]]
    ) -> int:
        """Create test results in bulk. Returns count created."""
        if not results:
            return 0
        payload = {"lot_id": lot_id, "results": results}
        result = self._post("/test-results/bulk", payload)
        if result:
            return len(result)
        return 0

    def fetch_product_specs(self, product_id: int) -> dict[str, dict[str, str | None]]:
        """Fetch test specifications for a product. Returns {test_name: {specification, method, unit}}.

        Results are cached to avoid re-fetching for the same product.
        """
        if not hasattr(self, "_specs_cache"):
            self._specs_cache: dict[int, dict[str, dict[str, str | None]]] = {}

        if product_id in self._specs_cache:
            return self._specs_cache[product_id]

        if self.dry_run:
            return {}

        resp = self.session.get(
            f"{self.base_url}/products/{product_id}/test-specifications",
        )
        if not resp.ok:
            print(f"  WARNING: Could not fetch specs for product {product_id}")
            return {}

        specs: dict[str, dict[str, str | None]] = {}
        for s in resp.json():
            specs[s["test_name"]] = {
                "specification": s.get("specification"),
                "method": s.get("test_method"),
                "unit": s.get("test_unit"),
            }

        self._specs_cache[product_id] = specs
        return specs


# ---------------------------------------------------------------------------
# Test result extraction
# ---------------------------------------------------------------------------

def build_test_results(
    row: dict[str, str],
    product_specs: dict[str, dict[str, str | None]],
) -> list[dict[str, Any]]:
    """Extract non-empty test results from a CSV row.

    Returns a list of dicts matching the TestResultBase schema
    (test_type, result_value, unit, specification, method).
    """
    results: list[dict[str, Any]] = []
    for csv_col, (test_type, unit) in TEST_COLUMN_MAP.items():
        raw_value = row.get(csv_col, "").strip()
        if not raw_value:
            continue
        spec_info = product_specs.get(test_type, {})
        result: dict[str, Any] = {
            "test_type": test_type,
            "result_value": raw_value,
            "unit": spec_info.get("unit") or unit,
        }
        if spec_info.get("specification"):
            result["specification"] = spec_info["specification"]
        if spec_info.get("method"):
            result["method"] = spec_info["method"]
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Product lookup helper
# ---------------------------------------------------------------------------

def find_product_id(
    row: dict[str, str],
    product_lookup: dict[tuple[str, str, str | None], int],
) -> int | None:
    """Resolve a CSV row to a product_id using the product lookup dict."""
    brand = row.get("Brand", "").strip()
    product_name = row.get("Product", "").strip()
    flavor = row.get("Flavor", "").strip() or None

    # Apply brand alias if needed
    db_brand = BRAND_ALIASES.get(brand, brand)

    # Apply product name alias if needed
    db_product_name = PRODUCT_NAME_ALIASES.get((brand, product_name), product_name)

    key = (db_brand, db_product_name, flavor)
    product_id = product_lookup.get(key)

    if product_id is None:
        # Try without flavor as a fallback
        key_no_flavor = (db_brand, db_product_name, None)
        product_id = product_lookup.get(key_no_flavor)

    if product_id is None:
        print(f"  WARNING: No product found for ({db_brand}, {db_product_name}, {flavor})")

    return product_id


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_lot_group(
    lot_number: str,
    rows: list[dict[str, str]],
    client: LabTrackClient,
    product_lookup: dict[tuple[str, str, str | None], int],
    counters: dict[str, int],
) -> None:
    """Process a single lot group (standard or parent lot with sublots)."""
    is_parent = len(rows) > 1
    first_row = rows[0]

    # Resolve product
    product_id = find_product_id(first_row, product_lookup)
    if product_id is None and not client.dry_run:
        print(f"  Skipping lot {lot_number}: product not found in catalog")
        counters["skipped"] += 1
        return

    if is_parent:
        _process_parent_lot(lot_number, rows, client, product_id, counters)
    else:
        _process_standard_lot(lot_number, first_row, client, product_id, counters)


def _process_parent_lot(
    lot_number: str,
    rows: list[dict[str, str]],
    client: LabTrackClient,
    product_id: int | None,
    counters: dict[str, int],
) -> None:
    """Create a parent lot with sublots and test results."""
    # Determine earliest mfg_date and the shared exp_date
    mfg_dates = [parse_date(r.get("Mfg Date", "")) for r in rows]
    valid_mfg = [d for d in mfg_dates if d is not None]
    earliest_mfg = min(valid_mfg) if valid_mfg else None
    exp_date = parse_date(rows[0].get("Exp Date", ""))

    sublot_count = len(rows)
    print(f"Creating parent lot {lot_number} with {sublot_count} sublots...")

    # Step 1: Create the parent lot (no reference_number for parent lots)
    lot_payload: dict[str, Any] = {
        "lot_number": lot_number,
        "lot_type": "parent_lot",
        "generate_coa": True,
        "products": [{"product_id": product_id}] if product_id else [],
    }
    if earliest_mfg:
        lot_payload["mfg_date"] = earliest_mfg
    if exp_date:
        lot_payload["exp_date"] = exp_date

    if client.dry_run:
        print(f"  [DRY RUN] POST /lots -> parent lot {lot_number}")
        print(f"    mfg_date={earliest_mfg}, exp_date={exp_date}, product_id={product_id}")
        counters["lots"] += 1
    else:
        lot_id = client.create_lot(lot_payload)
        if lot_id is None:
            counters["skipped"] += 1
            return
        counters["lots"] += 1

    # Step 2: Create sublots
    sublots_payload: list[dict[str, Any]] = []
    for row in rows:
        ref_id = row.get("RefID", "").strip()
        mfg = parse_date(row.get("Mfg Date", ""))
        sublot: dict[str, Any] = {"sublot_number": ref_id}
        if mfg:
            sublot["production_date"] = mfg
        sublots_payload.append(sublot)

    if client.dry_run:
        print(f"  [DRY RUN] POST /lots/{{id}}/sublots/bulk -> {len(sublots_payload)} sublots")
        for s in sublots_payload:
            print(f"    sublot_number={s['sublot_number']}, production_date={s.get('production_date')}")
        counters["sublots"] += len(sublots_payload)
    else:
        created = client.create_sublots_bulk(lot_id, sublots_payload)
        counters["sublots"] += created
        if created:
            print(f"  Created {created} sublots")

    # Step 3: Create test results (use first row's values - identical across group)
    product_specs = client.fetch_product_specs(product_id) if product_id else {}
    test_results = build_test_results(rows[0], product_specs)
    if client.dry_run:
        if test_results:
            print(f"  [DRY RUN] POST /test-results/bulk -> {len(test_results)} tests")
            for t in test_results:
                print(f"    {t['test_type']}: {t['result_value']} {t['unit']}")
        else:
            print("  [DRY RUN] No test results to insert")
        counters["test_results"] += len(test_results)
    else:
        created = client.create_test_results_bulk(lot_id, test_results)
        counters["test_results"] += created
        if created:
            print(f"  Created {created} test results")


def _process_standard_lot(
    lot_number: str,
    row: dict[str, str],
    client: LabTrackClient,
    product_id: int | None,
    counters: dict[str, int],
) -> None:
    """Create a standard lot with test results."""
    ref_id = row.get("RefID", "").strip()
    mfg_date = parse_date(row.get("Mfg Date", ""))
    exp_date = parse_date(row.get("Exp Date", ""))

    print(f"Creating standard lot {lot_number} (ref: {ref_id})...")

    # Step 1: Create the lot
    lot_payload: dict[str, Any] = {
        "lot_number": lot_number,
        "lot_type": "standard",
        "reference_number": ref_id,
        "generate_coa": True,
        "products": [{"product_id": product_id}] if product_id else [],
    }
    if mfg_date:
        lot_payload["mfg_date"] = mfg_date
    if exp_date:
        lot_payload["exp_date"] = exp_date

    if client.dry_run:
        print(f"  [DRY RUN] POST /lots -> standard lot {lot_number}, ref={ref_id}")
        print(f"    mfg_date={mfg_date}, exp_date={exp_date}, product_id={product_id}")
        counters["lots"] += 1
    else:
        lot_id = client.create_lot(lot_payload)
        if lot_id is None:
            counters["skipped"] += 1
            return
        counters["lots"] += 1

    # Step 2: Create test results
    product_specs = client.fetch_product_specs(product_id) if product_id else {}
    test_results = build_test_results(row, product_specs)
    if client.dry_run:
        if test_results:
            print(f"  [DRY RUN] POST /test-results/bulk -> {len(test_results)} tests")
            for t in test_results:
                print(f"    {t['test_type']}: {t['result_value']} {t['unit']}")
        else:
            print("  [DRY RUN] No test results to insert")
        counters["test_results"] += len(test_results)
    else:
        created = client.create_test_results_bulk(lot_id, test_results)
        counters["test_results"] += created
        if created:
            print(f"  Created {created} test results")


def preflight_check(
    rows: list[dict[str, str]],
    product_lookup: dict[tuple[str, str, str | None], int],
) -> bool:
    """Verify all required products exist before creating any lots.

    Returns True if all products found, False if any are missing.
    """
    missing: set[tuple[str, str, str | None]] = set()
    for row in rows:
        brand = row.get("Brand", "").strip()
        product_name = row.get("Product", "").strip()
        flavor = row.get("Flavor", "").strip() or None

        db_brand = BRAND_ALIASES.get(brand, brand)
        db_product_name = PRODUCT_NAME_ALIASES.get((brand, product_name), product_name)

        key = (db_brand, db_product_name, flavor)
        if key not in product_lookup:
            key_no_flavor = (db_brand, db_product_name, None)
            if key_no_flavor not in product_lookup:
                missing.add(key)

    if missing:
        print("PREFLIGHT FAILED: The following products are missing from the catalog:")
        for brand, product, flavor in sorted(missing):
            print(f"  - {brand} / {product} / {flavor}")
        print("\nCreate these products first, then re-run.")
        return False

    print("Preflight check passed: all products found in catalog.\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk insert samples from recentsamples.csv into LabTrack"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without making API calls",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print(f"CSV path: {CSV_PATH}")
    print(f"API base: {base_url}")
    print(f"Dry run:  {args.dry_run}\n")

    # Load and fix CSV data
    print("Loading CSV...")
    rows = load_csv(CSV_PATH)
    print(f"Loaded {len(rows)} rows (after filtering).\n")

    # Group by lot
    lot_groups = group_by_lot(rows)
    parent_count = sum(1 for g in lot_groups.values() if len(g) > 1)
    standard_count = sum(1 for g in lot_groups.values() if len(g) == 1)
    print(f"Found {len(lot_groups)} unique lots: {parent_count} parent lots, {standard_count} standard lots.\n")

    # Initialize API client
    client = LabTrackClient(base_url, dry_run=args.dry_run)
    client.login()

    # Fetch product catalog
    product_lookup = client.fetch_products()

    # Preflight: verify all products exist
    if not args.dry_run and not preflight_check(rows, product_lookup):
        sys.exit(1)

    # Process each lot group
    counters = {"lots": 0, "sublots": 0, "test_results": 0, "skipped": 0}

    for lot_number, group_rows in lot_groups.items():
        try:
            process_lot_group(lot_number, group_rows, client, product_lookup, counters)
        except Exception as e:
            print(f"  ERROR processing lot {lot_number}: {e}")
            counters["skipped"] += 1

    # Print summary
    mode = "DRY RUN " if args.dry_run else ""
    print(f"\n{'='*50}")
    print(f"{mode}Summary:")
    print(f"  Lots created:         {counters['lots']}")
    print(f"  Sublots created:      {counters['sublots']}")
    print(f"  Test results created: {counters['test_results']}")
    print(f"  Skipped/errors:       {counters['skipped']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
