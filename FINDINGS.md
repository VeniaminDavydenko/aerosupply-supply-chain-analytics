# AeroSupply Analytics — Findings & Recommendations

**Analyst:** Veniamin Davydenko · **As-of date:** June 1, 2026
**Scope:** 274 parts · 40 suppliers · 1,478 PO lines · 18 months of inventory snapshots · 120 work orders

The company builds two aircraft-interior assemblies — the PSU-100 Passenger Service Unit and the FAD-200 Fuel Access Door — under AS9100. Total inventory on the books at the May 2026 snapshot is **$5.73M**, with A-class parts holding 56.5% of the value across just 60 part numbers.

---

## Finding 1 — Four suppliers drive most of our delivery risk, and one of them is in free fall

Company-wide on-time delivery runs in the low-to-mid 70s and has been slipping: Q1 2026 months came in at 59–68%, the worst stretch in the data. The decline is not broad-based. The supplier scorecard (Q04) shows a clean cliff: four suppliers sit between **15% and 58% OTD**, and everyone else is at 62% or better.

| Supplier | OTD % | Avg days late | Spend on late lines |
|---|---|---|---|
| Cascade Fastener Works | 15.4% | 11.3 | $56K |
| Apex Precision Machining | 25.0% | 8.0 | $781K |
| Velocity Electronic Components | 30.5% | 11.2 | $375K |
| Pacific Anodize & Finishing | 57.6% | 13.8 | $185K |

The quarterly trend (Q05, using LAG) separates two very different problems. Cascade has **always** been bad — between 5.6% and 35.7% OTD in every quarter for two years. Pacific Anodize is the opposite: it ran **94–100% on-time in three of its first four quarters (66.7% in Q4 2024), then collapsed to 50% → 42% → 0% → 0%**. Something changed at that supplier around mid-2025 (capacity, ownership, staffing), and our quoted lead times never adjusted: actual lead times now run 8–13 days past quote for all four offenders (Q06).

## Finding 2 — Inventory records get less trustworthy exactly where we look least

Cycle-count results against system quantities (Q08, 4,896 part-months):

| ABC class | Record accuracy | Avg units off (when wrong) |
|---|---|---|
| A | 96.9% | 13 |
| B | 91.0% | 35 |
| C | **87.3%** | 418 |

The miss *frequency* concentrates in C-class — all 15 of the worst parts by miss count are C items (Q09). But the dollars split differently (Q10): C-class contributes **$264K** of the $442K total absolute variance through sheer volume of misses, while a rare A-class miss costs **$3,497 on average** — 4x a C-class miss. The count program needs both: more C-bin coverage to fix frequency, and tighter A-item controls because each A miss is expensive.

## Finding 3 — Seven fasteners are blocking released work orders, and they all trace to one supplier

Exploding the BOM for every **Released** work order and comparing total requirements to current on-hand (Q12) flags **7 component shortages — every one a C-class fastener**, with shortfalls from 498 to 2,382 units. Cheap parts, expensive consequences: these screws, nutplates, and studs gate assemblies worth far more than their $52–$4,340 shortage values.

The root-cause join (Q13) closes the loop: **all seven short parts have open purchase orders with Cascade Fastener Works — 38 to 74 days overdue** — and in each case the overdue quantity inbound would clear the shortage. This is not seven problems; it is one supplier problem wearing seven part numbers.

## Bonus finding — Expired shelf-life material is still on the shelf

Five adhesive/sealant lots are inside the 90-day expiry window or past it (Q14). Three are **already past estimated expiry**, including $50K of fuel tank sealant (ADH-1222) — in an AS9100 environment that is a quarantine-and-disposition action, not just a cost issue.

## Secondary observation — Excess stock

15 parts hold more than 6 months of supply, totaling **~$2.4M** (Q11) — concentrated in high-value purchased assemblies (PSB signs, oxygen modules) plus C-class overstock pockets like 47K washers (71 months of supply). Worth a buy-policy review, with the caveat that work-order-driven demand is lumpy, so months-of-supply on slow movers overstates the problem for some MRP-planned items.

---

## Recommendations

1. **Escalate Cascade Fastener Works this week.** Daily expedite cadence on the 7 overdue POs blocking released builds; supplier corrective action request; begin qualifying a second fastener source. At 15% OTD over two years, this is a sourcing decision, not a follow-up email.
2. **Investigate Pacific Anodize before it costs a build.** The Q3-2025 collapse pattern means a site visit / capacity conversation now, while exposure is still mostly machined-part finishing rather than line-down events.
3. **Re-baseline lead times for the four offenders** (+8 to +13 days) so MRP plans on reality, and add safety stock to fasteners on active BOMs sourced from single suppliers.
4. **Rebalance the cycle-count program:** increase C-class coverage on parts feeding open work orders (frequency problem) and add control counts on top-value A items (severity problem).
5. **Quarantine and disposition the three expired sealant lots** and add a shelf-life expiry report to the weekly inventory review.

*Built from synthetic data modeled on real AS9100 shop-floor patterns; all figures reproducible from `analysis_queries.sql` against the included dataset.*
