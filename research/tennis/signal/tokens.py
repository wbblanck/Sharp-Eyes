"""Token ids (outcome 0, outcome 1) for condition ids, from Gamma. Caches to JSON.
Usage: tokens.py CIDS.txt OUT.json"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

UA = "sharp-eyes-research/0.1"
cids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
out = Path(sys.argv[2])
tok = json.loads(out.read_text()) if out.exists() else {}
todo = sorted(c for c in set(cids) if c not in tok)
for i in range(0, len(todo), 20):
    q = urllib.parse.urlencode([("condition_ids", c) for c in todo[i:i + 20]] + [("limit", 100), ("closed", "true")])
    for a in range(5):
        try:
            rows = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://gamma-api.polymarket.com/markets?" + q, headers={"User-Agent": UA}), timeout=60).read())
            break
        except Exception as e:
            print("retry", e, file=sys.stderr); time.sleep(10)
    else:
        continue
    for m in rows:
        tok[m["conditionId"]] = json.loads(m["clobTokenIds"])
    if i % 400 == 0:
        out.write_text(json.dumps(tok)); print(i, len(todo), flush=True)
    time.sleep(0.2)
out.write_text(json.dumps(tok))
print("done", len(tok))
