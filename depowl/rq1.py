"""RQ1: can DepOwl prevent the known CFailures?

For every issue:
  1. build the issue's application snippet against the version it was built against
     (`build`, optionally with the distro's compile directives) and analyse it;
  2. reproduce the failure: run it with LD_BIND_NOW=1 against the `failing` library
     version, and also try to link it against that version;
  3. run DepOwl over the full version history of the library (default directives);
  4. the CFailure is prevented iff the failing version is among the suggested
     incompatible versions (no version range: all versions accepted, as in the paper).
"""
import json, os, subprocess, sys
import app as A
import depowl as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAR = os.path.join(ROOT, "build-variants")


def variant_dir(lib, ver, cflags):
    tag = ver + "-" + cflags.replace("-D", "").replace(" ", "_").lower()
    P = os.path.join(VAR, lib, tag)
    if not os.path.exists(os.path.join(P, ".ok")):
        assert lib == "sqlite"
        amalg = os.path.join(D.BUILD, lib, ver, "src", "sqlite3.c")
        os.makedirs(os.path.join(P, "lib"), exist_ok=True)
        os.makedirs(os.path.join(P, "include"), exist_ok=True)
        so = os.path.join(P, "lib", "libsqlite3.so.0")
        subprocess.run("gcc -g -O0 -fPIC -w -shared -Wl,-soname,libsqlite3.so.0 %s -o %s %s -lpthread -ldl -lm"
                       % (cflags, so, amalg), shell=True, check=True)
        os.symlink("libsqlite3.so.0", os.path.join(P, "lib", "libsqlite3.so"))
        subprocess.run(["cp", os.path.join(D.BUILD, lib, ver, "include", "sqlite3.h"), os.path.join(P, "include")], check=True)
        open(os.path.join(P, ".ok"), "w").close()
    return P


def libdir(lib, ver, variant=None):
    if variant:
        return os.path.join(variant_dir(lib, ver, variant["cflags"]), "lib")
    return os.path.join(D.BUILD, lib, ver, "lib")


def reproduce(issue, binary, src):
    lib, fv = issue["lib"], issue["failing"]
    ld = libdir(lib, fv, issue.get("failing_variant"))
    env = dict(os.environ, LD_LIBRARY_PATH=ld, LD_BIND_NOW="1")
    r = subprocess.run([binary], env=env, capture_output=True, text=True)
    run_err = (r.stderr.strip().splitlines() or [""])[-1]
    run_ok = r.returncode == 0 or ("error" not in r.stderr and "not found" not in r.stderr)
    inc = os.path.join(D.BUILD, lib, issue["build"], "include") if not issue.get("build_variant") else \
        os.path.join(variant_dir(lib, issue["build"], issue["build_variant"]["cflags"]), "include")
    l = subprocess.run(["gcc", "-w", "-I", inc, src, "-o", os.devnull, "-L", ld, "-l" + A.LINK[lib]],
                       capture_output=True, text=True)
    link_err = next((x.strip() for x in l.stderr.splitlines() if "undefined reference" in x or "not found" in x), "")
    return {"runtime_failure": not run_ok, "runtime_msg": run_err.replace(ROOT, "<kit>"),
            "link_failure": l.returncode != 0, "link_msg": link_err}


def analyze_app(issue, src, work):
    lib, bv = issue["lib"], issue["build"]
    if issue.get("build_variant"):
        P = variant_dir(lib, bv, issue["build_variant"]["cflags"])
        # compile against the variant but describe the usage with the default-build model
        out = os.path.join(work, "app-built-vs-%s-variant" % bv)
        os.makedirs(work, exist_ok=True)
        subprocess.run(["gcc", "-g", "-O0", "-w", "-I", os.path.join(P, "include"), src, "-o", out,
                        "-L", os.path.join(P, "lib"), "-l" + A.LINK[lib]], check=True)
        facts = A.ast_facts(lib, bv, src)
        facts.update(undef_syms=A.undef_syms(out), build=bv, binary=out)
        return facts
    return A.analyze(lib, bv, src, work)


def run_issue(issue):
    src = os.path.join(ROOT, "issues", issue["id"] + ".c")
    work = os.path.join(ROOT, "data", "apps", issue["id"])
    facts = analyze_app(issue, src, work)
    json.dump({k: v for k, v in facts.items() if k != "binary"}, open(os.path.join(work, "facts.json"), "w"), indent=1)
    repro = reproduce(issue, facts["binary"], src)
    V, ev = D.run(issue["lib"], facts)
    lib_syms = [s for s in facts["undef_syms"] if not s.startswith(("__", "_ITM", "_Jv", "puts", "printf"))]
    return {
        **{k: issue[k] for k in ("id", "lib", "app", "symbol", "build", "failing", "url")},
        "app_lib_symbols": sorted(lib_syms),
        "reproduced": repro,
        "incompatible_versions": D.compress_ranges(issue["lib"], V) if V else "",
        "n_incompatible": len(V),
        "prevented": issue["failing"] in V,
        "ics_used": [{"change": "%s -> %s" % (e["ic"]["old"], e["ic"]["new"]), "elem": e["ic"]["elem"],
                      "type": e["ic"]["type"], "vbug": e["vbug"]} for e in ev],
    }


PAPER_EXAMPLES = [
    # (id, library, build version, paper's expected incompatible versions)
    ("paper_gzgetc", "zlib", "1.2.5.1", "[1.2.5.2]"),        # Sec. IV-C: gzgetc removed then restored
    ("paper_unalz", "zlib", "1.2.6.1", "[1.2.7, Vlast]"),    # Table III: unalz, get_crc_table long -> int
]


def paper_examples():
    """The paper's two zlib worked examples, built against the version they describe."""
    out = []
    print("\nPaper's worked examples:")
    for name, lib, bv, expected in PAPER_EXAMPLES:
        work = os.path.join(ROOT, "data", "apps", name)
        facts = A.analyze(lib, bv, os.path.join(ROOT, "issues", name + ".c"), work)
        json.dump({k: v for k, v in facts.items() if k != "binary"}, open(os.path.join(work, "facts.json"), "w"), indent=1)
        V, _ = D.run(lib, facts)
        got = D.compress_ranges(lib, V)
        out.append({"id": name, "expected": expected, "got": got, "match": got == expected})
        print("  %-13s paper %-16s ours %-16s %s" % (name, expected, got, "MATCH" if got == expected else "DIFFERENT"))
    json.dump(out, open(os.path.join(ROOT, "data", "paper_examples.json"), "w"), indent=1)



def main():
    issues = json.load(open(os.path.join(ROOT, "issues", "issues.json")))
    only = set(sys.argv[1:])
    res = [run_issue(i) for i in issues if not only or i["id"] in only or i["lib"] in only]
    for r in res:
        print("%-3s %-6s %-28s build=%-8s fail=%-8s repro(run=%s,link=%s) prevented=%s  V=%s" % (
            r["id"], r["lib"], r["symbol"][:28], r["build"], r["failing"], r["reproduced"]["runtime_failure"],
            r["reproduced"]["link_failure"], r["prevented"], r["incompatible_versions"]))
    out = os.path.join(ROOT, "data", "rq1_results%s.json" % ("" if not only else "_" + "_".join(sorted(only))))
    json.dump(res, open(out, "w"), indent=1)
    n = sum(r["prevented"] for r in res)
    print("\nRQ1 recall: %d of %d failures prevented (%.0f%%); paper: 35 of 38 (92%%)" % (n, len(res), 100.0 * n / len(res)))
    if not only:
        paper_examples()



if __name__ == "__main__":
    main()
