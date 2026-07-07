#!/usr/bin/env python3
"""Wipe per-lot lab data and load the real COA Register spreadsheet.

Reads '2.4.4 New COA Register.xlsx', groups rows into standard lots, parent lots
(shared Lot number -> sublots = RefIDs) and multi-SKU composites (shared C-ref),
auto-creates missing products (with their real test panel), and recreates lots /
sublots / test results / releases with the correct status.

Status rules (per group, from the lead row + the ToPrint flag):
  * QC Approval present AND not "NEEDS METALS"      -> RELEASED  (+ COARelease/product)
  * ToPrint == "NEEDS METALS"                       -> PARTIAL_RESULTS (micro in, metals pending)
  * no QC, but the row already has results          -> AWAITING_RELEASE (shows in Release Queue)
  * no QC and no results                            -> AWAITING_RESULTS (shows in Sample Tracker)

Usage:
    cd backend
    .venv/bin/python scripts/load_coa_register.py --dry-run     # report only (default)
    .venv/bin/python scripts/load_coa_register.py --commit      # backup + wipe + load
    .venv/bin/python scripts/load_coa_register.py --append-from-row 1896 --commit
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.coa_release import COARelease  # noqa: E402
from app.models.enums import (  # noqa: E402
    COAReleaseStatus,
    LotStatus,
    LotType,
    TestResultStatus,
)
from app.models.lab_test_type import LabTestType  # noqa: E402
from app.models.lot import Lot, LotProduct, Sublot  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.product_test_spec import ProductTestSpecification  # noqa: E402
from app.models.test_result import TestResult  # noqa: E402
from app.models.user import User  # noqa: E402

DEFAULT_XLSX = "/Users/gregsimek/Downloads/2.4.4 New COA Register.xlsx"
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "labtrack.db")

C_TOPRINT, C_REFID, C_BRAND, C_PRODUCT, C_FLAVOR, C_SIZE, C_LOT = 0, 1, 2, 3, 4, 5, 6
C_MFG, C_EXP, C_RELEASE, C_QC = 7, 8, 9, 14

TEST_COLS = [
    (10, "Total Plate Count"),
    (11, "Yeast & Mold"),
    (12, "Escherichia coli"),
    (13, "Salmonella spp."),
    (15, "Gluten"),
    (16, "Staphylococcus aureus"),
    (17, "Total Coliform Count"),
    (18, "Arsenic"),
    (19, "Cadmium"),
    (20, "Lead"),
    (21, "Mercury"),
    (23, "Caffeine"),
]
# Panel every product is expected to be tested for when nothing else is known.
MICRO_COMMON = ["Total Plate Count", "Yeast & Mold", "Escherichia coli", "Salmonella spp."]
METALS = ["Arsenic", "Cadmium", "Lead", "Mercury"]

WIPE_ORDER = [
    "email_history", "retest_items", "retest_requests", "coa_releases", "coa_history",
    "test_results", "sublots", "lot_products", "audit_annotations", "audit_logs",
    "parsing_queue", "lots", "daane_coc_daily_counters",
]


# --------------------------------------------------------------------------- #
def cell_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def is_composite_ref(refid) -> bool:
    return str(refid).strip().upper().startswith("C")


def display_name(brand, product, flavor, size) -> str:
    return " - ".join(str(p).strip() for p in (brand, product, flavor, size) if p)


def sku_key(row):
    def n(i):
        return str(row[i]).strip().lower() if not is_blank(row[i]) else ""
    return (n(C_BRAND), n(C_PRODUCT), n(C_FLAVOR), n(C_SIZE))


def load_rows(xlsx_path, append_from_row=None):
    ws = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)["Sheet1"]
    rows = []
    for excel_row, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if append_from_row is not None and excel_row < append_from_row:
            continue
        if any(not is_blank(v) for v in r):
            rows.append(list(r))
    return rows


def group_rows(rows):
    flags = []
    c_groups, rest = OrderedDict(), []
    for r in rows:
        (c_groups.setdefault(str(r[C_REFID]).strip(), []).append(r) if is_composite_ref(r[C_REFID])
         else rest.append(r))
    groups = []
    for cref, grp in c_groups.items():
        if len({sku_key(x) for x in grp}) > 1:
            groups.append({"kind": "composite", "key": cref, "rows": grp})
        else:
            groups.append({"kind": "parent", "key": cref, "rows": grp,
                           "ref_override": cref, "lotnum_override": cref})
            flags.append(f"same-SKU composite {cref} loaded as a PARENT lot ({len(grp)} batches)")
    by_lot = OrderedDict()
    for r in rest:
        by_lot.setdefault(str(r[C_LOT]).strip(), []).append(r)
    for lot, grp in by_lot.items():
        groups.append({"kind": "parent" if len(grp) > 1 else "standard", "key": lot, "rows": grp})
    return groups, flags


def build_test_values(row, ltt_by_name):
    out = []
    for idx, name in TEST_COLS:
        if idx < len(row):
            v = cell_str(row[idx])
            if v:
                out.append((name, ltt_by_name.get(name), v))
    return out


def release_date_of(group):
    for r in group["rows"]:
        d = to_date(r[C_RELEASE])
        if d:
            return d
    return None


def classify(group, ltt_by_name):
    """Return (LotStatus, is_released)."""
    first = group["rows"][0]
    qc = not is_blank(first[C_QC])
    needs_metals = any(str(r[C_TOPRINT]).strip() == "NEEDS METALS" for r in group["rows"])
    has_results = bool(build_test_values(first, ltt_by_name))
    if qc and not needs_metals:
        return LotStatus.RELEASED, True
    if needs_metals:
        return LotStatus.PARTIAL_RESULTS, False
    if has_results:
        return LotStatus.AWAITING_RELEASE, False
    return LotStatus.AWAITING_RESULTS, False


def make_ref_generator(existing_refs=None):
    seq = defaultdict(int)
    ref_re = re.compile(r"^(\d{6})-(\d{3})$")
    for ref in existing_refs or ():
        match = ref_re.match(str(ref).strip())
        if match:
            seq[match.group(1)] = max(seq[match.group(1)], int(match.group(2)))
    today = datetime.now().date()

    def gen(mfg):
        prefix = (mfg or today).strftime("%y%m%d")
        seq[prefix] += 1
        return f"{prefix}-{seq[prefix]:03d}"
    return gen


def future_date_flags(rows, first_future_year=2029):
    flags = []
    for r in rows:
        mfg = to_date(r[C_MFG])
        if mfg and mfg.year >= first_future_year:
            flags.append(
                "future Mfg Date "
                f"{mfg.isoformat()} for RefID {cell_str(r[C_REFID])}, "
                f"Lot {cell_str(r[C_LOT])}, "
                f"{display_name(r[C_BRAND], r[C_PRODUCT], r[C_FLAVOR], r[C_SIZE])}"
            )
    return flags


def append_conflicts(db, groups):
    existing_lot_numbers = {
        lot_number for (lot_number,) in db.query(Lot.lot_number).all()
    }
    existing_refs = {
        reference_number for (reference_number,) in db.query(Lot.reference_number).all()
    }
    existing_sublots = {
        sublot_number for (sublot_number,) in db.query(Sublot.sublot_number).all()
    }
    conflicts = []
    for g in groups:
        rows_g = g["rows"]
        first = rows_g[0]
        if g["kind"] == "standard":
            lotnum = cell_str(first[C_LOT])
            if lotnum.upper() == "NEEDS LOT":
                lotnum = cell_str(first[C_REFID])
            ref = cell_str(first[C_REFID])
            if lotnum.upper() in existing_lot_numbers:
                conflicts.append(("lot_number", lotnum, g["key"]))
            if ref.upper() in existing_refs:
                conflicts.append(("reference_number", ref, g["key"]))
        elif g["kind"] == "parent":
            lotnum = g.get("lotnum_override") or cell_str(first[C_LOT])
            if lotnum.upper() in existing_lot_numbers:
                conflicts.append(("lot_number", lotnum, g["key"]))
            if "ref_override" in g and str(g["ref_override"]).strip().upper() in existing_refs:
                conflicts.append(("reference_number", g["ref_override"], g["key"]))
            same_sku_cref = "ref_override" in g
            for r in rows_g:
                sublot = cell_str(r[C_LOT]) if same_sku_cref else cell_str(r[C_REFID])
                if sublot.upper() in existing_sublots:
                    conflicts.append(("sublot_number", sublot, g["key"]))
        else:
            cref = str(g["key"]).strip()
            if cref.upper() in existing_lot_numbers:
                conflicts.append(("lot_number", cref, g["key"]))
            if cref.upper() in existing_refs:
                conflicts.append(("reference_number", cref, g["key"]))
    return conflicts


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Wipe and load the COA register")
    ap.add_argument("--file", default=DEFAULT_XLSX)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--append-from-row",
        type=int,
        help="Append only nonblank workbook rows at or after this Excel row number; never wipes existing lots.",
    )
    args = ap.parse_args()
    commit = args.commit and not args.dry_run
    append_mode = args.append_from_row is not None

    print(f"Source : {args.file}")
    print(f"DB     : {DB_PATH}")
    if append_mode:
        mode = "APPEND COMMIT" if commit else "APPEND DRY RUN"
        print(f"Mode   : {mode} (from Excel row {args.append_from_row}; no wipe)\n")
    else:
        print(f"Mode   : {'COMMIT (wipe + load)' if commit else 'DRY RUN (no writes)'}\n")

    rows = load_rows(args.file, args.append_from_row)
    print(f"Rows read: {len(rows)}")
    groups, flags = group_rows(rows)
    flags.extend(future_date_flags(rows))

    # per-product test panel (union across the product's rows) + needs-metals marker
    product_tests, product_needs_metals = defaultdict(set), defaultdict(bool)
    for r in rows:
        k = sku_key(r)
        for idx, name in TEST_COLS:
            if idx < len(r) and cell_str(r[idx]):
                product_tests[k].add(name)
        if str(r[C_TOPRINT]).strip() == "NEEDS METALS":
            product_needs_metals[k] = True

    db = SessionLocal()
    try:
        ltt_by_name = {t.test_name: t for t in db.query(LabTestType).all()}
        qc_user = db.query(User).filter(User.username == "qcmanager").first()
        if qc_user is None:
            print("FATAL: qcmanager user not found"); sys.exit(1)
        existing = {(
            (p.brand or "").strip().lower(), (p.product_name or "").strip().lower(),
            (p.flavor or "").strip().lower(), (p.size or "").strip().lower(),
        ): p.id for p in db.query(Product).all()}

        statuses = Counter()
        for g in groups:
            st, _ = classify(g, ltt_by_name)
            statuses[st.value] += 1
        needed = OrderedDict()
        for g in groups:
            for r in g["rows"]:
                needed.setdefault(sku_key(r), r)
        to_create = [r for k, r in needed.items() if k not in existing]

        n = {kind: sum(1 for g in groups if g["kind"] == kind) for kind in ("standard", "parent", "composite")}
        print(f"\nLots: {len(groups)}  (standard {n['standard']}, parent {n['parent']}, composite {n['composite']})")
        print("Status breakdown: " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items())))
        print(f"Products: {len(needed)} SKUs referenced, {len(needed) - len(to_create)} existing, {len(to_create)} to create")

        conflicts = append_conflicts(db, groups) if append_mode else []
        if conflicts:
            print("\nFATAL: append import would collide with existing identifiers:")
            for field, value, group_key in conflicts:
                print(f"  ! {field} {value!r} in group {group_key!r}")
            sys.exit(1)

        if not commit:
            if flags:
                print("\nFlags:")
                for f in flags:
                    print(f"  ! {f}")
            print("\nDRY RUN complete — no writes. Re-run with --commit to apply.")
            return

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{DB_PATH}.bak-{ts}"
        shutil.copy2(DB_PATH, backup)
        if not os.path.exists(backup):
            print("FATAL: backup not created"); sys.exit(1)
        print(f"\nBacked up DB -> {backup}")
        if append_mode:
            print("Append mode: existing per-lot lab data left intact.")
        else:
            for t in WIPE_ORDER:
                try:
                    db.execute(text(f"DELETE FROM {t}"))
                except Exception as e:
                    print(f"  (skip wipe {t}: {e})")
            print("Wiped per-lot lab data.")

        existing_refs = {
            reference_number for (reference_number,) in db.query(Lot.reference_number).all()
        } if append_mode else set()
        existing_sublots = {
            sublot_number for (sublot_number,) in db.query(Sublot.sublot_number).all()
        } if append_mode else set()
        gen_ref = make_ref_generator(existing_refs)
        used_refs, used_sublots = set(existing_refs), set(existing_sublots)
        pid_cache = dict(existing)
        counts = Counter()

        specs_done = set()

        def ensure_specs(pid, k):
            # Give a product its required panel, but never touch a product that
            # already has specs (e.g. the seed catalog). Covers products created
            # by an earlier run that had no specs yet.
            if pid in specs_done:
                return
            specs_done.add(pid)
            if db.query(ProductTestSpecification).filter_by(product_id=pid).count() > 0:
                return
            panel = set(product_tests.get(k) or ()) or set(MICRO_COMMON)
            if product_needs_metals.get(k):
                panel |= set(METALS)
            for name in panel:
                ltt = ltt_by_name.get(name)
                if ltt:
                    db.add(ProductTestSpecification(
                        product_id=pid, lab_test_type_id=ltt.id, is_required=True,
                        specification=(ltt.default_specification or "Within limits")[:100]))
                    counts["specs"] += 1

        def get_pid(row):
            k = sku_key(row)
            if k in pid_cache:
                ensure_specs(pid_cache[k], k)
                return pid_cache[k]
            p = Product(
                brand=str(row[C_BRAND]).strip(),
                product_name=str(row[C_PRODUCT]).strip(),
                flavor=(str(row[C_FLAVOR]).strip() or None) if not is_blank(row[C_FLAVOR]) else None,
                size=(str(row[C_SIZE]).strip() or None) if not is_blank(row[C_SIZE]) else None,
                display_name=display_name(row[C_BRAND], row[C_PRODUCT], row[C_FLAVOR], row[C_SIZE]),
            )
            db.add(p); db.flush()
            pid_cache[k] = p.id
            counts["products"] += 1
            ensure_specs(p.id, k)
            return p.id

        def uniq(value, used, label):
            v, i = value, 1
            while v in used:
                i += 1
                v = f"{value}-{i}"
            if v != value:
                flags.append(f"deduped {label} {value!r} -> {v!r}")
            used.add(v)
            return v

        def add_results(lot_id, row, approved, rel_date):
            for name, ltt, v in build_test_values(row, ltt_by_name):
                tr = TestResult(
                    lot_id=lot_id, test_type=name, result_value=v,
                    unit=(ltt.default_unit if ltt else None),
                    specification=(ltt.default_specification if ltt else None),
                    method=(ltt.test_method if ltt else None),
                    lab_test_type_id=(ltt.id if ltt else None), include_on_coa=True,
                    status=TestResultStatus.APPROVED if approved else TestResultStatus.DRAFT)
                if approved:
                    tr.approved_by_id = qc_user.id
                    tr.approved_at = datetime.combine(rel_date or datetime.now().date(), datetime.min.time())
                db.add(tr); counts["results"] += 1

        def add_release(lot_id, pid, rel_date):
            db.add(COARelease(lot_id=lot_id, product_id=pid, status=COAReleaseStatus.RELEASED,
                              released_at=datetime.combine(rel_date or datetime.now().date(), datetime.min.time()),
                              released_by_id=qc_user.id,
                              notes="Loaded from COA register (QC: Tattyana Villegas)"))
            counts["releases"] += 1

        for g in groups:
            rows_g = g["rows"]; first = rows_g[0]
            status, _ = classify(g, ltt_by_name)
            approved = status in (LotStatus.RELEASED, LotStatus.AWAITING_RELEASE)
            rel_date = release_date_of(g)

            if g["kind"] == "standard":
                lotnum = str(first[C_LOT]).strip()
                if lotnum.upper() == "NEEDS LOT":
                    lotnum = str(first[C_REFID]).strip()
                    flags.append(f"NEEDS-LOT row: lot_number set to RefID {lotnum}")
                ref = uniq(str(first[C_REFID]).strip(), used_refs, "reference")
                lot = Lot(lot_number=lotnum, lot_type=LotType.STANDARD, reference_number=ref,
                          mfg_date=to_date(first[C_MFG]), exp_date=to_date(first[C_EXP]),
                          status=status, generate_coa=True)
                db.add(lot); db.flush()
                db.add(LotProduct(lot_id=lot.id, product_id=get_pid(first)))
                add_results(lot.id, first, approved, rel_date)
                if status == LotStatus.RELEASED:
                    add_release(lot.id, get_pid(first), rel_date)

            elif g["kind"] == "parent":
                lotnum = g.get("lotnum_override") or str(first[C_LOT]).strip()
                mfgs = [to_date(r[C_MFG]) for r in rows_g if to_date(r[C_MFG])]
                mfg = min(mfgs) if mfgs else None
                ref = uniq(g["ref_override"], used_refs, "reference") if "ref_override" in g \
                    else uniq(gen_ref(mfg), used_refs, "reference")
                lot = Lot(lot_number=lotnum, lot_type=LotType.PARENT_LOT, reference_number=ref,
                          mfg_date=mfg, exp_date=to_date(first[C_EXP]), status=status, generate_coa=True)
                db.add(lot); db.flush()
                db.add(LotProduct(lot_id=lot.id, product_id=get_pid(first)))
                same_sku_cref = "ref_override" in g
                for r in rows_g:
                    src = str(r[C_LOT]).strip() if same_sku_cref else str(r[C_REFID]).strip()
                    db.add(Sublot(parent_lot_id=lot.id,
                                  sublot_number=uniq(src, used_sublots, "sublot"),
                                  production_date=to_date(r[C_MFG])))
                    counts["sublots"] += 1
                add_results(lot.id, first, approved, rel_date)
                if status == LotStatus.RELEASED:
                    add_release(lot.id, get_pid(first), rel_date)

            else:  # composite
                cref = g["key"]
                ref = uniq(cref, used_refs, "reference")
                lot = Lot(lot_number=cref, lot_type=LotType.MULTI_SKU_COMPOSITE, reference_number=ref,
                          mfg_date=to_date(first[C_MFG]), exp_date=to_date(first[C_EXP]),
                          status=status, generate_coa=True)
                db.add(lot); db.flush()
                by_pid = OrderedDict()
                for r in rows_g:
                    by_pid.setdefault(get_pid(r), []).append(str(r[C_LOT]).strip())
                for pid, lots in by_pid.items():
                    db.add(LotProduct(lot_id=lot.id, product_id=pid, batch_number=", ".join(lots)[:50]))
                add_results(lot.id, first, approved, rel_date)
                if status == LotStatus.RELEASED:
                    for pid in by_pid:
                        add_release(lot.id, pid, rel_date)

        db.commit()
        print(f"\nLoaded: {len(groups)} lots, {counts['sublots']} sublots, {counts['results']} test results, "
              f"{counts['releases']} releases, {counts['products']} products created, {counts['specs']} specs added.")
        print("Status breakdown: " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items())))
        if flags:
            print("\nFlags:")
            for f in flags:
                print(f"  ! {f}")
        print(f"\nDone. Backup at {backup}")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
