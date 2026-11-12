import csv, math, sys
from collections import defaultdict
from datetime import datetime, timezone
S = sys.argv[1]  # usage: skill.py PICKS.csv FROZEN_LIST.csv
LIST = {r["wallet"] for r in csv.DictReader(open(sys.argv[2]))}
SPLIT = datetime(2026, 7, 3, tzinfo=timezone.utc).timestamp()
FROZEN = datetime(2026, 10, 29, 14, 10, tzinfo=timezone.utc).timestamp()

def load(path):
    out = []
    for r in csv.DictReader(open(path)):
        if r["q30"] == "":
            continue
        q, q30, pay = float(r["q"]), float(r["q30"]), float(r["payout"])
        if not (0.05 <= q <= 0.95 and 0.05 <= q30 <= 0.95):
            continue
        out.append((r["wallet"], r["eid"], int(r["ts"]), q, q30, pay, r["kind"]))
    return out

hist = load(f"{S}/hist.csv")
paper = [x for x in load(f"{S}/paper.csv") if x[2] >= FROZEN]
hist_eids = {x[1] for x in hist}
paper = [x for x in paper if x[1] not in hist_eids]
print("history picks", len(hist), "dates", datetime.fromtimestamp(min(x[2] for x in hist), timezone.utc).date(), datetime.fromtimestamp(max(x[2] for x in hist), timezone.utc).date())
print("post-freeze picks", len(paper))

def stats(v):
    n = len(v)
    if n < 2: return n, (v[0] if v else 0), 0.0
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)) or 1e-9
    return n, m, m / (sd / math.sqrt(n))

per = defaultdict(lambda: defaultdict(lambda: {"e0": [], "e30": [], "speed": []}))
for name, rows in (("A", [x for x in hist if x[2] < SPLIT]), ("B", [x for x in hist if x[2] >= SPLIT]), ("C", paper)):
    for w, eid, ts, q, q30, pay, kind in rows:
        d = per[w][name]
        d["e0"].append(pay - q); d["e30"].append(pay - q30); d["speed"].append(q30 - q)

# pooled
for grp, ws in (("frozen list", LIST), ("everyone else", None)):
    for per_ in "ABC":
        e0 = []; e30 = []; sp = []
        for w, d in per.items():
            if (ws is None and w in LIST) or (ws is not None and w not in ws): continue
            e0 += d[per_]["e0"]; e30 += d[per_]["e30"]; sp += d[per_]["speed"]
        n, m0, t0 = stats(e0); _, m30, t30 = stats(e30); _, ms, ts_ = stats(sp)
        print(f"{grp:13s} {per_}: picks {n:7d}  edge vs own price {m0*100:+.2f}c (t {t0:+.1f})  vs 30s-later price {m30*100:+.2f}c (t {t30:+.1f})  price move in 30s {ms*100:+.2f}c")

# persistence of e30 between A and B among wallets with >=30 picks in both
MIN = 30
rows = []
for w, d in per.items():
    a, b, c = d["A"]["e30"], d["B"]["e30"], d["C"]["e30"]
    if len(a) >= MIN and len(b) >= MIN:
        rows.append((w, stats(a), stats(b), stats(c), stats(d["A"]["e0"]+d["B"]["e0"]), stats(d["A"]["speed"]+d["B"]["speed"])))
print("wallets with >=30 picks in both halves:", len(rows), "of which on list:", sum(r[0] in LIST for r in rows))
ta = [r[1][2] for r in rows]; tb = [r[2][2] for r in rows]
def corr(x, y):
    mx, my = sum(x)/len(x), sum(y)/len(y)
    sx = math.sqrt(sum((a-mx)**2 for a in x)); sy = math.sqrt(sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a, b in zip(x, y)) / (sx*sy)
print("corr of wallet t-stat (vs 30s price) first half vs second half:", round(corr(ta, tb), 3))
good_a = [r for r in rows if r[1][2] > 2]
print("t>2 in first half:", len(good_a), " of those t>2 in second half:", sum(r[2][2] > 2 for r in good_a), " positive in second half:", sum(r[2][1] > 0 for r in good_a))
print("base rate t>2 in second half among all:", round(sum(t > 2 for t in tb)/len(tb), 3), " positive:", round(sum(r[2][1] > 0 for r in rows)/len(rows), 3))
both = [r for r in rows if r[1][2] > 2 and r[2][2] > 2]
print("\nwallets beating the 30s-later price in BOTH halves (t>2 each):")
for w, a, b, c, e0, sp in sorted(both, key=lambda r: -(r[1][2]+r[2][2])):
    print(f" {w[:10]} list={w in LIST}  A n{a[0]} {a[1]*100:+.1f}c t{a[2]:+.1f} | B n{b[0]} {b[1]*100:+.1f}c t{b[2]:+.1f} | after freeze n{c[0]} {c[1]*100:+.1f}c t{c[2]:+.1f} | own-price edge {e0[1]*100:+.1f}c, 30s move {sp[1]*100:+.1f}c")
# expected false positives if no skill: P(t>2)^2 approx
p = sum(t > 2 for t in ta)/len(ta) * sum(t > 2 for t in tb)/len(tb)
print("expected by chance if halves independent:", round(p*len(rows), 1))
