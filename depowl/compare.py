"""Compare a full run's results (data/) with the results in the report (expected/)."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load = lambda d, f: json.load(open(os.path.join(ROOT, d, f)))
ok = True
for f, key, fields in [("rq1_results.json", "id", ["incompatible_versions", "prevented"]),
                       ("version_truth.json", "id", ["truly_failing", "suggested", "missed", "extra"]),
                       ("paper_examples.json", "id", ["got"])]:
    exp = {r[key]: r for r in load("expected", f)}
    new = {r[key]: r for r in load("data", f)}
    diffs = [(k, fl, exp[k][fl], new.get(k, {}).get(fl)) for k in exp for fl in fields if new.get(k, {}).get(fl) != exp[k][fl]]
    ok &= not diffs
    print("%-20s %s" % (f, "same as the report" if not diffs else "DIFFERENT"))
    for d in diffs:
        print("    %s %s: report %r, now %r" % d)
r = load("data", "rq1_results.json")
print("\nAll %d failures reproduced: %s" % (len(r), all(x["reproduced"]["runtime_failure"] and x["reproduced"]["link_failure"] for x in r)))
print("Recall: %d of %d prevented (paper: 35 of 38)" % (sum(x["prevented"] for x in r), len(r)))
print("\nFULL RUN MATCHES THE REPORT" if ok else "\nFULL RUN DIFFERS FROM THE REPORT (see above)")
