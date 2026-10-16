"""Simplified re-implementation of DepOwl (Jia et al., ICSE 2021).

Step 1  collect_ics():   incompatible changes between every pair of successive
                         library versions, IC(vi,vi+1) = BIC(vi,vi+1) U BIC(vi+1,vi)
                         (Eq. 1-4); pairs with different sonames are skipped.
Step 2  detect():        for each IC whose element the application uses, apply the
                         Table II rules to decide whether v_old or v_new is
                         incompatible with the application.
Step 3  suggest():       every version that is both backward and forward compatible
                         with v_bug w.r.t. the changed element is also incompatible
                         (Eq. 5-8).

Element = ("func", name) | ("var", name) | ("record", name, field) | ("enum", name, member)
"""
import json, os, re
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
# per-version ABI models; DEPOWL_CACHE lets a full rerun write a fresh cache instead of the shipped one
CACHE = os.environ.get("DEPOWL_CACHE") or os.path.join(ROOT, "data", "abi_cache")


def vkey(v):
    return [int(x) for x in re.findall(r"\d+", v)]


# --------------------------------------------------------------------------- models
@lru_cache(maxsize=None)
def model(lib, ver, prefix=None):
    os.makedirs(CACHE, exist_ok=True)
    cf = os.path.join(CACHE, "%s-%s.json" % (lib, ver))
    if os.path.exists(cf):
        return json.load(open(cf))
    import abi
    libdir = os.path.join(BUILD, lib, ver, "lib")
    so = [f for f in os.listdir(libdir) if re.search(r"\.so\.\d+\.\d", f) or f.endswith(".so." + ver)]
    # like ABI-tracker, restrict to the public API (non-API internals are exported by old libtool builds)
    prefix = {"sqlite": "sqlite3_", "expat": "XML_"}.get(lib, prefix)
    # record/enum types whose definition is part of the public headers of this version
    public = set()
    incdir = os.path.join(BUILD, lib, ver, "include")
    for h in os.listdir(incdir):
        txt = open(os.path.join(incdir, h), errors="replace").read()
        public |= set(re.findall(r"\b(?:struct|union|enum)\s+(\w+)\s*\{", txt))
        public |= set(re.findall(r"typedef\s+(?:struct|union|enum)\s*\{[^{}]*\}\s*(\w+)\s*;", txt))
    public.discard("internal_state")      # zlib.h's '{int dummy;}' placeholder for an opaque type
    m = abi.extract(os.path.join(libdir, sorted(so)[0]), prefix, public)
    json.dump(m, open(cf, "w"))
    return m


def versions(lib):
    d = os.path.join(BUILD, lib)
    if os.path.isdir(d):
        vs = [v for v in os.listdir(d) if os.path.exists(os.path.join(d, v, ".ok"))]
    else:   # quick check: no builds, use the shipped ABI models
        vs = [f[len(lib) + 1:-5] for f in os.listdir(CACHE) if f.startswith(lib + "-") and f.endswith(".json")]
    return sorted(vs, key=vkey)


# --------------------------------------------------------------------------- binary-level type compatibility
_RECPTR = re.compile(r"\b(struct|union) \w+\*")


def type_compat(a, b):
    if a == b:
        return True
    # a pointer to a record is just an address: the tag name (e.g. sqlite's internal
    # `struct Mem` vs the API's `struct sqlite3_value`) does not affect the ABI;
    # layout changes of public records are tracked as separate record elements
    if _RECPTR.sub(r"\1*", a) == _RECPTR.sub(r"\1*", b):
        return True
    # any data pointer is ABI-compatible with void* (e.g. zlib's gzFile: voidp -> struct gzFile_s*)
    if a.endswith("*") and b.endswith("*") and ("void*" in (a, b)):
        return True
    return False


def elem_def(m, e):
    """Definition of element e in model m, or None if absent."""
    k = e[0]
    if k in ("func", "var"):
        # Symbols with different version nodes are different symbols (paper, Sec. IV-A).
        # e = (kind, name, node). An unversioned reference binds to whatever the library
        # exports; a versioned one needs that node, unless the library defines no
        # version nodes at all (ld.so then only warns "no version information").
        d = m["funcs" if k == "func" else "vars"].get(e[1])
        if d is None or e[2] is None or not m["has_verdef"]:
            return d
        return d if e[2] in d.get("vers", []) else None
    if k == "record":
        r = m["records"].get(e[1])
        if r is None:
            return None
        for f in r["fields"]:
            if f[0] == e[2]:
                return {"type": f[1], "offset": f[2]}
        return None
    if k == "enum":
        en = m["enums"].get(e[1])
        if en is None or e[2] not in en:
            return None
        return {"value": en[e[2]]}


def symver_ok(ma, mb, da, db):
    """App linked against `a` references the symbol with a's default version node.
    glibc accepts the reference on `b` if b has no version definitions at all
    (only a 'no version information' warning) or b exports the same node."""
    if not ma["has_verdef"] or not mb["has_verdef"]:
        return True
    need = da.get("default")
    if need is None:
        return True
    if need not in mb["nodes"]:
        return False                      # "version `X' not found" (fatal, _dl_check_map_versions)
    # a versioned reference binds to the symbol's own node or to an unversioned (global) definition
    return need in db.get("vers", []) or not db.get("vers")


def bbc(lib, a, b, e, ma=None, mb=None):
    """Does element e break backward compatibility from version a to version b,
    i.e. would an application built against a and using e fail on b?"""
    ma = ma or model(lib, a)
    mb = mb or model(lib, b)
    da, db = elem_def(ma, e), elem_def(mb, e)
    if da is None:
        return False                      # app built against a cannot use e
    if db is None:
        return True                       # removed
    k = e[0]
    if k == "func":
        if da.get("nodebug") or db.get("nodebug"):
            return False
        if len(da["params"]) != len(db["params"]) or da["variadic"] != db["variadic"]:
            return True
        if any(not type_compat(x, y) for x, y in zip(da["params"], db["params"])):
            return True
        if da["ret"] != "void" and not type_compat(da["ret"], db["ret"]):
            return True                   # void -> non-void is backward compatible
        return False
    if k == "var":
        return not type_compat(da.get("type", "?"), db.get("type", "?"))
    if k == "record":
        return not type_compat(da["type"], db["type"]) or da["offset"] != db["offset"]
    if k == "enum":
        return da["value"] != db["value"]


def classify(lib, vo, vn, e, mo, mn):
    """Map an incompatible change to its Table II id."""
    do, dn = elem_def(mo, e), elem_def(mn, e)
    k = e[0]
    if k == "enum":
        return 1 if do is None else 2 if dn is None else 3
    if k == "record":
        if do is None:
            return 4
        if dn is None:
            return 5
        return 6 if do["type"] != dn["type"] else 7
    if k == "var":
        return 8 if do is None else 9 if dn is None else 10
    if do is None:
        return 11
    if dn is None:
        return 12
    if len(do["params"]) < len(dn["params"]):
        return 13
    if len(do["params"]) > len(dn["params"]):
        return 14
    if any(not type_compat(x, y) for x, y in zip(do["params"], dn["params"])):
        return 15
    if do["ret"] == "void":
        return 16
    if dn["ret"] == "void":
        return 17
    return 18


def elements(m):
    for kind, tab in (("func", m["funcs"]), ("var", m["vars"])):
        for name, d in tab.items():
            yield (kind, name, None)
            for node in d.get("vers", []):
                yield (kind, name, node)
    for r, d in m["records"].items():
        for f in d["fields"]:
            yield ("record", r, f[0])
    for en, mem in m["enums"].items():
        for x in mem:
            yield ("enum", en, x)


# --------------------------------------------------------------------------- step 1
@lru_cache(maxsize=None)
def collect_ics(lib):
    vs = versions(lib)
    ics = []
    for vo, vn in zip(vs, vs[1:]):
        mo, mn = model(lib, vo), model(lib, vn)
        if mo["soname"] != mn["soname"]:
            continue
        els = set(elements(mo)) | set(elements(mn))
        for e in sorted(els, key=lambda x: tuple("" if y is None else str(y) for y in x)):
            b = bbc(lib, vo, vn, e, mo, mn)        # BIC(vo, vn)
            f = bbc(lib, vn, vo, e, mn, mo)        # FIC(vo, vn) = BIC(vn, vo)
            if b or f:
                ics.append({"lib": lib, "old": vo, "new": vn, "elem": e,
                            "bic": b, "fic": f, "type": classify(lib, vo, vn, e, mo, mn)})
    return ics


# --------------------------------------------------------------------------- step 2
def usage_compat(lib, app, e, v):
    """Is the application's usage of e (compiled against app['build']) compatible
    with library version v?  Implements the 'DepOwl rules' column of Table II:
    the app view is the declaration it was compiled against; whether a changed
    return value / field / member matters depends on whether the app uses it."""
    mb, mv = model(lib, app["build"]), model(lib, v)
    db, dv = elem_def(mb, e), elem_def(mv, e)
    if db is None:
        return True
    if dv is None:
        return False
    if e[0] == "func":
        if db.get("nodebug") or dv.get("nodebug"):
            return True
        if len(db["params"]) != len(dv["params"]) or any(not type_compat(x, y) for x, y in zip(db["params"], dv["params"])):
            return False
        if not type_compat(db["ret"], dv["ret"]):
            if dv["ret"] == "void" or db["ret"] == "void":
                return e[1] not in app.get("ret_used", []) or db["ret"] == "void"   # rules 16/17
            return False                                                        # rule 18
        return True
    return not bbc(lib, app["build"], v, e, mb, mv)


def uses(app, e):
    if e[0] in ("func", "var"):
        return e[1] in app["undef_syms"] and app["undef_syms"][e[1]] == e[2]
    if e[0] == "record":
        return [e[1].split(" ", 1)[1], e[2]] in app.get("fields", []) or (e[1].split(" ", 1)[1], e[2]) in app.get("fields", [])
    if e[0] == "enum":
        return e[2] in app.get("enum_members", [])


def in_range(app, v):
    lo, hi = app.get("range", [None, None])
    return (lo is None or vkey(v) >= vkey(lo)) and (hi is None or vkey(v) <= vkey(hi))


def detect(lib, app, ic):
    """Filtering + detecting phase. Returns (v_old or -1, v_new or -1)."""
    e = ic["elem"]
    if not (in_range(app, ic["old"]) or in_range(app, ic["new"])):
        return -1, -1
    if not uses(app, e):
        return -1, -1
    if ic["type"] in (3, 7):              # enum value / field order: undeterminable from source
        return -1, -1
    co = usage_compat(lib, app, e, ic["old"])
    cn = usage_compat(lib, app, e, ic["new"])
    vold = ic["old"] if (not co and cn and in_range(app, ic["old"])) else -1
    vnew = ic["new"] if (not cn and co and in_range(app, ic["new"])) else -1
    return vold, vnew


# --------------------------------------------------------------------------- step 3
def suggest(lib, e, vbug, app):
    out = []
    for v in versions(lib):
        if model(lib, v)["soname"] != model(lib, vbug)["soname"]:
            continue
        isiv = (not bbc(lib, vbug, v, e)) and (not bbc(lib, v, vbug, e))   # Eq. 7
        if isiv and in_range(app, v):
            out.append(v)
    return out


def run(lib, app):
    """Algorithm 1 for one <lib, app> pair. Returns incompatible versions + evidence."""
    V, evidence = set(), []
    for ic in collect_ics(lib):
        vo, vn = detect(lib, app, ic)
        for vb in (vo, vn):
            if vb != -1:
                s = suggest(lib, ic["elem"], vb, app)
                V |= set(s)
                evidence.append({"ic": ic, "vbug": vb, "suggested": s})
    return sorted(V, key=vkey), evidence


def compress_ranges(lib, vs):
    """[1.2.0,1.2.0.1,...] -> '[1.2.0, 1.2.3]' style ranges over the built version list."""
    allv = versions(lib)
    idx = sorted(allv.index(v) for v in vs)
    out, start, prev = [], None, None
    for i in idx:
        if start is None:
            start = prev = i
        elif i == prev + 1:
            prev = i
        else:
            out.append((start, prev)); start = prev = i
    if start is not None:
        out.append((start, prev))
    fmt = lambda a, b: "[%s]" % allv[a] if a == b else "[%s, %s]" % (
        "Vinit" if a == 0 else allv[a], "Vlast" if b == len(allv) - 1 else allv[b])
    return " U ".join(fmt(a, b) for a, b in out)
