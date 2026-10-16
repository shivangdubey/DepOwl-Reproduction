"""Quick check (no library builds needed, ~1 minute).

Reruns DepOwl's three steps from the shipped per-version ABI models
(data/abi_cache) and the shipped application facts (data/apps/*/facts.json),
then checks three things against what the report says:
  1. RQ1: which of the 15 failures are prevented (expected 13 of 15);
  2. the paper's two worked zlib examples;
  3. the zlib 1.2.5.1 -> 1.2.5.3 changes against the authors' own ABI-Tracker output
     (test_results/symbols.xlsx in github.com/ZhouyangJia/DepOwl).
It does not rebuild libraries or reproduce the failures; full_run.sh does that.
"""
import json, os, sys
import depowl as D

ROOT = D.ROOT
EXP = os.path.join(ROOT, "expected")
ok_all = True


def check(cond, msg):
    global ok_all
    ok_all &= bool(cond)
    print("  [%s] %s" % ("PASS" if cond else "FAIL", msg))


def facts(name):
    return json.load(open(os.path.join(ROOT, "data", "apps", name, "facts.json")))


print("Step 1: incompatible changes found per library")
stats = json.load(open(os.path.join(EXP, "ic_stats.json")))
for lib in ("zlib", "expat", "sqlite"):
    ics = D.collect_ics(lib)
    check(len(D.versions(lib)) == stats[lib]["versions"] and len(ics) == stats[lib]["ics"],
          "%-6s %3d versions, %3d incompatible changes (report: %d, %d)"
          % (lib, len(D.versions(lib)), len(ics), stats[lib]["versions"], stats[lib]["ics"]))

print("\nRQ1: is each failing version among DepOwl's suggestions?")
expected = {r["id"]: r for r in json.load(open(os.path.join(EXP, "rq1_results.json")))}
prevented = 0
for iid, e in expected.items():
    V, _ = D.run(e["lib"], facts(iid))
    got = D.compress_ranges(e["lib"], V) if V else ""
    p = e["failing"] in V
    prevented += p
    check(got == e["incompatible_versions"] and p == e["prevented"],
          "%-3s %-30s failed on %-9s prevented=%-5s suggested %s" % (iid, e["symbol"][:30], e["failing"], p, got))
print("  => %d of %d prevented (paper: 35 of 38)" % (prevented, len(expected)))

print("\nPaper's worked examples")
for e in json.load(open(os.path.join(EXP, "paper_examples.json"))):
    V, _ = D.run("zlib", facts(e["id"]))
    got = D.compress_ranges("zlib", V)
    check(got == e["expected"], "%-13s paper says %-15s ours %s" % (e["id"], e["expected"], got))

print("\nAuthors' ABI-Tracker output for zlib 1.2.5.1 -> 1.2.5.3 (their repo, test_results/symbols.xlsx)")
authors = {  # (old, new, symbol): direction, as listed in their file
    ("1.2.5.1", "1.2.5.2", "gzgetc"): "backward", ("1.2.5.1", "1.2.5.2", "gzgetc_"): "forward",
    ("1.2.5.1", "1.2.5.2", "inflateResetKeep"): "forward", ("1.2.5.1", "1.2.5.2", "deflateResetKeep"): "forward",
    ("1.2.5.1", "1.2.5.2", "gzflags"): "forward", ("1.2.5.2", "1.2.5.3", "gzgetc"): "forward",
}
ours = {}
for i in D.collect_ics("zlib"):
    if i["elem"][0] == "func" and (i["old"], i["new"]) in (("1.2.5.1", "1.2.5.2"), ("1.2.5.2", "1.2.5.3")):
        ours[(i["old"], i["new"], i["elem"][1])] = "backward" if i["bic"] else "forward"
for k, d in authors.items():
    check(ours.get(k) == d, "%s -> %s  %-17s authors: %-8s ours: %s" % (k[0], k[1], k[2], d, ours.get(k, "not found")))
extra = sorted(set(ours) - set(authors))
check(not extra, "no function changes beyond the authors' list%s" % ("" if not extra else ": " + str(extra)))
other = [i for i in D.collect_ics("zlib") if i["elem"][0] != "func"
         and (i["old"], i["new"]) in (("1.2.5.1", "1.2.5.2"), ("1.2.5.2", "1.2.5.3"))]
print("  (info) not in the authors' file, found by this tool only: %s" % ", ".join(
    "%s %s" % (i["elem"][0], ".".join(x for x in i["elem"][1:] if x)) for i in other))
print("         z_errmsg and the *_copyright variables are internals that zlib 1.2.5.1 exports because its own")
print("         version script is broken (ld: 'unable to find version dependency ZLIB_1.2.5'); the three")
print("         gzFile_s fields are new in the public header of 1.2.5.2.")

print("\nALL CHECKS PASSED" if ok_all else "\nSOME CHECKS FAILED")
sys.exit(0 if ok_all else 1)
