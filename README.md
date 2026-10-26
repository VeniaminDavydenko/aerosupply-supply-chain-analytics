# AeroSupply Analytics — Supplier & Inventory Analysis for an AS9100 Aerospace Shop

End-to-end SQL portfolio project: a synthetic-but-realistic aerospace interiors manufacturer (PSU-100 Passenger Service Units, FAD-200 Fuel Access Doors) analyzed from raw CSVs to a findings memo and a Power BI dashboard.

**Stack:** PostgreSQL · SQL (CTEs, window functions, multi-table joins) · Python (data generation) · Power BI

## The three questions this project answers

1. **Which suppliers are hurting us, and is it getting worse?** → supplier OTD scorecard + quarterly trend with `LAG()`
2. **Can we trust our inventory records?** → cycle-count accuracy by ABC class (96.9% A-class vs 87.3% C-class)
3. **Can we actually build what's released?** → BOM explosion vs on-hand: 7 fastener shortages, all traced to one supplier's overdue POs

Full writeup with numbers: [`FINDINGS.md`](FINDINGS.md)

## Visuals

Each chart exists to answer one specific question from the analysis — rendered by `make_visuals.py` (Q-numbers reference `sql/analysis_queries.sql`).

### Supplier OTD Scorecard
![Supplier OTD scorecard](visuals/supplier_scorecard.png)

**Why this chart:** the first question any buyer asks is "who's late?" — but a raw OTD % alone can mislead. The scorecard (Q04) puts OTD next to volume, average days late, and dollars on late lines, so a 15% supplier with $56K of late spend and a 25% supplier with $781K read as two different problems. The 15-line minimum keeps small-sample suppliers from polluting the ranking.

### Chronic vs Collapsing Suppliers
![Quarterly OTD trend](visuals/otd_quarterly_trend.png)

**Why this chart:** a single OTD number hides direction. The quarterly trend (Q05, built with `LAG()`) separates the two failure modes that need different conversations: Cascade has been bad in every quarter for two years (a sourcing decision), while Pacific Anodize ran mostly 94–100% on time until mid-2025 and then collapsed to 0% (a "what changed at your site?" conversation). The all-supplier line is the baseline both are judged against.

### Cycle-Count Accuracy by ABC Class
![Cycle-count accuracy](visuals/cycle_count_accuracy.png)

**Why this chart:** two panels because there are two different problems, and averaging them hides both. The left panel (Q08) shows *frequency* — record accuracy degrades down the ABC ladder, exactly where count attention is lowest. The right panel (Q10) shows *severity* — C-class leaks the most total dollars through sheer miss volume, but a rare A-class miss costs 4× more per event. The fix is different for each, which is why recommendation 4 targets both ends.

### Shortage Root Cause — One Supplier, Seven Part Numbers
![Shortage root cause](visuals/shortage_root_cause.png)

**Why this chart:** the BOM explosion (Q12) found 7 parts short for released work orders — this chart proves it's really *one* problem. Pairing each shortage (red) with the units already inbound on an overdue Cascade PO (blue) shows the inbound quantity covers the shortfall in every case. No new buys needed; the fix is expediting one supplier, and the days-overdue labels say how urgent that is.

### Shelf-Life Exposure
![Shelf-life exposure](visuals/shelf_life_exposure.png)

**Why this chart:** in an AS9100 shop, expired sealant on the shelf is a quarantine-and-disposition action, not just a cost line. The chart (Q14) splits the exposure into material already past estimated expiry (red, labeled) versus lots inside the 90-day warning window (amber), sized by dollars at risk — which is what makes the $50K of fuel tank sealant the headline.

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
