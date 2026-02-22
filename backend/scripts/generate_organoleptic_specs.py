"""Generate organoleptic (Appearance + Taste) specs for product test mapping CSV.

Reads the product_test_mapping.csv, determines appropriate Appearance and Taste
specifications based on each product's flavor/type, appends those tests and specs
to the existing rows, and writes the updated CSV back.

Usage:
    python -m scripts.generate_organoleptic_specs

The flavor-to-appearance mapping is exposed via ``get_appearance_spec()`` so other
modules can reuse it without duplicating the logic.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CSV_PATH = Path(__file__).resolve().parent.parent / "product_test_mapping.csv"

# Ordered list of (compiled regex, appearance description).
# Earlier entries take priority, so more specific patterns come first.
_APPEARANCE_RULES: list[tuple[re.Pattern[str], str]] = [
    # --- Exact / special-case product names (checked against product+flavor) ---
    (re.compile(r"\bCookies\s*&\s*Cream\b", re.I), "Fine cream powder with dark specks"),
    (re.compile(r"\bRocket\s*Pop\b", re.I), "Fine multi-colored powder"),
    (re.compile(r"\bRainbow\s*Sherbert\b", re.I), "Fine multi-colored powder"),
    (re.compile(r"\bFruity\s*Cereal\b", re.I), "Fine multi-colored powder"),

    # --- Blue family ---
    (re.compile(r"\bBlue\s*Raspberry\b", re.I), "Fine blue powder"),
    (re.compile(r"\bBlue\s*Slush\b", re.I), "Fine blue powder"),

    # --- Red family (Cherry before Lime so "Cherry Lime" maps to red) ---
    (re.compile(r"\bFruit\s*Punch\b", re.I), "Fine red powder"),
    (re.compile(r"\bCherry\b", re.I), "Fine red powder"),

    # --- Green family ---
    (re.compile(r"\bLimeade\b", re.I), "Fine light green powder"),
    (re.compile(r"\bLime\b", re.I), "Fine light green powder"),

    # --- Pink family (must come after red so "Strawberry" doesn't steal "Cherry Lime") ---
    (re.compile(r"\bStrawberry\b", re.I), "Fine pink to light red powder"),
    (re.compile(r"\bBerry\b", re.I), "Fine pink to light red powder"),
    (re.compile(r"\bBlueberry\b", re.I), "Fine pink to light red powder"),
    (re.compile(r"\bWatermelon\b", re.I), "Fine pink to light red powder"),
    (re.compile(r"\bPink\s*Lemonade\b", re.I), "Fine pink to light red powder"),

    # --- Brown family ---
    (re.compile(r"\bChocolate\b", re.I), "Fine brown powder"),
    (re.compile(r"\bMocha\b", re.I), "Fine brown powder"),
    (re.compile(r"\bBrownie\b", re.I), "Fine brown powder"),
    (re.compile(r"\bCocoa\b", re.I), "Fine brown powder"),
    (re.compile(r"\bCoffee\b", re.I), "Fine brown powder"),

    # --- Tan / light-brown family ---
    (re.compile(r"\bCinnamon\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bCinnaBun\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bCaramel\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bSalted\s*Caramel\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bGinger\s*Bread\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bS'mores\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bPeanut\s*Butter\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bMaple\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bBanana\b", re.I), "Fine tan to light brown powder"),
    (re.compile(r"\bButtermilk\b", re.I), "Fine tan to light brown powder"),

    # --- Yellow / orange family ---
    (re.compile(r"\bLemon\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bOrange\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bMango\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bPeach\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bPineapple\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bTropical\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bTangerine\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bCitrus\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bFuzzy\s*Navel\b", re.I), "Fine yellow to orange powder"),
    (re.compile(r"\bPi[nñ]a\s*Colada\b", re.I), "Fine yellow to orange powder"),

    # --- Off-white / cream family ---
    (re.compile(r"\bVanilla\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bBirthday\s*Cake\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bMarshmallow\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bAngel\s*Food\s*Cake\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bCoconut\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bEggnog\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bSugar\s*Cookie\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bCookie\s*Dough\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bButtery\s*Blend\b", re.I), "Fine off-white to cream powder"),
    (re.compile(r"\bSamoa\b", re.I), "Fine off-white to cream powder"),

    # --- White family ---
    (re.compile(r"\bUnflavored\b", re.I), "Fine white to off-white powder"),
    (re.compile(r"\bUnsweetened\b", re.I), "Fine white to off-white powder"),
]

# Products that are capsules/tablets/softgels regardless of flavor column.
_CAPSULE_PRODUCTS = {
    "cla",
    "ejaculoid",
    "natural burn",
    "cholestprotect",
    "sag glutathione",
    "cytronium",
    "sund",
    "shredam",
    "shredpm",
    "md muscle",
    "citruslim",
    "paractin",
    "relief",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class OrganolepticSpecs(NamedTuple):
    """Appearance and Taste specifications for a product."""
    appearance: str
    taste: str


def get_appearance_spec(flavor: str, product: str) -> str:
    """Return the appearance specification string for a given flavor and product.

    Parameters
    ----------
    flavor:
        The flavor column value (may be empty).
    product:
        The product column value (used for capsule/tablet detection).

    Returns
    -------
    str
        A human-readable appearance specification suitable for a COA.
    """
    flavor_clean = (flavor or "").strip()
    product_clean = (product or "").strip()

    # --- Capsule / tablet / softgel detection ---
    if flavor_clean.lower() == "capsules":
        return "Capsules conforming to standard"

    if flavor_clean.lower() == "fat burner":
        return "Conforms to standard"

    if flavor_clean.lower() == "tummy toner":
        return "Conforms to standard"

    if product_clean.lower() in _CAPSULE_PRODUCTS:
        return "Conforms to standard"

    if flavor_clean.lower() in ("not applicable", ""):
        return "Conforms to standard"

    # --- Special product-level overrides ---
    if flavor_clean.lower() == "recovery & regeneration":
        return "Fine powder conforming to standard"

    # Build a combined string so compound flavors like "Chocolate Peanut Butter"
    # match on the first (dominant) keyword via rule ordering.
    search_text = flavor_clean

    for pattern, appearance in _APPEARANCE_RULES:
        if pattern.search(search_text):
            return appearance

    # If nothing matched, return a safe generic default.
    return "Fine powder conforming to standard"


def get_taste_spec(flavor: str, product: str) -> str:
    """Return the taste specification string for a given flavor and product.

    Parameters
    ----------
    flavor:
        The flavor column value (may be empty).
    product:
        The product column value.

    Returns
    -------
    str
        A human-readable taste specification suitable for a COA.
    """
    flavor_clean = (flavor or "").strip()
    product_clean = (product or "").strip()

    if flavor_clean.lower() == "capsules":
        return "Conforms to standard"

    if flavor_clean.lower() in ("fat burner", "tummy toner"):
        return "Conforms to standard"

    if product_clean.lower() in _CAPSULE_PRODUCTS:
        return "Conforms to standard"

    if flavor_clean.lower() in ("not applicable", ""):
        return "Conforms to standard"

    if flavor_clean.lower() in ("unflavored", "unsweetened"):
        return "Bland, characteristic"

    return f"Characteristic {flavor_clean}"


def get_organoleptic_specs(flavor: str, product: str) -> OrganolepticSpecs:
    """Return both Appearance and Taste specs for a product/flavor combination.

    This is a convenience wrapper around ``get_appearance_spec`` and
    ``get_taste_spec``.
    """
    return OrganolepticSpecs(
        appearance=get_appearance_spec(flavor, product),
        taste=get_taste_spec(flavor, product),
    )


# ---------------------------------------------------------------------------
# CSV processing
# ---------------------------------------------------------------------------

def process_csv(csv_path: Path | None = None, *, dry_run: bool = False) -> None:
    """Read the product test mapping CSV, append organoleptic specs, and write back.

    Parameters
    ----------
    csv_path:
        Path to the CSV file. Defaults to the standard location next to this script.
    dry_run:
        If True, print what would be written but do not modify the file.
    """
    if csv_path is None:
        csv_path = CSV_PATH

    # ------------------------------------------------------------------
    # 1. Read
    # ------------------------------------------------------------------
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            print("ERROR: CSV has no header row.", file=sys.stderr)
            sys.exit(1)
        rows: list[dict[str, str]] = list(reader)

    # ------------------------------------------------------------------
    # 2. Transform
    # ------------------------------------------------------------------
    appearance_counter: Counter[str] = Counter()
    updated_count = 0
    skipped_count = 0

    for row in rows:
        required_tests = row.get("Required Tests", "").strip()

        # Skip NO MATCH / empty rows
        if not required_tests:
            skipped_count += 1
            continue

        flavor = row.get("Flavor", "")
        product = row.get("Product", "")
        specs = get_organoleptic_specs(flavor, product)

        # Append test names
        row["Required Tests"] = f"{required_tests}; Appearance; Taste"

        # Append spec values
        existing_specs = row.get("Specifications", "").strip()
        row["Specifications"] = f"{existing_specs}; {specs.appearance}; {specs.taste}"

        # Increment test count
        try:
            current_count = int(row.get("Test Count", "0"))
        except ValueError:
            current_count = 0
        row["Test Count"] = str(current_count + 2)

        appearance_counter[specs.appearance] += 1
        updated_count += 1

    # ------------------------------------------------------------------
    # 3. Write
    # ------------------------------------------------------------------
    if not dry_run:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    print(f"Processed {updated_count} rows, skipped {skipped_count} (no tests).\n")
    print("Appearance spec distribution:")
    for appearance, count in appearance_counter.most_common():
        print(f"  {count:3d}  {appearance}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN (no file changes) ===\n")
    process_csv(dry_run=dry_run)
