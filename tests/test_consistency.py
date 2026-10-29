"""The daily pipeline and the SQL analysis must report the same numbers from the same data."""
import re

import polars as pl
import pytest

from pipeline.pipeline import ASOF, compute
from conftest import DATA, ROOT


@pytest.fixture(scope="module")
def frames():
    return compute(DATA)


def test_scorecard_matches_q04(frames, sql_result):
    q04 = sql_result("Q04")
    pipe = {r["supplier_name"]: r for r in frames["scorecard"].iter_rows(named=True)}
    for row in q04.itertuples():
        mine = pipe[row.supplier_name]
        assert mine["otd_pct"] == float(row.otd_pct), row.supplier_name
        assert mine["avg_days_late"] == float(row.avg_days_late), row.supplier_name
        assert mine["total_lines"] == row.lines, row.supplier_name


def test_monthly_matches_q03(frames, sql_result):
    q03 = sql_result("Q03")
    pipe = frames["monthly"]
    assert pipe.height == len(q03)
    for mine, theirs in zip(pipe.iter_rows(named=True), q03.itertuples()):
        assert str(mine["month"]) == str(theirs.month)[:10]
        assert mine["lines_received"] == theirs.lines_received
        assert mine["otd_pct"] == float(theirs.otd_pct)


def test_asof_matches_sql():
    assert str(ASOF) == "2026-06-01"
    sql = (ROOT / "sql" / "analysis_queries.sql").read_text(encoding="utf-8")
    # Q11's 'snapshot_date >= DATE ...' is a 6-month usage window, not the as-of date
    assert set(re.findall(r"(?<!>= )DATE '(\d{4}-\d{2}-\d{2})'", sql)) == {"2026-06-01"}


def test_published_numbers(frames):
    card = frames["scorecard"].filter(pl.col("supplier_name") == "Cascade Fastener Works")
    assert card["otd_pct"].item() == 15.4
    received = frames["clean"].filter(pl.col("received_date").is_not_null())
    assert round(100.0 * received["on_time"].sum() / received.height, 1) == 73.0
