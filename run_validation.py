import duckdb, re, sys
con = duckdb.connect()
for t in ["suppliers","parts","bom","purchase_order_lines","inventory_snapshots","production_orders"]:
    con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv('data/{t}.csv', header=true)")

sql = open("sql/analysis_queries.sql").read()
blocks = re.split(r"(?m)^(?=-- Q\d\d)", sql)
out = open("validation_results.txt", "w")
fails = 0
for b in blocks:
    m = re.match(r"-- (Q\d\d)[^\n]*", b)
    if not m: continue
    qid = m.group(0)[3:]
    try:
        df = con.execute(b).fetchdf()
        out.write(f"\n===== {qid} =====\n{df.to_string(index=False)}\n")
        print(qid.split(' ')[0], "ok", len(df), "rows")
    except Exception as e:
        fails += 1
        print(qid.split(' ')[0], "FAIL:", str(e)[:200])
out.close()
sys.exit(1 if fails else 0)
