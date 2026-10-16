"""Application side: build the app (a C snippet reproducing the issue's library
usage) against one library version and extract what DepOwl needs:
  * undefined dynamic symbols the binary references (filtering phase, readelf)
  * usage facts from the source (detecting phase): which library functions'
    return values are used, which struct fields / enum members are referenced.
The source facts come from clang's JSON AST, standing in for srcML.
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "pyelftools"))
from elftools.elf.elffile import ELFFile

BUILD = os.path.join(ROOT, "build")
LINK = {"zlib": "z", "expat": "expat", "sqlite": "sqlite3", "curl": "curl"}


def compile_app(lib, ver, src, out, extra=()):
    inc, libdir = os.path.join(BUILD, lib, ver, "include"), os.path.join(BUILD, lib, ver, "lib")
    cmd = ["gcc", "-g", "-O0", "-w", "-I", inc, src, "-o", out, "-L", libdir, "-l" + LINK[lib], *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def undef_syms(binary):
    with open(binary, "rb") as f:
        elf = ELFFile(f)
        dyn = elf.get_section_by_name(".dynsym")
        verneed = elf.get_section_by_name(".gnu.version_r")
        versym = elf.get_section_by_name(".gnu.version")
        ndx = {}
        if verneed:
            for vn, aux in verneed.iter_versions():
                for a in aux:
                    ndx[a["vna_other"]] = (vn.name, a.name)
        out = {}
        for i, s in enumerate(dyn.iter_symbols()):
            if s["st_shndx"] == "SHN_UNDEF" and s.name:
                v = None
                if versym:
                    n = versym.get_symbol(i)["ndx"]
                    v = ndx.get(n if isinstance(n, int) else -1)
                out[s.name] = v[1] if v else None
        return out


def ast_facts(lib, ver, src):
    inc = os.path.join(BUILD, lib, ver, "include")
    r = subprocess.run(["clang", "-fsyntax-only", "-w", "-Xclang", "-ast-dump=json", "-I", inc, src],
                       capture_output=True, text=True)
    ast = json.loads(r.stdout)
    ret_used, fields, enums, called = set(), set(), set(), set()

    def callee_name(call):
        for c in call.get("inner", [])[:1]:
            stack = [c]
            while stack:
                n = stack.pop()
                if n.get("kind") == "DeclRefExpr" and n.get("referencedDecl", {}).get("kind") == "FunctionDecl":
                    return n["referencedDecl"]["name"]
                stack.extend(n.get("inner", []))

    def walk(n, parent_kind):
        k = n.get("kind")
        if k == "CallExpr":
            nm = callee_name(n)
            if nm:
                called.add(nm)
                if parent_kind not in ("CompoundStmt", None) and not (
                        parent_kind == "CStyleCastExpr" and n.get("type", {}).get("qualType") == "void"):
                    ret_used.add(nm)
        if k == "MemberExpr":
            base_t = ""
            for c in n.get("inner", []):
                base_t = c.get("type", {}).get("desugaredQualType") or c.get("type", {}).get("qualType", "")
            rec = base_t.replace("struct ", "").replace("*", "").replace("const", "").strip()
            fields.add((rec, n.get("name")))
        if k == "DeclRefExpr" and n.get("referencedDecl", {}).get("kind") == "EnumConstantDecl":
            enums.add(n["referencedDecl"]["name"])
        for c in n.get("inner", []):
            walk(c, k)

    for top in ast.get("inner", []):
        if top.get("kind") == "FunctionDecl" and not top.get("isImplicit") and "loc" in top and \
                top.get("loc", {}).get("file", src) == src or top.get("loc", {}).get("includedFrom") is None:
            for c in top.get("inner", []):
                walk(c, top.get("kind"))
    return {"ret_used": sorted(ret_used), "fields": sorted(fields), "enum_members": sorted(enums),
            "called": sorted(called)}


def analyze(lib, build_ver, src, workdir, extra=()):
    os.makedirs(workdir, exist_ok=True)
    out = os.path.join(workdir, "app-built-vs-%s" % build_ver)
    rc, log = compile_app(lib, build_ver, src, out, extra)
    if rc != 0:
        raise RuntimeError("app does not build against %s %s:\n%s" % (lib, build_ver, log))
    facts = ast_facts(lib, build_ver, src)
    facts["undef_syms"] = undef_syms(out)
    facts["build"] = build_ver
    facts["binary"] = out
    return facts
