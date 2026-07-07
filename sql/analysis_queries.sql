-- ============================================================
-- AeroSupply Analytics — analysis_queries.sql (PostgreSQL)
-- 14 queries in 4 phases. As-of date for "today" logic is
-- pinned to 2026-06-01 so results stay reproducible.
-- ============================================================

-- ############################################################
-- PHASE 1 · FOUNDATION — know the data before judging it
-- ############################################################

-- Q01 · Inventory value by ABC class (latest snapshot)
-- Why: confirms the 80/15/5 concentration that justifies an A/B/C
-- control strategy, and sizes total inventory on the books.
SELECT p.abc_class,
       COUNT(DISTINCT p.part_id)                          AS parts,
       SUM(s.system_qty * p.unit_cost)::numeric(12,0)     AS inventory_value,
       ROUND(100.0 * SUM(s.system_qty * p.unit_cost)
             / SUM(SUM(s.system_qty * p.unit_cost)) OVER (), 1) AS pct_of_value
FROM inventory_snapshots s
JOIN parts p USING (part_id)
WHERE s.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
GROUP BY p.abc_class
ORDER BY inventory_value DESC;

-- Q02 · Top 10 parts by inventory value (latest snapshot)
SELECT p.part_number, p.part_name, p.category, p.abc_class,
       s.system_qty,
       (s.system_qty * p.unit_cost)::numeric(12,0) AS value_on_hand
FROM inventory_snapshots s
JOIN parts p USING (part_id)
WHERE s.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
ORDER BY value_on_hand DESC
LIMIT 10;

-- Q03 · Company-wide on-time delivery, by month (received lines only)
-- "On time" = received on or before the promised date.
SELECT DATE_TRUNC('month', received_date)::date AS month,
       COUNT(*)                                  AS lines_received,
       ROUND(100.0 * COUNT(*) FILTER (WHERE received_date <= promised_date)
             / COUNT(*), 1)                      AS otd_pct
FROM purchase_order_lines
WHERE received_date IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- ############################################################
-- PHASE 2 · SUPPLIER OTD — Finding 1
-- ############################################################

-- Q04 · Supplier scorecard: OTD %, average days late, spend impacted
-- Why: ranks suppliers by lateness where it matters (enough volume
-- to judge), and prices the lateness in dollars of affected spend.
SELECT s.supplier_name, s.primary_commodity, s.approval_status,
       COUNT(*)                                                    AS lines,
       ROUND(100.0 * COUNT(*) FILTER (WHERE pol.received_date <= pol.promised_date)
             / COUNT(*), 1)                                        AS otd_pct,
       ROUND(AVG(pol.received_date - pol.promised_date)
             FILTER (WHERE pol.received_date > pol.promised_date)::numeric, 1)
                                                                   AS avg_days_late,
       SUM(pol.qty_ordered * pol.unit_price)
             FILTER (WHERE pol.received_date > pol.promised_date)::numeric(12,0)
                                                                   AS late_spend
FROM purchase_order_lines pol
JOIN suppliers s USING (supplier_id)
WHERE pol.received_date IS NOT NULL
GROUP BY 1, 2, 3
HAVING COUNT(*) >= 15
ORDER BY otd_pct ASC
LIMIT 10;

-- Q05 · Quarterly OTD trend for the worst suppliers, with change vs
-- prior quarter (window function: LAG)
-- Why: a single OTD number hides direction. This separates "always
-- bad" from "getting worse" — different conversations with the supplier.
WITH quarterly AS (
  SELECT s.supplier_name,
         DATE_TRUNC('quarter', pol.received_date)::date AS qtr,
         ROUND(100.0 * COUNT(*) FILTER (WHERE pol.received_date <= pol.promised_date)
               / COUNT(*), 1) AS otd_pct
  FROM purchase_order_lines pol
  JOIN suppliers s USING (supplier_id)
  WHERE pol.received_date IS NOT NULL
    AND s.supplier_id IN (          -- bottom 4 by overall OTD, min 15 lines
      SELECT supplier_id
      FROM purchase_order_lines
      WHERE received_date IS NOT NULL
      GROUP BY supplier_id
      HAVING COUNT(*) >= 15
      ORDER BY 100.0 * COUNT(*) FILTER (WHERE received_date <= promised_date) / COUNT(*)
      LIMIT 4)
  GROUP BY 1, 2
)
SELECT supplier_name, qtr, otd_pct,
       otd_pct - LAG(otd_pct) OVER (PARTITION BY supplier_name ORDER BY qtr)
         AS change_vs_prior_qtr
FROM quarterly
ORDER BY supplier_name, qtr;

-- Q06 · Quoted vs actual lead time by supplier
-- Why: if actual lead time routinely beats the quote, MRP is planning
-- on a fantasy number — buyers should re-baseline lead times.
SELECT s.supplier_name,
       ROUND(AVG(p.lead_time_days)::numeric, 0)                       AS quoted_lt_days,
       ROUND(AVG(pol.received_date - pol.order_date)::numeric, 0)     AS actual_lt_days,
       ROUND(AVG(pol.received_date - pol.order_date)::numeric
             - AVG(p.lead_time_days)::numeric, 0)                     AS gap_days
FROM purchase_order_lines pol
JOIN suppliers s USING (supplier_id)
JOIN parts p USING (part_id)
WHERE pol.received_date IS NOT NULL
GROUP BY 1
HAVING COUNT(*) >= 15
ORDER BY gap_days DESC
LIMIT 10;

-- Q07 · Open-PO exposure: overdue lines as of 2026-06-01
-- Why: this is tomorrow's stockout list. Dollars and days overdue.
SELECT s.supplier_name, p.part_number, p.part_name,
       pol.po_number, pol.promised_date,
       (DATE '2026-06-01' - pol.promised_date)              AS days_overdue,
       pol.qty_ordered,
       (pol.qty_ordered * pol.unit_price)::numeric(12,0)    AS open_value
FROM purchase_order_lines pol
JOIN suppliers s USING (supplier_id)
JOIN parts p USING (part_id)
WHERE pol.received_date IS NULL
  AND pol.promised_date < DATE '2026-06-01'
ORDER BY days_overdue DESC, open_value DESC
LIMIT 15;

-- ############################################################
-- PHASE 3 · INVENTORY RECORD ACCURACY — Finding 2
-- ############################################################

-- Q08 · Record accuracy by ABC class
-- "Accurate" = cycle count matched the system quantity.
-- Why: the headline finding — accuracy degrades down the ABC ladder,
-- exactly where count attention is lowest.
SELECT p.abc_class,
       COUNT(*)                                                       AS part_months,
       ROUND(100.0 * COUNT(*) FILTER (WHERE s.counted_qty = s.system_qty)
             / COUNT(*), 1)                                           AS accuracy_pct,
       ROUND(AVG(ABS(s.counted_qty - s.system_qty))
             FILTER (WHERE s.counted_qty <> s.system_qty)::numeric, 1) AS avg_units_off
FROM inventory_snapshots s
JOIN parts p USING (part_id)
GROUP BY 1
ORDER BY 1;

-- Q09 · Worst 15 parts by miss frequency (with $ variance)
SELECT p.part_number, p.part_name, p.abc_class, p.category,
       COUNT(*) FILTER (WHERE s.counted_qty <> s.system_qty)          AS months_missed,
       ROUND(100.0 * COUNT(*) FILTER (WHERE s.counted_qty <> s.system_qty)
             / COUNT(*), 0)                                           AS miss_rate_pct,
       SUM(ABS(s.counted_qty - s.system_qty) * p.unit_cost)::numeric(12,0)
                                                                      AS abs_variance_value
FROM inventory_snapshots s
JOIN parts p USING (part_id)
GROUP BY 1, 2, 3, 4
ORDER BY months_missed DESC, abs_variance_value DESC
LIMIT 15;

-- Q10 · Where the variance dollars live (by class)
-- Why: C-class misses more often, but does A-class still cost more
-- per miss? Decides where count effort buys the most.
SELECT p.abc_class,
       SUM(ABS(s.counted_qty - s.system_qty) * p.unit_cost)::numeric(12,0)
         AS total_abs_variance_value,
       ROUND(SUM(ABS(s.counted_qty - s.system_qty) * p.unit_cost)::numeric
             / COUNT(*) FILTER (WHERE s.counted_qty <> s.system_qty), 0)
         AS avg_value_per_miss
FROM inventory_snapshots s
JOIN parts p USING (part_id)
GROUP BY 1
ORDER BY 1;

-- Q11 · Excess stock: parts holding > 6 months of supply (latest month)
-- Why: cash tied up in slow movers; months_of_supply = on hand /
-- average monthly demand over the last 6 months.
WITH demand AS (
  SELECT part_id, AVG(monthly_demand_qty) AS avg_mo_demand
  FROM inventory_snapshots
  WHERE snapshot_date >= DATE '2025-12-01'
  GROUP BY part_id
)
SELECT p.part_number, p.part_name, p.abc_class,
       s.system_qty,
       ROUND(d.avg_mo_demand::numeric, 0)                       AS avg_mo_demand,
       ROUND((s.system_qty / NULLIF(d.avg_mo_demand, 0))::numeric, 1) AS months_of_supply,
       (s.system_qty * p.unit_cost)::numeric(12,0)              AS value_on_hand
FROM inventory_snapshots s
JOIN parts p USING (part_id)
JOIN demand d USING (part_id)
WHERE s.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
  AND s.system_qty / NULLIF(d.avg_mo_demand, 0) > 6
ORDER BY value_on_hand DESC
LIMIT 15;

-- ############################################################
-- PHASE 4 · CLEAR-TO-BUILD — Finding 3 (the centerpiece)
-- ############################################################

-- Q12 · Component shortages for released work orders
-- Logic: explode the BOM for every Released WO, total the required
-- qty per component, compare to the latest on-hand. Negative
-- shortfall = cannot build.
WITH requirements AS (
  SELECT b.component_part_id,
         SUM(w.build_qty * b.qty_per) AS total_required
  FROM production_orders w
  JOIN bom b ON b.assembly_part_id = w.assembly_part_id
  WHERE w.status = 'Released'
  GROUP BY b.component_part_id
),
on_hand AS (
  SELECT part_id, system_qty
  FROM inventory_snapshots
  WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
)
SELECT p.part_number, p.part_name, p.abc_class,
       r.total_required,
       o.system_qty                            AS on_hand,
       o.system_qty - r.total_required         AS surplus_or_short,
       ((r.total_required - o.system_qty) * p.unit_cost)::numeric(12,0)
                                               AS shortage_value
FROM requirements r
JOIN on_hand o ON o.part_id = r.component_part_id
JOIN parts p   ON p.part_id = r.component_part_id
WHERE o.system_qty < r.total_required
ORDER BY surplus_or_short ASC;

-- Q13 · Root cause: are the short parts stuck behind late suppliers?
-- Joins the shortage list to open POs and each supplier's track record.
-- This is the query that turns three findings into one story.
WITH requirements AS (
  SELECT b.component_part_id, SUM(w.build_qty * b.qty_per) AS total_required
  FROM production_orders w
  JOIN bom b ON b.assembly_part_id = w.assembly_part_id
  WHERE w.status = 'Released'
  GROUP BY b.component_part_id
),
shortages AS (
  SELECT r.component_part_id AS part_id,
         r.total_required - i.system_qty AS short_qty
  FROM requirements r
  JOIN inventory_snapshots i
    ON i.part_id = r.component_part_id
   AND i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
  WHERE i.system_qty < r.total_required
),
supplier_otd AS (
  SELECT supplier_id,
         ROUND(100.0 * COUNT(*) FILTER (WHERE received_date <= promised_date)
               / COUNT(*), 0) AS otd_pct
  FROM purchase_order_lines
  WHERE received_date IS NOT NULL
  GROUP BY supplier_id
)
SELECT p.part_number, p.part_name, sh.short_qty,
       s.supplier_name,
       so.otd_pct                                    AS supplier_otd_pct,
       pol.po_number, pol.promised_date,
       (DATE '2026-06-01' - pol.promised_date)       AS days_overdue,
       pol.qty_ordered                               AS qty_inbound
FROM shortages sh
JOIN parts p     ON p.part_id = sh.part_id
JOIN suppliers s ON s.supplier_id = p.preferred_supplier_id
JOIN supplier_otd so ON so.supplier_id = s.supplier_id
LEFT JOIN purchase_order_lines pol
       ON pol.part_id = sh.part_id AND pol.received_date IS NULL
ORDER BY sh.short_qty DESC;

-- Q14 · Bonus: shelf-life exposure on adhesives & sealants
-- Assumes newest receipt sets the clock; flags lots that expire
-- within 90 days of 2026-06-01 with stock still on the shelf.
WITH last_receipt AS (
  SELECT part_id, MAX(received_date) AS last_rcv
  FROM purchase_order_lines
  WHERE received_date IS NOT NULL
  GROUP BY part_id
)
SELECT p.part_number, p.part_name, p.shelf_life_days,
       lr.last_rcv,
       (lr.last_rcv + p.shelf_life_days * INTERVAL '1 day')::date AS est_expiry,
       i.system_qty,
       (i.system_qty * p.unit_cost)::numeric(10,0) AS value_at_risk
FROM parts p
JOIN last_receipt lr USING (part_id)
JOIN inventory_snapshots i
  ON i.part_id = p.part_id
 AND i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
WHERE p.shelf_life_days IS NOT NULL
  AND i.system_qty > 0
  AND lr.last_rcv + p.shelf_life_days * INTERVAL '1 day' < DATE '2026-06-01' + INTERVAL '90 days'
ORDER BY est_expiry;
