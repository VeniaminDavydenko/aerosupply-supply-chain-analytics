"""
AeroSupply Analytics - Synthetic dataset generator
Generates a realistic AS9100 aerospace shop (builds Passenger Service Units
and Fuel Access Doors): 6 tables, ~7,800 total rows.

Three findings are deliberately baked in for the SQL analysis to discover:
  1. Four chronically late suppliers (~70-85% late), one deteriorating over time
  2. Inventory record accuracy: ~96% A-class -> ~86% C-class
  3. Clear-to-build shortages on released work orders, mostly caused by
     overdue POs from the late suppliers (connected root cause)
Bonus: shelf-life-controlled adhesives/sealants with near-term expiry risk.

Run:  python generate_data.py   (writes CSVs into ./data)
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(42)
OUT = "data"
import os; os.makedirs(OUT, exist_ok=True)

ASOF = date(2026, 6, 1)          # analysis as-of date
SNAP_MONTHS = pd.date_range("2024-12-31", "2026-05-31", freq="ME")  # 18 month-ends
PO_START, PO_END = date(2024, 7, 1), date(2026, 5, 20)

# ---------------------------------------------------------------- suppliers
commodities = {
    "Fasteners & Hardware": 6, "Machined Components": 8, "Sheet Metal": 5,
    "Electrical Components": 7, "Adhesives & Sealants": 3,
    "Purchased Assemblies": 5, "Raw Material": 4, "Outside Processing": 2,
}
name_pool = ["Cascade","Sellwood","Apex","Tilikum","Summit","Tualatin","Columbia","Willamette",
 "Rainier","Olympic","Northstar","Ridgeline","Bluewing","Skyline","Meridian","Lattice",
 "Sterling","Granite","Falcon","Harbor","Crestline","Ironwood","Vector","Juniper",
 "Stratus","Anchor","Pinnacle","Redwood","Halcyon","Bridger","Larkspur","Quartz",
 "Tamarack","Foxtail","Silverbow","Kestrel","Drift","Argo","Beacon","Cobalt"]
suffix = {"Fasteners & Hardware":"Fastener Works","Machined Components":"Precision Machining",
 "Sheet Metal":"Sheet Metal","Electrical Components":"Electronic Components",
 "Adhesives & Sealants":"Polymer Systems","Purchased Assemblies":"Aerospace Assemblies",
 "Raw Material":"Metals Supply","Outside Processing":"Anodize & Finishing"}
countries = ["USA"]*30 + ["USA","Canada","Mexico","Germany","Japan","Taiwan","USA","UK","USA","Canada"]

rows, i = [], 0
for comm, n in commodities.items():
    for _ in range(n):
        rows.append({"supplier_id": f"S{i+1:03d}",
                     "supplier_name": f"{name_pool[i]} {suffix[comm]}",
                     "country": countries[i],
                     "as9100_certified": bool(rng.random() < 0.75),
                     "approval_status": "Approved",
                     "primary_commodity": comm})
        i += 1
suppliers = pd.DataFrame(rows)

# Finding 1: four chronic offenders (renamed so the story reads well)
BAD = {}
def mark(commodity, new_name, profile):
    sid = suppliers.loc[suppliers.primary_commodity == commodity, "supplier_id"].iloc[0]
    suppliers.loc[suppliers.supplier_id == sid, "supplier_name"] = new_name
    BAD[sid] = profile
    return sid
S_FAST  = mark("Fasteners & Hardware",  "Cascade Fastener Works",        dict(p_late=0.78, late_mu=12, deteriorate=False))
S_ANOD  = mark("Outside Processing",    "Pacific Anodize & Finishing",   dict(p_late=0.80, late_mu=15, deteriorate=True))  # falls off a cliff after Q2-2025
S_MACH  = mark("Machined Components",   "Apex Precision Machining",      dict(p_late=0.72, late_mu=9,  deteriorate=False))
S_ELEC  = mark("Electrical Components", "Velocity Electronic Components",dict(p_late=0.75, late_mu=11, deteriorate=False))
suppliers.loc[suppliers.supplier_id.isin([S_ANOD, S_FAST]), "approval_status"] = "Conditional"
suppliers.loc[suppliers.supplier_id.isin([S_ANOD]), "as9100_certified"] = True  # certified but still late: nice nuance

# ---------------------------------------------------------------- parts (274)
cat_plan = [("Fasteners & Hardware",78,(0.05,4),"FAS"),("Machined Components",50,(40,950),"MCH"),
 ("Sheet Metal",34,(15,260),"SHM"),("Electrical Components",46,(3,420),"ELE"),
 ("Adhesives & Sealants",14,(25,310),"ADH"),("Purchased Assemblies",20,(150,2600),"ASY"),
 ("Raw Material",30,(8,120),"RAW")]
nouns = {"FAS":["Hi-Lok Pin","Hex Bolt","Nutplate","Rivet","Washer","Lock Nut","Screw","Insert","Clamp","Stud"],
 "MCH":["Hinge Fitting","Latch Body","Bracket","Spar Fitting","Cam","Housing","Shaft","Guide Block","Pivot Lug","Stiffener Fitting"],
 "SHM":["Door Skin","Panel","Doubler","Rib","Gusset","Closeout","Frame Channel","Stringer Clip"],
 "ELE":["LED Strip","Wire Harness","Connector","Switch","Terminal Block","Sensor","Relay","Light Lens","PCB Module"],
 "ADH":["Epoxy Adhesive","Fuel Tank Sealant","Primer","Potting Compound","Structural Film Adhesive","Surface Sealant"],
 "ASY":["Oxygen Module","Reading Light Assy","Gasper Outlet","Latch Mechanism","Speaker Assy","PSB Sign Assy","Hinge Assy"],
 "RAW":["7075 Sheet","2024 Sheet","6061 Extrusion","Ti Bar","SS Tube","Honeycomb Core","Phenolic Block"]}
prows, pid = [], 0
for cat, n, (lo, hi), code in cat_plan:
    pool = suppliers[suppliers.primary_commodity.isin(
        [cat, "Outside Processing"] if cat in ("Machined Components","Sheet Metal") else [cat])]
    for k in range(n):
        pid += 1
        noun = nouns[code][k % len(nouns[code])]
        cost = float(np.round(np.exp(rng.uniform(np.log(lo), np.log(hi))), 2))
        prows.append({"part_id": f"P{pid:04d}",
            "part_number": f"{code}-{1000+pid}",
            "part_name": f"{noun} {chr(65+k%6)}{k//6+1}",
            "category": cat,
            "unit_cost": cost,
            "lead_time_days": int(rng.integers(7,21) if code=="FAS" else rng.integers(20,75) if code in("MCH","ASY") else rng.integers(14,45)),
            "shelf_life_days": int(rng.choice([180,270,365])) if code=="ADH" else None,
            "itar_flag": bool(rng.random() < (0.30 if code in ("MCH","ASY") else 0.06)),
            "make_or_buy": "Buy",
            "preferred_supplier_id": pool.sample(1, random_state=int(rng.integers(1e6))).supplier_id.iloc[0]})
parts = pd.DataFrame(prows)
# two top-level make assemblies
for apid, pn, nm in [("P9001","PSU-100","Passenger Service Unit Assy"),
                     ("P9002","FAD-200","Fuel Access Door Assy")]:
    parts.loc[len(parts)] = [apid, pn, nm, "Finished Assembly", 0.0, 0, None, True, "Make", None]

# steer some parts to the bad suppliers so their lateness has teeth
for sid, code, n in [(S_FAST,"FAS",16),(S_MACH,"MCH",10),(S_ELEC,"ELE",10),(S_ANOD,"MCH",6),(S_ANOD,"SHM",5)]:
    idx = parts[parts.part_number.str.startswith(code)].sample(n, random_state=int(rng.integers(1e6))).index
    parts.loc[idx, "preferred_supplier_id"] = sid

# ------------------------------------------------- demand & ABC (computed, then assigned)
base_demand = {"Fasteners & Hardware": (60, 900), "Machined Components": (4, 60),
 "Sheet Metal": (4, 50), "Electrical Components": (8, 160), "Adhesives & Sealants": (3, 30),
 "Purchased Assemblies": (3, 40), "Raw Material": (5, 70)}
buy = parts[parts.make_or_buy=="Buy"].copy()
buy["avg_monthly_demand"] = [int(rng.integers(*base_demand[c])) for c in buy.category]
buy["annual_usage_value"] = buy.avg_monthly_demand * 12 * buy.unit_cost
buy = buy.sort_values("annual_usage_value", ascending=False)
cum = buy.annual_usage_value.cumsum() / buy.annual_usage_value.sum()
buy["abc_class"] = np.where(cum <= 0.80, "A", np.where(cum <= 0.95, "B", "C"))
parts = parts.merge(buy[["part_id","abc_class","avg_monthly_demand"]], on="part_id", how="left")
parts["abc_class"] = parts["abc_class"].fillna("A")  # assemblies
dem_map = dict(zip(buy.part_id, buy.avg_monthly_demand))

# ---------------------------------------------------------------- BOM (single level)
def pick(code, n): return parts[parts.part_number.str.startswith(code)].sample(n, random_state=int(rng.integers(1e6))).part_id.tolist()
bom_rows = []
psu = pick("ELE",12)+pick("ASY",8)+pick("FAS",10)+pick("MCH",4)+pick("SHM",2)
fad = pick("MCH",9)+pick("SHM",8)+pick("FAS",8)+pick("ADH",3)
for comp in psu:
    q = int(rng.integers(8,25)) if comp.startswith(tuple(parts[parts.part_number.str.startswith("FAS")].part_id.str[:5])) else 0
    bom_rows.append({"assembly_part_id":"P9001","component_part_id":comp,
                     "qty_per": int(rng.integers(8,25)) if parts.set_index("part_id").loc[comp,"category"]=="Fasteners & Hardware" else int(rng.integers(1,5))})
for comp in fad:
    bom_rows.append({"assembly_part_id":"P9002","component_part_id":comp,
                     "qty_per": int(rng.integers(10,30)) if parts.set_index("part_id").loc[comp,"category"]=="Fasteners & Hardware" else int(rng.integers(1,4))})
bom = pd.DataFrame(bom_rows).drop_duplicates(subset=["assembly_part_id","component_part_id"])

# ---------------------------------------------------------------- purchase orders (~1,500 lines)
def quarter(d): return (d.year, (d.month-1)//3+1)
po_rows, line_no = [], 0
po_days = (PO_END - PO_START).days
for _, p in parts[parts.make_or_buy=="Buy"].iterrows():
    sid = p.preferred_supplier_id
    n_lines = max(2, int(rng.poisson(5.2)))
    for _ in range(n_lines):
        line_no += 1
        od = PO_START + timedelta(days=int(rng.integers(0, po_days)))
        promised = od + timedelta(days=int(p.lead_time_days + rng.integers(0, 8)))
        qty = max(1, int(rng.normal(dem_map.get(p.part_id, 20)*1.6, dem_map.get(p.part_id, 20)*0.4)))
        # late behaviour
        prof = BAD.get(sid)
        if prof:
            p_late, mu = prof["p_late"], prof["late_mu"]
            if prof["deteriorate"]:                      # Pacific Anodize: fine until Q2-2025, then collapses
                p_late = 0.18 if od < date(2025,7,1) else 0.88
                mu     = 4    if od < date(2025,7,1) else 17
        else:
            p_late, mu = 0.06 + rng.random()*0.10, 5
        late = rng.random() < p_late
        days_off = int(max(1, rng.normal(mu, mu*0.35))) if late else int(rng.integers(-4, 1))
        rec = promised + timedelta(days=days_off)
        open_line = rec > ASOF or (rng.random() < 0.04 and promised > ASOF - timedelta(days=45))
        po_rows.append({"po_line_id": line_no,
            "po_number": f"PO-{24000+line_no//3}", "part_id": p.part_id, "supplier_id": sid,
            "order_date": od, "promised_date": promised,
            "received_date": None if open_line else rec,
            "qty_ordered": qty,
            "qty_received": 0 if open_line else (qty if rng.random()<0.93 else int(qty*rng.uniform(0.7,0.98))),
            "unit_price": round(float(p.unit_cost) * rng.uniform(0.97, 1.06), 2)})
po = pd.DataFrame(po_rows)

# ---------------------------------------------------------------- production orders (~120)
wo_rows = []
for k in range(120):
    asm = "P9001" if rng.random() < 0.58 else "P9002"
    nd = date(2025,1,10) + timedelta(days=int(rng.integers(0, 540)))
    status = "Complete" if nd < ASOF - timedelta(days=14) else ("Released" if nd < ASOF + timedelta(days=45) else "Planned")
    wo_rows.append({"wo_number": f"WO-{5100+k}", "assembly_part_id": asm,
        "build_qty": int(rng.integers(4, 26)), "need_date": nd, "status": status})
wos = pd.DataFrame(wo_rows)

# ---------------------------------------------------------------- inventory snapshots (274 x 18)
# Finding 3 prep: choose shortage parts = BOM components fed by the bad suppliers (+2 others)
open_req = (wos[wos.status.isin(["Released"])]
            .merge(bom, left_on="assembly_part_id", right_on="assembly_part_id")
            .assign(req=lambda d: d.build_qty*d.qty_per)
            .groupby("component_part_id")["req"].sum())
bad_parts = parts[(parts.preferred_supplier_id.isin(BAD)) & (parts.part_id.isin(open_req.index))].part_id.tolist()
short_ids = set(bad_parts[:7] + list(open_req.sort_values(ascending=False).index[:2]))
covered_ids = set(open_req.index) - short_ids   # everything else must clear the build
acc_target = {"A": 0.96, "B": 0.91, "C": 0.86}

snap_rows = []
pi = parts.set_index("part_id")
for pid_, p in pi[pi.make_or_buy=="Buy"].iterrows():
    dem = dem_map[pid_]
    on_hand = int(dem * rng.uniform(1.2, 3.5))
    for d in SNAP_MONTHS:
        d = d.date()
        usage = max(0, int(rng.normal(dem, dem*0.30)))
        receipts = int(dem * rng.uniform(0.7, 1.4)) if rng.random() < 0.8 else 0
        on_hand = max(0, on_hand + receipts - usage)
        sys_qty = on_hand
        if pid_ in short_ids and d >= date(2026,2,28):      # bleed the shortage parts down
            sys_qty = int(max(0, open_req.get(pid_,0) * rng.uniform(0.05, 0.45)))
            on_hand = sys_qty
        if pid_ in covered_ids and d >= date(2026,3,31):    # everyone else can cover the build
            sys_qty = max(sys_qty, int(open_req[pid_] * rng.uniform(1.15, 1.6)))
            on_hand = sys_qty
        if p.abc_class == "C" and rng.random() < 0.18:      # C-class overstock pockets (excess story)
            sys_qty = int(sys_qty + dem * rng.uniform(6, 14)); on_hand = sys_qty
        ok = rng.random() < acc_target[p.abc_class]
        if ok:
            counted = sys_qty
        else:
            mag = max(2, int(abs(rng.normal(0, max(3, sys_qty*0.12)))))
            counted = max(0, sys_qty + int(rng.choice([-1,1])) * max(mag, int(sys_qty*0.03)+1))
        snap_rows.append({"snapshot_date": d, "part_id": pid_, "system_qty": sys_qty,
                          "counted_qty": counted, "monthly_demand_qty": usage})
snaps = pd.DataFrame(snap_rows)

# make sure late suppliers' shortage parts have OVERDUE open POs (the root-cause join)
for spid in short_ids:
    sid = pi.loc[spid, "preferred_supplier_id"]
    if sid in BAD:
        line_no += 1
        od = ASOF - timedelta(days=int(rng.integers(50, 90)))
        po.loc[len(po)] = {"po_line_id": line_no, "po_number": f"PO-{24000+line_no//3}",
            "part_id": spid, "supplier_id": sid, "order_date": od,
            "promised_date": od + timedelta(days=int(pi.loc[spid,"lead_time_days"])),
            "received_date": None, "qty_ordered": int(open_req.get(spid, 50)),
            "qty_received": 0, "unit_price": round(float(pi.loc[spid,"unit_cost"])*1.02, 2)}

# ---------------------------------------------------------------- write
suppliers.to_csv(f"{OUT}/suppliers.csv", index=False)
parts.drop(columns=["avg_monthly_demand"]).to_csv(f"{OUT}/parts.csv", index=False)
bom.to_csv(f"{OUT}/bom.csv", index=False)
po.to_csv(f"{OUT}/purchase_order_lines.csv", index=False)
snaps.to_csv(f"{OUT}/inventory_snapshots.csv", index=False)
wos.to_csv(f"{OUT}/production_orders.csv", index=False)
print({t: len(df) for t, df in [("suppliers",suppliers),("parts",parts),("bom",bom),
       ("purchase_order_lines",po),("inventory_snapshots",snaps),("production_orders",wos)]})
print("late% bad suppliers:", po[po.supplier_id.isin(BAD) & po.received_date.notna()]
      .assign(late=lambda d: pd.to_datetime(d.received_date) > pd.to_datetime(d.promised_date))
      .groupby("supplier_id").late.mean().round(2).to_dict())
acc = snaps.merge(parts[["part_id","abc_class"]], on="part_id")
acc["hit"] = acc.system_qty == acc.counted_qty
print("accuracy by class:", acc.groupby("abc_class").hit.mean().round(3).to_dict())
print("shortage parts:", sorted(short_ids))
