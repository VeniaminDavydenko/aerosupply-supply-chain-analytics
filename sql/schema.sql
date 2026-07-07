-- ============================================================
-- AeroSupply Analytics — schema & load (PostgreSQL)
-- Synthetic AS9100 aerospace shop: PSU-100 (Passenger Service
-- Unit) and FAD-200 (Fuel Access Door) assemblies.
-- Run from the /data folder:  psql -d aerosupply -f schema.sql
-- ============================================================

DROP TABLE IF EXISTS production_orders, inventory_snapshots,
  purchase_order_lines, bom, parts, suppliers CASCADE;

CREATE TABLE suppliers (
  supplier_id        text PRIMARY KEY,
  supplier_name      text NOT NULL,
  country            text,
  as9100_certified   boolean,
  approval_status    text,            -- Approved / Conditional
  primary_commodity  text
);

CREATE TABLE parts (
  part_id            text PRIMARY KEY,
  part_number        text UNIQUE NOT NULL,
  part_name          text,
  category           text,
  unit_cost          numeric(10,2),
  lead_time_days     integer,
  shelf_life_days    integer,         -- NULL unless shelf-life controlled
  itar_flag          boolean,
  make_or_buy        text,
  preferred_supplier_id text REFERENCES suppliers(supplier_id),
  abc_class          text             -- A / B / C by annual usage value
);

CREATE TABLE bom (
  assembly_part_id   text REFERENCES parts(part_id),
  component_part_id  text REFERENCES parts(part_id),
  qty_per            integer NOT NULL,
  PRIMARY KEY (assembly_part_id, component_part_id)
);

CREATE TABLE purchase_order_lines (
  po_line_id     integer PRIMARY KEY,
  po_number      text,
  part_id        text REFERENCES parts(part_id),
  supplier_id    text REFERENCES suppliers(supplier_id),
  order_date     date,
  promised_date  date,
  received_date  date,                -- NULL = still open
  qty_ordered    integer,
  qty_received   integer,
  unit_price     numeric(10,2)
);

CREATE TABLE inventory_snapshots (
  snapshot_date      date,
  part_id            text REFERENCES parts(part_id),
  system_qty         integer,         -- what the ERP says
  counted_qty        integer,         -- what the cycle count found
  monthly_demand_qty integer,         -- consumed that month
  PRIMARY KEY (snapshot_date, part_id)
);

CREATE TABLE production_orders (
  wo_number        text PRIMARY KEY,
  assembly_part_id text REFERENCES parts(part_id),
  build_qty        integer,
  need_date        date,
  status           text               -- Planned / Released / Complete
);

-- ---------- load ----------
\copy suppliers            FROM 'suppliers.csv'            WITH (FORMAT csv, HEADER true, NULL '');
\copy parts                FROM 'parts.csv'                WITH (FORMAT csv, HEADER true, NULL '');
\copy bom                  FROM 'bom.csv'                  WITH (FORMAT csv, HEADER true);
\copy purchase_order_lines FROM 'purchase_order_lines.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy inventory_snapshots  FROM 'inventory_snapshots.csv'  WITH (FORMAT csv, HEADER true, NULL '');
\copy production_orders    FROM 'production_orders.csv'    WITH (FORMAT csv, HEADER true);

-- ---------- helpful indexes ----------
CREATE INDEX ix_pol_supplier ON purchase_order_lines(supplier_id);
CREATE INDEX ix_pol_part     ON purchase_order_lines(part_id);
CREATE INDEX ix_inv_part     ON inventory_snapshots(part_id);
CREATE INDEX ix_inv_date     ON inventory_snapshots(snapshot_date);
CREATE INDEX ix_bom_assembly ON bom(assembly_part_id);

-- ---------- sanity check ----------
SELECT 'suppliers' AS t, count(*) FROM suppliers
UNION ALL SELECT 'parts', count(*) FROM parts
UNION ALL SELECT 'bom', count(*) FROM bom
UNION ALL SELECT 'purchase_order_lines', count(*) FROM purchase_order_lines
UNION ALL SELECT 'inventory_snapshots', count(*) FROM inventory_snapshots
UNION ALL SELECT 'production_orders', count(*) FROM production_orders;
