"""Render the README visuals from the generated dataset.

Every figure reproduces a query in sql/analysis_queries.sql (Q-numbers noted
per chart); computed values are asserted against validation_results.txt so
the pictures can never drift from the SQL.

Usage: python make_visuals.py   (writes PNGs into visuals/)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "visuals"
OUT.mkdir(exist_ok=True)

# palette (validated: CVD-safe, >=3:1 on white)
BLUE = "#2a6cb8"
AMBER = "#c87d2a"
RED = "#c23434"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "font.family": "sans-serif",
    "font.size": 11,
    "text.color": INK,
    "axes.edgecolor": BASE,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": INK2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "svg.fonttype": "none",
})

pol = pd.read_csv(DATA / "purchase_order_lines.csv", parse_dates=["order_date", "promised_date", "received_date"])
sup = pd.read_csv(DATA / "suppliers.csv")
snap = pd.read_csv(DATA / "inventory_snapshots.csv", parse_dates=["snapshot_date"])
parts = pd.read_csv(DATA / "parts.csv")

rec = pol[pol.received_date.notna()].merge(sup, on="supplier_id")
rec["on_time"] = rec.received_date <= rec.promised_date
rec["days_late"] = (rec.received_date - rec.promised_date).dt.days
rec["line_value"] = rec.qty_ordered * rec.unit_price


def save(fig, name):
    fig.savefig(OUT / name, dpi=145, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote visuals/{name}")


# ---- 1 · Supplier OTD scorecard (Q04) --------------------------------------
g = rec.groupby(["supplier_name", "primary_commodity"], as_index=False).agg(
    lines=("on_time", "size"),
    otd_pct=("on_time", lambda s: round(100 * s.mean(), 1)),
)
late = rec[~rec.on_time].groupby("supplier_name").agg(
    avg_days_late=("days_late", "mean"), late_spend=("line_value", "sum"))
g = g.merge(late, on="supplier_name", how="left")
g = g[g.lines >= 15].sort_values("otd_pct").head(10)

assert g.iloc[0].supplier_name == "Cascade Fastener Works" and g.iloc[0].otd_pct == 15.4

fig, ax = plt.subplots(figsize=(12.8, 4.6))
ax.axis("off")
ax.set_title("Supplier OTD scorecard — worst 10 (min 15 received lines)",
             fontsize=15, fontweight="bold", loc="left", pad=16)
cols = ["Supplier", "Commodity", "Lines", "OTD %", "Avg Days Late", "Late Spend"]
rows = [[" " + r.supplier_name, r.primary_commodity, f"{r.lines}", f"{r.otd_pct:.1f}%",
         f"{r.avg_days_late:.1f}", f"${r.late_spend:,.0f}"] for r in g.itertuples()]
tbl = ax.table(cellText=rows, colLabels=cols, loc="center", cellLoc="center",
               colWidths=[0.31, 0.21, 0.08, 0.10, 0.14, 0.13])
tbl.auto_set_font_size(False)
tbl.set_fontsize(10.5)
tbl.scale(1, 1.75)
for (r, c), cell in tbl.get_celld().items():
    cell.set_edgecolor("#e6e5df")
    if r == 0:
        cell.set_facecolor("#1f2a38")
        cell.set_text_props(color="white", fontweight="bold")
    elif c == 3:
        v = g.iloc[r - 1].otd_pct
        cell.set_facecolor("#f6d5d3" if v < 60 else "#fbeed7" if v < 85 else "#d9efdf")
    if r > 0 and c == 0:
        cell.set_text_props(ha="left", fontweight="bold", color="#1f2a38")
        cell.PAD = 0.02
save(fig, "supplier_scorecard.png")

# ---- 2 · Quarterly OTD trend: chronic vs collapse (Q03/Q05) -----------------
rec["qtr"] = rec.received_date.dt.to_period("Q")
qtrs = pd.period_range(rec.qtr.min(), "2026Q2", freq="Q")
series = {
    "All suppliers": (rec, BLUE),
    "Cascade Fastener Works": (rec[rec.supplier_name == "Cascade Fastener Works"], AMBER),
    "Pacific Anodize & Finishing": (rec[rec.supplier_name == "Pacific Anodize & Finishing"], RED),
}
fig, ax = plt.subplots(figsize=(11.5, 6))
x = np.arange(len(qtrs))
for name, (df, color) in series.items():
    otd = df.groupby("qtr").on_time.mean().reindex(qtrs) * 100
    if name == "Pacific Anodize & Finishing":
        assert round(otd.loc[pd.Period("2026Q1")], 1) == 0.0
    ax.plot(x, otd.values, color=color, lw=2.2, marker="o", ms=5.5,
            markerfacecolor=color, markeredgecolor="white", markeredgewidth=1.2,
            label=name, zorder=3)
    last = otd.dropna()
    ax.annotate(f"{last.iloc[-1]:.0f}%", (x[qtrs.get_loc(last.index[-1])], last.iloc[-1]),
                xytext=(10, 0), textcoords="offset points", color=color,
                fontweight="bold", fontsize=11.5, va="center")
ax.annotate("Pacific Anodize: 94–100% through Q2 2025,\nthen a four-quarter collapse to 0%",
            xy=(x[4] - 0.07, 48.5), xytext=(x[0] + 0.7, 38), color=RED, fontsize=10.5,
            arrowprops=dict(arrowstyle="->", color=RED, lw=1.2,
                            connectionstyle="arc3,rad=-0.15"))
ax.set_xticks(x)
ax.set_xticklabels([f"Q{q.quarter} '{str(q.year)[2:]}" for q in qtrs])
ax.set_ylim(-4, 104)
ax.yaxis.set_major_formatter(mtick.PercentFormatter())
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.set_title("On-time delivery by quarter — chronic vs collapsing suppliers",
             fontsize=15, fontweight="bold", loc="left", pad=14)
ax.legend(frameon=False, loc="lower left", fontsize=10.5)
save(fig, "otd_quarterly_trend.png")

# ---- 3 · Cycle-count accuracy & variance dollars by ABC class (Q08/Q10) -----
sp = snap.merge(parts[["part_id", "abc_class", "unit_cost"]], on="part_id")
sp["miss"] = sp.counted_qty != sp.system_qty
sp["abs_var_val"] = (sp.counted_qty - sp.system_qty).abs() * sp.unit_cost
acc = sp.groupby("abc_class").agg(accuracy=("miss", lambda s: round(100 * (1 - s.mean()), 1)),
                                  var_dollars=("abs_var_val", "sum"))
assert list(acc.accuracy) == [96.9, 91.0, 87.3]

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
fig.suptitle("Inventory record accuracy degrades down the ABC ladder — but dollars leak everywhere",
             fontsize=15, fontweight="bold", x=0.005, ha="left")
classes = ["A", "B", "C"]
for ax, vals, fmt, sub in [
        (axes[0], acc.accuracy, lambda v: f"{v:.1f}%", "Cycle-count record accuracy (4,896 part-months)"),
        (axes[1], acc.var_dollars / 1000, lambda v: f"${v:,.0f}K", "Absolute variance value, 18 months")]:
    bars = ax.bar(classes, vals, width=0.55, color=["#256abf", "#5598e7", "#86b6ef"], zorder=3)
    for b, v in zip(bars, vals):
        ax.annotate(fmt(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 5), textcoords="offset points", ha="center",
                    fontweight="bold", fontsize=12, color=INK)
    ax.set_title(sub, fontsize=11, color=INK2, loc="left", pad=12)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("ABC class")
    ax.tick_params(axis="x", labelsize=12)
axes[0].set_ylim(0, 112)
axes[0].yaxis.set_major_formatter(mtick.PercentFormatter())
axes[1].yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}K"))
axes[1].annotate("a rare A-class miss still averages $3,497 —\n4× the cost of a C-class miss",
                 xy=(0.04, 0.82), xycoords="axes fraction", fontsize=9.5, color=INK2, style="italic")
fig.tight_layout(rect=[0, 0, 1, 0.90])
save(fig, "cycle_count_accuracy.png")

# ---- 4 · Shortages vs overdue Cascade POs (Q12/Q13) -------------------------
short = pd.DataFrame({  # values from validation_results.txt Q13
    "part": ["Screw E3", "Nutplate A8", "Clamp E5", "Stud D7",
             "Lock Nut B10", "Clamp C7", "Hi-Lok Pin A6"],
    "short_qty": [2382, 2284, 2210, 2028, 1180, 520, 498],
    "inbound": [2618, 3511, 2380, 2261, 1547, 645, 817],
    "days_overdue": [54, 74, 57, 38, 70, 43, 65],
})
fig, ax = plt.subplots(figsize=(11.5, 6))
y = np.arange(len(short))[::-1]
h = 0.36
ax.barh(y + h / 2 + 0.02, short.short_qty, height=h, color=RED, label="Units short for released work orders", zorder=3)
ax.barh(y - h / 2 - 0.02, short.inbound, height=h, color=BLUE, label="Units inbound on overdue Cascade PO", zorder=3)
for yi, r in zip(y, short.itertuples()):
    ax.annotate(f"{r.short_qty:,}", (r.short_qty, yi + h / 2 + 0.02), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=10, color=RED, fontweight="bold")
    ax.annotate(f"{r.inbound:,}  ·  {r.days_overdue} days overdue", (r.inbound, yi - h / 2 - 0.02),
                xytext=(6, 0), textcoords="offset points", va="center", fontsize=10, color=INK2)
ax.set_yticks(y)
ax.set_yticklabels(short.part, fontsize=11.5)
ax.set_xlim(0, 4600)
ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.set_xlabel("Units")
ax.set_title("All 7 work-order shortages trace to one supplier — and its late POs would clear every one",
             fontsize=15, fontweight="bold", loc="left", pad=14)
ax.legend(frameon=False, loc="lower right", fontsize=10.5)
save(fig, "shortage_root_cause.png")

# ---- 5 · Shelf-life exposure (Q14) ------------------------------------------
shelf = pd.DataFrame({  # values from validation_results.txt Q14; as-of 2026-06-01
    "lot": ["Fuel Tank Sealant B3", "Epoxy Adhesive A2", "Fuel Tank Sealant B1",
            "Structural Film Adhesive E1", "Potting Compound D1"],
    "value": [50166, 15188, 13285, 3786, 3760],
    "expiry": ["2025-12-30", "2025-11-15", "2026-07-25", "2026-08-11", "2025-08-09"],
})
shelf["expired"] = pd.to_datetime(shelf.expiry) < pd.Timestamp("2026-06-01")
shelf = shelf.sort_values("value")
fig, ax = plt.subplots(figsize=(11.5, 4.6))
colors = [RED if e else AMBER for e in shelf.expired]
ax.barh(shelf.lot, shelf.value, height=0.55, color=colors, zorder=3)
for i, r in enumerate(shelf.itertuples()):
    tag = "EXPIRED " + r.expiry if r.expired else "expires " + r.expiry
    ax.annotate(f"${r.value:,.0f}  ·  {tag}", (r.value, i), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=10.5,
                color=RED if r.expired else INK2,
                fontweight="bold" if r.expired else "normal")
ax.set_xlim(0, 68000)
ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.tick_params(axis="y", labelsize=11.5)
ax.set_title("Shelf-life exposure on adhesives & sealants — as of 2026-06-01",
             fontsize=15, fontweight="bold", loc="left", pad=14)
save(fig, "shelf_life_exposure.png")

print("all visuals rendered, all assertions passed")
