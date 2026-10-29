"""Daily supplier on-time-delivery report: clean, metrics, validate, output."""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import polars as pl
import duckdb

PIPE_DIR = Path(__file__).resolve().parent
ROOT = PIPE_DIR.parent
DATA = ROOT / "data"
OUT = PIPE_DIR / "output"
LOG = PIPE_DIR / "pipeline_log.txt"

ASOF = date(2026, 6, 1)     # dataset is frozen in the past, so pin "today"
MIN_ROWS = 500
INPUTS = ("purchase_order_lines.csv", "suppliers.csv")
REQUIRED = ("supplier_id", "promised_date", "po_number")


def log(path: Path, line: str) -> None:
    with open(path, "a") as f:
        f.write(line + "\n")


def load(data_dir: Path) -> dict[str, pl.DataFrame]:
    # Clean
    clean_df = (
        pl.scan_csv(data_dir / "purchase_order_lines.csv")
        .with_columns(
            pl.col("promised_date").str.to_date(strict=False),
            pl.col("received_date").str.to_date(strict=False),
        )
        .with_columns(
            (pl.col("received_date") - pl.col("promised_date")).dt.total_days().alias("days_late"),
        )
        .with_columns(
            (pl.col("days_late") <= 0).alias("on_time"),
        )
        .collect()
    )
    suppliers_df = pl.read_csv(data_dir / "suppliers.csv")
    return {"clean": clean_df, "suppliers": suppliers_df}


def metrics(frames: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    clean_df, suppliers_df = frames["clean"], frames["suppliers"]
    # Metrics
    scorecard_df = duckdb.sql("""
        SELECT
            s.supplier_name,
            COUNT(*)                                              AS total_lines,
            COUNT(*) FILTER (WHERE c.on_time)                     AS on_time_lines,
            ROUND(100.0 * COUNT(*) FILTER (WHERE c.on_time) / COUNT(*), 1) AS otd_pct,
            ROUND(AVG(c.days_late) FILTER (WHERE NOT c.on_time), 1)        AS avg_days_late
        FROM clean_df c
        JOIN suppliers_df s USING (supplier_id)
        WHERE c.received_date IS NOT NULL
        GROUP BY s.supplier_name
        ORDER BY otd_pct ASC
    """).pl()

    monthly_df = duckdb.sql("""
        SELECT
            date_trunc('month', received_date)::date              AS month,
            COUNT(*)                                              AS lines_received,
            ROUND(100.0 * COUNT(*) FILTER (WHERE on_time) / COUNT(*), 1) AS otd_pct
        FROM clean_df
        WHERE received_date IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """).pl()

    aging_df = duckdb.sql(f"""
        SELECT
            s.supplier_name,
            CASE
                WHEN DATE '{ASOF}' - c.promised_date BETWEEN 1 AND 15  THEN '1-15'
                WHEN DATE '{ASOF}' - c.promised_date BETWEEN 16 AND 30 THEN '16-30'
                WHEN DATE '{ASOF}' - c.promised_date BETWEEN 31 AND 60 THEN '31-60'
                ELSE '60+'
            END                                                   AS overdue_bucket,
            COUNT(*)                                              AS open_lines,
            ROUND(SUM(c.qty_ordered * c.unit_price), 0)           AS open_value_usd
        FROM clean_df c
        JOIN suppliers_df s USING (supplier_id)
        WHERE c.received_date IS NULL
          AND c.promised_date < DATE '{ASOF}'
        GROUP BY s.supplier_name, overdue_bucket
        ORDER BY s.supplier_name, open_value_usd DESC
    """).pl()

    return {**frames, "scorecard": scorecard_df, "monthly": monthly_df, "aging": aging_df}


def compute(data_dir: Path) -> dict[str, pl.DataFrame]:
    return metrics(load(data_dir))


def validate(frames: dict[str, pl.DataFrame]) -> str | None:
    """Return why the run must stop, or None if the data is fit to report on."""
    clean_df = frames["clean"]
    if clean_df.height < MIN_ROWS:
        return f"row count {clean_df.height} below floor {MIN_ROWS}"
    nulls = clean_df.select(pl.col(c).is_null().sum() for c in REQUIRED).row(0, named=True)
    bad = {col: n for col, n in nulls.items() if n > 0}
    if bad:
        return f"null values in required columns: {bad}"
    # an inner JOIN would silently drop these lines from the scorecard
    unknown = clean_df.join(frames["suppliers"], on="supplier_id", how="anti")["supplier_id"].unique().sort().to_list()
    if unknown:
        return f"unknown supplier_id: {unknown}"
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--log", type=Path, default=LOG)
    ap.add_argument("--run-date", default=date.today().isoformat())
    args = ap.parse_args(argv)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Validate (a missing file is a failure the scheduler must see, not a bare traceback)
    missing = [name for name in INPUTS if not (args.data / name).exists()]
    if missing:
        reason = f"missing input: {', '.join(missing)}"
    else:
        frames = load(args.data)
        reason = validate(frames)    # before metrics, so bad data never reaches the SQL
    if reason:
        log(args.log, f"{stamp} | FAIL | {reason}")
        print(f"VALIDATION FAILED: {reason}")
        return 1

    # Output
    frames = metrics(frames)
    args.out.mkdir(parents=True, exist_ok=True)
    frames["scorecard"].write_excel(args.out / f"otd_scorecard_{args.run_date}.xlsx")
    frames["monthly"].write_excel(args.out / f"monthly_otd_trend_{args.run_date}.xlsx")
    frames["aging"].write_excel(args.out / f"delinquency_aging_{args.run_date}.xlsx")
    frames["scorecard"].write_parquet(args.out / f"supplier_scorecard_{args.run_date}.parquet")

    clean_df = frames["clean"]
    received = clean_df.filter(pl.col("received_date").is_not_null())
    overall_otd = round(100.0 * received["on_time"].sum() / received.height, 1)

    log(args.log, f"{stamp} | PASS | rows_processed={clean_df.height} | overall_otd={overall_otd}%")

    print(f"OK — {clean_df.height} rows, overall OTD {overall_otd}%")
    print(f"  Wrote 3 Excel files + 1 Parquet to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
