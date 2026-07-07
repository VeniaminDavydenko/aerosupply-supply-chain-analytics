# AeroSupply Analytics — Supplier & Inventory Analysis for an AS9100 Aerospace Shop

End-to-end SQL portfolio project: a synthetic-but-realistic aerospace interiors manufacturer (PSU-100 Passenger Service Units, FAD-200 Fuel Access Doors) analyzed from raw CSVs to a findings memo and a Power BI dashboard.

**Stack:** PostgreSQL · SQL (CTEs, window functions, multi-table joins) · Python (data generation) · Power BI

## The three questions this project answers

1. **Which suppliers are hurting us, and is it getting worse?** → supplier OTD scorecard + quarterly trend with `LAG()`
2. **Can we trust our inventory records?** → cycle-count accuracy by ABC class (96.9% A-class vs 87.3% C-class)
3. **Can we actually build what's released?** → BOM explosion vs on-hand: 7 fastener shortages, all traced to one supplier's overdue POs

Full writeup with numbers: [`FINDINGS.md`](FINDINGS.md)

## Visuals

### Supplier OTD Scorecard
![Supplier OTD scorecard](visuals/supplier_scorecard.png)

### Chronic vs Collapsing Suppliers
![Quarterly OTD trend](visuals/otd_quarterly_trend.png)

### Cycle-Count Accuracy by ABC Class
![Cycle-count accuracy](visuals/cycle_count_accuracy.png)

### Shortage Root Cause — One Supplier, Seven Part Numbers
![Shortage root cause](visuals/shortage_root_cause.png)

### Shelf-Life Exposure
![Shelf-life exposure](visuals/shelf_life_exposure.png)

## Repo structure

```
├── data/                     # six CSVs (generated)
│   ├── suppliers.csv             40 rows
│   ├── parts.csv                274 rows
│   ├── bom.csv                   64 rows
│   ├── purchase_order_lines.csv  ~1,500 rows
│   ├── inventory_snapshots.csv   4,896 rows (part × month, 18 months)
│   └── production_orders.csv     120 rows
├── sql/
│   ├── schema.sql            # DDL + \copy load + indexes
│   └── analysis_queries.sql  # 14 commented queries in 4 phases
├── visuals/                  # README charts, rendered by make_visuals.py
├── generate_data.py          # reproducible dataset generator (seed=42)
├── make_visuals.py           # renders the charts; asserts against query output
├── run_validation.py         # runs every query, writes validation_results.txt
├── validation_results.txt    # full output of all 14 queries
├── FINDINGS.md               # analyst memo: 3 findings + recommendations
└── powerbi_dashboard_guide.md# data model, DAX measures, 3-page layout
```

## Reproduce it

```bash
createdb aerosupply
cd data && psql -d aerosupply -f ../sql/schema.sql   # loads all six tables
psql -d aerosupply -f ../sql/analysis_queries.sql    # runs the analysis
```

Or regenerate the data from scratch: `python generate_data.py`

## Why synthetic data

Real AS9100 shop data is ITAR/proprietary and can't leave the building. The generator models real patterns from aerospace floor experience — serialized parts, shelf-life-controlled sealants, conditional supplier approvals, work-order-driven demand — and bakes in discoverable problems so the SQL has something true to find. Every number in the findings is the output of a query in `analysis_queries.sql`, not an assumption.
