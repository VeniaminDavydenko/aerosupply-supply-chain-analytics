# Power BI Dashboard Build Guide — AeroSupply Analytics

Everything below is ready to paste. Budget ~45–60 minutes in Power BI Desktop.

## 1 · Connect

Get Data → PostgreSQL (server: localhost, database: aerosupply) → import all six tables.
No PostgreSQL running? Get Data → Text/CSV and load the six CSVs from `/data` instead — relationships work the same.

## 2 · Data model (star-ish schema)

Facts: `purchase_order_lines`, `inventory_snapshots`, `production_orders`
Dimensions: `parts`, `suppliers`, plus a `DateTable` you create.

Relationships (single direction, dimension → fact):
- parts[part_id] → purchase_order_lines[part_id]
- parts[part_id] → inventory_snapshots[part_id]
- parts[part_id] → production_orders[assembly_part_id]
- suppliers[supplier_id] → purchase_order_lines[supplier_id]
- DateTable[Date] → purchase_order_lines[received_date]  (active)
- DateTable[Date] → inventory_snapshots[snapshot_date]   (inactive — activate per-measure with USERELATIONSHIP)

`bom` stays unrelated; it's used by the shortage measures via DAX, or pre-compute shortages in SQL (Q12) and import that view — simpler and what I'd do first.

## 3 · Date table (Modeling → New table)

```DAX
DateTable =
ADDCOLUMNS (
    CALENDAR ( DATE(2024,7,1), DATE(2026,6,30) ),
    "Year", YEAR([Date]),
    "Quarter", "Q" & FORMAT([Date], "Q YYYY"),
    "Month", FORMAT([Date], "MMM YYYY"),
    "MonthSort", FORMAT([Date], "YYYYMM")
)
```
Mark as date table. Sort Month by MonthSort.

## 4 · DAX measures (create a blank table `_Measures` to hold them)

```DAX
Lines Received =
CALCULATE ( COUNTROWS(purchase_order_lines),
    NOT ISBLANK(purchase_order_lines[received_date]) )

On-Time Lines =
CALCULATE ( COUNTROWS(purchase_order_lines),
    purchase_order_lines[received_date] <= purchase_order_lines[promised_date] )

OTD % = DIVIDE ( [On-Time Lines], [Lines Received] )

Avg Days Late =
AVERAGEX (
    FILTER ( purchase_order_lines,
        purchase_order_lines[received_date] > purchase_order_lines[promised_date] ),
    DATEDIFF ( purchase_order_lines[promised_date],
               purchase_order_lines[received_date], DAY ) )

OTD % Prior Qtr =
CALCULATE ( [OTD %], DATEADD ( DateTable[Date], -1, QUARTER ) )

OTD Change vs PQ = [OTD %] - [OTD % Prior Qtr]

Open PO Value =
CALCULATE ( SUMX ( purchase_order_lines,
        purchase_order_lines[qty_ordered] * purchase_order_lines[unit_price] ),
    ISBLANK ( purchase_order_lines[received_date] ) )

Inventory Value =
VAR LastSnap = CALCULATE ( MAX ( inventory_snapshots[snapshot_date] ), ALL ( DateTable ) )
RETURN
CALCULATE (
    SUMX ( inventory_snapshots,
        inventory_snapshots[system_qty] * RELATED ( parts[unit_cost] ) ),
    inventory_snapshots[snapshot_date] = LastSnap )

Accurate Counts =
CALCULATE ( COUNTROWS ( inventory_snapshots ),
    FILTER ( inventory_snapshots,
        inventory_snapshots[counted_qty] = inventory_snapshots[system_qty] ) )

Record Accuracy % =
DIVIDE ( [Accurate Counts], COUNTROWS ( inventory_snapshots ) )

Abs Variance Value =
SUMX ( inventory_snapshots,
    ABS ( inventory_snapshots[counted_qty] - inventory_snapshots[system_qty] )
        * RELATED ( parts[unit_cost] ) )
```

## 5 · Three pages

**Page 1 — Executive Summary.** KPI cards: OTD % · Inventory Value · Record Accuracy % · Open PO Value. Line chart: OTD % by Month (DateTable). Bar: Inventory Value by abc_class. Slicer: Quarter.

**Page 2 — Supplier Scorecard.** Table: supplier_name, Lines Received, OTD %, Avg Days Late, Open PO Value, with conditional formatting (red < 60% OTD). Line chart: OTD % by Quarter, legend = supplier_name, filtered to the bottom 4 — this is where Pacific Anodize's collapse becomes the visual centerpiece. Scatter: OTD % (x) vs Avg Days Late (y), size = Open PO Value.

**Page 3 — Inventory Health & Clear-to-Build.** Clustered bar: Record Accuracy % by abc_class (the 96.9 → 87.3 stair-step). Table: shortage list (import Q12's result as `v_shortages` or run it as a SQL view), columns: part_number, total_required, on_hand, surplus_or_short, with red data bars. Card: count of short parts. Table: Q14 shelf-life flags.

## 6 · Polish

Theme: View → Themes → customize to a dark navy/amber palette (aerospace, not default yellow-green). Page tooltips on the supplier table showing that supplier's quarterly trend. Publish to Power BI Service, take PNGs of each page for the GitHub README.
