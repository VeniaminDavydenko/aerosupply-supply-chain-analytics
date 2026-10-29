"""The pipeline passes on good data and fails loudly, before writing anything, on bad data."""
import csv

from pipeline.pipeline import main
from conftest import DATA

RUN_DATE = "2026-07-20"
OUTPUTS = {
    f"otd_scorecard_{RUN_DATE}.xlsx",
    f"monthly_otd_trend_{RUN_DATE}.xlsx",
    f"delinquency_aging_{RUN_DATE}.xlsx",
    f"supplier_scorecard_{RUN_DATE}.parquet",
}


def run(data_dir, tmp_path):
    out, log = tmp_path / "out", tmp_path / "log.txt"
    code = main(["--data", str(data_dir), "--out", str(out), "--log", str(log), "--run-date", RUN_DATE])
    lines = log.read_text().splitlines() if log.exists() else []
    files = {p.name for p in out.iterdir()} if out.exists() else set()
    return code, lines, files


def edit_po_lines(data_dir, change):
    """Rewrite purchase_order_lines.csv after change(rows), where rows excludes the header."""
    path = data_dir / "purchase_order_lines.csv"
    with open(path, newline="") as f:
        header, *rows = list(csv.reader(f))
    rows = change(rows)
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([header, *rows])
    return header


def test_pass_on_repo_data(tmp_path):
    code, lines, files = run(DATA, tmp_path)
    assert code == 0
    assert "| PASS | rows_processed=1478 | overall_otd=73.0%" in lines[-1]
    assert files == OUTPUTS


def test_fail_below_row_floor(data_copy, tmp_path):
    edit_po_lines(data_copy, lambda rows: rows[:100])
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL | row count 100 below floor 500" in lines[-1]
    assert files == set()


def test_fail_header_only(data_copy, tmp_path):
    edit_po_lines(data_copy, lambda rows: [])
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL | row count 0 below floor 500" in lines[-1]
    assert files == set()


def test_fail_null_supplier(data_copy, tmp_path):
    header = (DATA / "purchase_order_lines.csv").read_text().splitlines()[0].split(",")
    col = header.index("supplier_id")
    edit_po_lines(data_copy, lambda rows: [[*r[:col], "", *r[col + 1:]] if i == 0 else r for i, r in enumerate(rows)])
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL |" in lines[-1] and "supplier_id" in lines[-1]
    assert files == set()


def test_fail_bad_promised_date(data_copy, tmp_path):
    header = (DATA / "purchase_order_lines.csv").read_text().splitlines()[0].split(",")
    col = header.index("promised_date")
    edit_po_lines(data_copy, lambda rows: [[*r[:col], "not-a-date", *r[col + 1:]] if i == 0 else r for i, r in enumerate(rows)])
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL |" in lines[-1] and "promised_date" in lines[-1]
    assert files == set()


def test_fail_missing_input(data_copy, tmp_path):
    (data_copy / "purchase_order_lines.csv").unlink()
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL | missing input" in lines[-1] and "purchase_order_lines.csv" in lines[-1]
    assert files == set()


def test_fail_unknown_supplier(data_copy, tmp_path):
    header = (DATA / "purchase_order_lines.csv").read_text().splitlines()[0].split(",")
    col = header.index("supplier_id")
    edit_po_lines(data_copy, lambda rows: [[*r[:col], "S999", *r[col + 1:]] if i == 0 else r for i, r in enumerate(rows)])
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL | unknown supplier_id: ['S999']" in lines[-1]
    assert files == set()


def test_same_day_rerun(tmp_path):
    run(DATA, tmp_path)
    code, lines, files = run(DATA, tmp_path)
    assert code == 0
    assert files == OUTPUTS
    assert sum("| PASS |" in line for line in lines) == 2


def test_fail_unreadable_input(data_copy, tmp_path):
    (data_copy / "purchase_order_lines.csv").write_text("")
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL | cannot read input" in lines[-1]
    assert files == set()


def test_fail_duplicate_supplier(data_copy, tmp_path):
    path = data_copy / "suppliers.csv"
    text = path.read_text()
    path.write_text(text + text.splitlines()[1] + "\n")
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL | duplicate supplier_id in suppliers.csv: ['S001']" in lines[-1]
    assert files == set()


def test_fail_bad_received_date(data_copy, tmp_path):
    header = (DATA / "purchase_order_lines.csv").read_text().splitlines()[0].split(",")
    col = header.index("received_date")
    edit_po_lines(data_copy, lambda rows: [[*r[:col], "2026-13-45", *r[col + 1:]] if i == 0 else r for i, r in enumerate(rows)])
    code, lines, files = run(data_copy, tmp_path)
    assert code == 1
    assert "| FAIL | unparseable received_date" in lines[-1]
    assert files == set()
