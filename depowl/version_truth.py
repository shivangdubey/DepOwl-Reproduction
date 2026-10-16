"""Extra check beyond the paper: run each issue's app binary (built against its
build version) against EVERY library version in the history (LD_BIND_NOW=1) and
compare the set of versions that really fail to load with DepOwl's suggestion.
This shows the suggestions are not trivially 'everything'."""
import json, os, subprocess
import depowl as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = json.load(open(os.path.join(ROOT, "data", "rq1_results.json")))
out = []
for r in res:
    binary = os.path.join(ROOT, "data", "apps", r["id"],
                          "app-built-vs-%s%s" % (r["build"], "-variant" if r["id"] == "S9" else ""))
    fails = []
    for v in D.versions(r["lib"]):
        env = dict(os.environ, LD_LIBRARY_PATH=os.path.join(D.BUILD, r["lib"], v, "lib"), LD_BIND_NOW="1")
        p = subprocess.run([binary], env=env, capture_output=True, text=True)
        if "symbol lookup error" in p.stderr or "not found" in p.stderr or "undefined symbol" in p.stderr:
            fails.append(v)
    # DepOwl's suggestion as a set (re-run to get the raw list)
    import app as A
    facts = {"undef_syms": A.undef_syms(binary), "build": r["build"],
             **A.ast_facts(r["lib"], r["build"], os.path.join(ROOT, "issues", r["id"] + ".c"))}
    V, _ = D.run(r["lib"], facts)
    T, S = set(fails), set(V)
    out.append({"id": r["id"], "n_versions": len(D.versions(r["lib"])), "truly_failing": len(T), "suggested": len(S),
                "both": len(T & S), "missed": D.compress_ranges(r["lib"], sorted(T - S, key=D.vkey)),
                "extra": D.compress_ranges(r["lib"], sorted(S - T, key=D.vkey)),
                "build_in_suggested": r["build"] in S})
    o = out[-1]
    print("%-3s versions=%-3d truly-fail=%-3d suggested=%-3d overlap=%-3d missed=%s extra=%s build_flagged=%s" % (
        o["id"], o["n_versions"], o["truly_failing"], o["suggested"], o["both"], o["missed"] or "-", o["extra"] or "-",
        o["build_in_suggested"]))
json.dump(out, open(os.path.join(ROOT, "data", "version_truth.json"), "w"), indent=1)
