from __future__ import annotations

from datetime import date, datetime

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base
from app.models.coa_release import COARelease
from app.models.enums import LotStatus, LotType, TestResultStatus, UserRole
from app.models.lab_test_type import LabTestType
from app.models.lot import Lot, LotProduct, Sublot
from app.models.product import Product
from app.models.test_result import TestResult
from app.models.user import User
from scripts import load_coa_register as loader


HEADERS = [
    "ToPrint",
    "RefID",
    "Brand",
    "Product",
    "Flavor",
    "Size",
    "Lot",
    "Mfg Date",
    "Exp Date",
    "Release Date",
    "Total Plate Count",
    "Yeast/Mold",
    "E. Coli",
    "Salmonella",
    "QC Approval",
    "Gluten",
    "Staphylococcus aureus",
    "Total Coliform Count",
    "Arsenic",
    "Cadmium",
    "Lead",
    "Mercury",
    "Unused",
    "Caffeine",
]


def _row(values=None):
    values = values or {}
    row = [""] * len(HEADERS)
    defaults = {
        loader.C_BRAND: "BrandCo",
        loader.C_PRODUCT: "Powder",
        loader.C_FLAVOR: "Vanilla",
        loader.C_SIZE: "10 oz",
        loader.C_MFG: date(2026, 1, 1),
        loader.C_EXP: date(2028, 1, 1),
        loader.C_RELEASE: date(2026, 1, 5),
    }
    for idx, value in defaults.items():
        row[idx] = value
    for key, value in values.items():
        row[key] = value
    return row


def _write_register(tmp_path, rows):
    path = tmp_path / "register.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def _register_rows():
    long_batch = "BATCH-" + ("X" * 55)
    return [
        _row(
            {
                loader.C_REFID: "R100",
                loader.C_LOT: "L100",
                loader.C_PRODUCT: "Standard Released",
                10: "<10",
                23: "85",
                loader.C_QC: "Jane Smith",
            }
        ),
        _row(
            {
                loader.C_REFID: "R100",
                loader.C_LOT: "L101",
                loader.C_PRODUCT: "Duplicate Ref",
            }
        ),
        _row(
            {
                loader.C_REFID: "P1A",
                loader.C_LOT: "PL1",
                loader.C_PRODUCT: "Parent Non Lead",
            }
        ),
        _row(
            {
                loader.C_REFID: "P1B",
                loader.C_LOT: "PL1",
                loader.C_PRODUCT: "Parent Non Lead",
                11: "Pass",
            }
        ),
        _row(
            {
                loader.C_REFID: "P2A",
                loader.C_LOT: "PL2",
                loader.C_PRODUCT: "Parent Conflict",
                10: "<10",
                loader.C_QC: "Lead QC",
            }
        ),
        _row(
            {
                loader.C_REFID: "P2B",
                loader.C_LOT: "PL2",
                loader.C_PRODUCT: "Parent Conflict",
                10: "<20",
                11: "Pass",
                loader.C_QC: "Lead QC",
            }
        ),
        _row(
            {
                loader.C_REFID: "C001",
                loader.C_LOT: long_batch,
                loader.C_PRODUCT: "Composite A",
                10: "<10",
                loader.C_QC: "Comp QC",
            }
        ),
        _row(
            {
                loader.C_REFID: "C001",
                loader.C_LOT: "CB2",
                loader.C_PRODUCT: "Composite B",
                13: "Negative",
                loader.C_QC: "Comp QC",
            }
        ),
        _row(
            {
                loader.C_TOPRINT: "NEEDS METALS",
                loader.C_REFID: "NM1",
                loader.C_LOT: "NM1",
                loader.C_PRODUCT: "Needs Metals",
                10: "<10",
                loader.C_QC: "Metal QC",
            }
        ),
    ]


@pytest.fixture
def loader_db(tmp_path, monkeypatch):
    db_path = tmp_path / "labtrack.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    session.execute(text("CREATE TABLE parsing_queue (id INTEGER PRIMARY KEY)"))
    session.add(
        User(
            username="qcmanager",
            email="qc@example.com",
            role=UserRole.QC_MANAGER,
            active=True,
        )
    )
    for name in [
        "Total Plate Count",
        "Yeast & Mold",
        "Escherichia coli",
        "Salmonella spp.",
        "Gluten",
        "Staphylococcus aureus",
        "Total Coliform Count",
        "Arsenic",
        "Cadmium",
        "Lead",
        "Mercury",
    ]:
        category = "Heavy Metals" if name in loader.METALS else "Microbiological"
        session.add(
            LabTestType(
                test_name=name,
                test_category=category,
                default_unit="ppm" if category == "Heavy Metals" else "CFU/g",
                default_specification="Within limits",
                test_method="Method",
                is_active=True,
            )
        )
    session.commit()
    session.close()

    monkeypatch.setattr(loader, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(loader, "DB_PATH", str(db_path))
    monkeypatch.setattr(loader, "BACKUP_DIR", str(tmp_path / "backups"))

    yield TestingSessionLocal

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_dry_run_classifies_and_reports_without_writes(loader_db, tmp_path, capsys):
    workbook = _write_register(tmp_path, _register_rows())

    loader.run_load(file_path=str(workbook), dry_run=True)

    out = capsys.readouterr().out
    assert "standard 3, parent 2, composite 1" in out
    assert "partial_results=1" in out
    assert "awaiting_release=1" in out
    assert "conflicting Total Plate Count result in group 'PL2'" in out
    assert "row 7 Total Plate Count='<20' dropped" in out
    assert "row 2 Caffeine='85' has no LabTestType mapping" in out
    assert "DRY RUN complete" in out

    db = loader_db()
    try:
        assert db.query(Lot).count() == 0
        assert db.query(Product).count() == 0
    finally:
        db.close()


def test_commit_loads_groups_merges_results_and_reconciles(loader_db, tmp_path, capsys):
    workbook = _write_register(tmp_path, _register_rows())

    loader.run_load(file_path=str(workbook), commit=True)

    out = capsys.readouterr().out
    assert "Backed up DB ->" in out
    assert "Reconciliation:" in out
    assert "!!! WARNING: RECONCILIATION MISMATCH !!!" in out
    assert "deduped reference 'R100' -> 'R100-2'" in out
    assert "component batch number exceeds 50 chars in composite C001" in out
    assert "backfill_coa_snapshots.py --commit" in out

    db = loader_db()
    try:
        lots = {lot.lot_number: lot for lot in db.query(Lot).all()}
        assert lots["L100"].lot_type == LotType.STANDARD
        assert lots["PL1"].lot_type == LotType.PARENT_LOT
        assert lots["C001"].lot_type == LotType.MULTI_SKU_COMPOSITE
        assert lots["L100"].status == LotStatus.RELEASED
        assert lots["PL1"].status == LotStatus.AWAITING_RELEASE
        assert lots["NM1"].status == LotStatus.PARTIAL_RESULTS
        assert lots["L101"].reference_number == "R100-2"

        pl1_results = db.query(TestResult).filter_by(lot_id=lots["PL1"].id).all()
        assert [(r.test_type, r.result_value, r.status) for r in pl1_results] == [
            ("Yeast & Mold", "Pass", TestResultStatus.APPROVED)
        ]

        pl2_values = {
            r.test_type: r.result_value
            for r in db.query(TestResult).filter_by(lot_id=lots["PL2"].id).all()
        }
        assert pl2_values == {"Total Plate Count": "<10", "Yeast & Mold": "Pass"}

        notes = sorted(release.notes for release in db.query(COARelease).all())
        assert "Loaded from COA register (QC: Jane Smith)" in notes
        assert "Loaded from COA register (QC: Lead QC)" in notes
        assert notes.count("Loaded from COA register (QC: Comp QC)") == 2
        assert all("Tattyana Villegas" not in note for note in notes)

        composite_batches = [
            lp.batch_number
            for lp in db.query(LotProduct).filter_by(lot_id=lots["C001"].id).all()
        ]
        assert any(batch and len(batch) > 50 for batch in composite_batches)
        assert db.query(Sublot).count() == 4
    finally:
        db.close()


def test_commit_wipe_failure_aborts_and_rolls_back(loader_db, tmp_path, monkeypatch):
    db = loader_db()
    try:
        old_product = Product(
            brand="Old",
            product_name="Product",
            display_name="Old Product",
        )
        db.add(old_product)
        db.flush()
        old_lot = Lot(
            lot_number="OLDLOT",
            lot_type=LotType.STANDARD,
            reference_number="OLDREF",
            mfg_date=date(2026, 1, 1),
            exp_date=date(2028, 1, 1),
            status=LotStatus.AWAITING_RESULTS,
            generate_coa=True,
        )
        db.add(old_lot)
        db.commit()
    finally:
        db.close()

    original_wipe = loader.wipe_per_lot_data

    def wipe_with_delete_failure(session):
        original_execute = session.execute

        def execute(statement, *args, **kwargs):
            if "DELETE FROM test_results" in str(statement):
                raise RuntimeError("delete failed")
            return original_execute(statement, *args, **kwargs)

        session.execute = execute
        original_wipe(session)

    monkeypatch.setattr(loader, "wipe_per_lot_data", wipe_with_delete_failure)
    workbook = _write_register(
        tmp_path,
        [
            _row(
                {
                    loader.C_REFID: "NEWREF",
                    loader.C_LOT: "NEWLOT",
                    loader.C_PRODUCT: "New Product",
                    10: "<10",
                }
            )
        ],
    )

    with pytest.raises(RuntimeError, match="delete failed"):
        loader.run_load(file_path=str(workbook), commit=True)

    db = loader_db()
    try:
        assert db.query(Lot).filter_by(lot_number="OLDLOT").count() == 1
        assert db.query(Lot).filter_by(lot_number="NEWLOT").count() == 0
    finally:
        db.close()


def test_csv_input_dry_run_uses_same_loader_path(loader_db, tmp_path, capsys):
    csv_path = tmp_path / "register.csv"
    rows = _register_rows()[:1]
    with csv_path.open("w", encoding="utf-8") as fh:
        fh.write(",".join(HEADERS) + "\n")
        for row in rows:
            fh.write(",".join(str(value or "") for value in row) + "\n")

    loader.run_load(file_path=str(csv_path), dry_run=True)

    out = capsys.readouterr().out
    assert "Rows read: 1" in out
    assert "released=1" in out


def test_group_rows_separates_reused_lot_by_sku_and_blank_lots():
    rows = [
        loader.RegisterRow(
            _row({loader.C_REFID: "A1", loader.C_LOT: "SHARED", loader.C_PRODUCT: "One"}),
            2,
        ),
        loader.RegisterRow(
            _row({loader.C_REFID: "A2", loader.C_LOT: "SHARED", loader.C_PRODUCT: "One"}),
            3,
        ),
        loader.RegisterRow(
            _row({loader.C_REFID: "B1", loader.C_LOT: "SHARED", loader.C_PRODUCT: "Two"}),
            4,
        ),
        loader.RegisterRow(
            _row({loader.C_REFID: "NOLOT1", loader.C_LOT: None}),
            5,
        ),
        loader.RegisterRow(
            _row({loader.C_REFID: "NOLOT2", loader.C_LOT: "NEEDS LOT"}),
            6,
        ),
    ]

    groups, _ = loader.group_rows(rows)

    assert [(g["kind"], g["key"], len(g["rows"])) for g in groups] == [
        ("parent", "SHARED", 2),
        ("standard", "SHARED", 1),
        ("standard", "NOLOT1", 1),
        ("standard", "NOLOT2", 1),
    ]


def test_append_dedupes_reused_lot_number(loader_db, tmp_path, capsys):
    db = loader_db()
    try:
        db.add(
            Lot(
                lot_number="REUSED",
                lot_type=LotType.STANDARD,
                reference_number="OLDREF",
                status=LotStatus.AWAITING_RESULTS,
                generate_coa=True,
            )
        )
        db.commit()
    finally:
        db.close()

    workbook = _write_register(
        tmp_path,
        [_row({loader.C_REFID: "NEWREF", loader.C_LOT: "REUSED"})],
    )
    loader.run_load(file_path=str(workbook), commit=True, append_from_row=2)

    out = capsys.readouterr().out
    assert "deduped lot number 'REUSED' -> 'REUSED-2'" in out
    db = loader_db()
    try:
        assert db.query(Lot).filter_by(lot_number="REUSED").count() == 1
        assert db.query(Lot).filter_by(lot_number="REUSED-2").count() == 1
    finally:
        db.close()


def test_date_normalization_clamps_invalid_month_end_and_future_year():
    assert loader.to_date("06/31/2029") == date(2029, 6, 30)
    assert loader.to_date("2/24//2026") == date(2026, 2, 24)
    assert loader.to_date("2/29/2026") == date(2026, 2, 28)
    assert loader.to_date("07/20/206") == date(2026, 7, 20)

    row = loader.RegisterRow(
        _row(
            {
                loader.C_REFID: "FUTURE",
                loader.C_MFG: datetime(2029, 6, 27),
                loader.C_RELEASE: datetime(2026, 7, 2),
            }
        ),
        2,
    )
    flags = loader.normalize_future_mfg_typos([row])

    assert row[loader.C_MFG] == date(2026, 6, 27)
    assert "corrected future Mfg Date 2029-06-27 -> 2026-06-27" in flags[0]


def test_dedupes_latest_row_and_groups_shared_non_c_ref():
    rows = [
        loader.RegisterRow(
            _row({loader.C_REFID: "PARENT", loader.C_LOT: "B1"}),
            2,
        ),
        loader.RegisterRow(
            _row({loader.C_REFID: "PARENT", loader.C_LOT: "B2"}),
            3,
        ),
        loader.RegisterRow(
            _row({loader.C_REFID: "DUP", loader.C_LOT: "D1", loader.C_MFG: date(2026, 1, 1)}),
            4,
        ),
        loader.RegisterRow(
            _row({loader.C_REFID: "DUP", loader.C_LOT: "D1", loader.C_MFG: date(2026, 1, 2)}),
            5,
        ),
    ]

    deduped, dedupe_flags = loader.dedupe_register_rows(rows)
    groups, group_flags = loader.group_rows(deduped)

    assert [r.excel_row for r in deduped] == [2, 3, 5]
    assert "duplicate row 4 RefID DUP, Lot D1 skipped" in dedupe_flags[0]
    assert [(g["kind"], g["key"], len(g["rows"])) for g in groups] == [
        ("parent", "PARENT", 2),
        ("standard", "D1", 1),
    ]
    assert "shared non-C RefID PARENT loaded as a PARENT lot" in group_flags[0]
