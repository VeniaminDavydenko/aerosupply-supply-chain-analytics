"""Shared fixtures: a throwaway copy of the PO data, and the SQL queries run on DuckDB."""
import re
import shutil
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TABLES = ["suppliers", "parts", "bom", "purchase_order_lines", "inventory_snapshots", "production_orders"]


@pytest.fixture
def data_copy(tmp_path):
    """The two CSVs the pipeline reads, copied so a test can break them."""
    d = tmp_path / "data"
    d.mkdir()
    for name in ("purchase_order_lines.csv", "suppliers.csv"):
        shutil.copy(DATA / name, d / name)
    return d


@pytest.fixture(scope="session")
def sql_result():
    """Run one query block from sql/analysis_queries.sql by id, the way run_validation.py does."""
    con = duckdb.connect()
    for t in TABLES:
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv('{(DATA / f'{t}.csv').as_posix()}', header=true)")
    blocks = re.split(r"(?m)^(?=-- Q\d\d)", (ROOT / "sql" / "analysis_queries.sql").read_text(encoding="utf-8"))
    by_id = {b[3:6]: b for b in blocks if re.match(r"-- Q\d\d", b)}
    return lambda qid: con.execute(by_id[qid]).fetchdf()
