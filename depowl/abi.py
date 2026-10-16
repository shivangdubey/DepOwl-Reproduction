"""Step 0 of the simplified DepOwl: extract a binary-level ABI model from one
library build (shared object compiled with -g).

The model contains, for every exported symbol (optionally filtered by a name
prefix): its kind (FUNC/OBJECT), its symbol-version nodes, and its C-level
signature taken from DWARF (return type, parameter types, variable type).
It also records the layout of every struct/union and the members of every enum
reachable from those signatures. Types are rendered at binary level: typedefs
and cv-qualifiers are resolved away, so `uLong` and `unsigned long` compare
equal while `long` vs `int` do not.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "pyelftools"))
from elftools.elf.elffile import ELFFile
from elftools.elf.dynamic import DynamicSection

QUALS = {"DW_TAG_const_type", "DW_TAG_volatile_type", "DW_TAG_restrict_type",
         "DW_TAG_atomic_type"}
RECORDS = {"DW_TAG_structure_type": "struct", "DW_TAG_union_type": "union",
           "DW_TAG_class_type": "struct"}


def _name(die):
    a = die.attributes.get("DW_AT_name")
    return a.value.decode() if a else None


def _tgt(die):
    return die.get_DIE_from_attribute("DW_AT_type") if "DW_AT_type" in die.attributes else None


def decl_file(die):
    """Basename of the file a DIE was declared in (via the CU's line-program file table)."""
    a = die.attributes.get("DW_AT_decl_file")
    if a is None:
        return None
    lp = die.dwarfinfo.line_program_for_CU(die.cu)
    if lp is None:
        return None
    fe = lp["file_entry"]
    idx = a.value if lp.header["version"] >= 5 else a.value - 1
    if 0 <= idx < len(fe):
        return os.path.basename(fe[idx].name.decode())
    return None


class TypeRenderer:
    def __init__(self, public=None):
        self.public = public
        self.records = {}   # "struct NAME" -> {"size": n, "fields": [[name, type, offset]]}
        self.enums = {}     # "enum NAME" -> {member: value}
        self._pending = []

    def render(self, die, alias=None):
        if die is None:
            return "void"
        t = die.tag
        if t == "DW_TAG_base_type":
            return _name(die)
        if t in QUALS:
            return self.render(_tgt(die), alias)
        if t == "DW_TAG_typedef":
            return self.render(_tgt(die), alias=_name(die))
        if t in ("DW_TAG_pointer_type", "DW_TAG_reference_type", "DW_TAG_rvalue_reference_type"):
            return self.render(_tgt(die)) + "*"
        if t == "DW_TAG_array_type":
            n = ""
            for c in die.iter_children():
                if c.tag == "DW_TAG_subrange_type":
                    ub = c.attributes.get("DW_AT_upper_bound") or c.attributes.get("DW_AT_count")
                    n += "[%s]" % (ub.value + (1 if "DW_AT_upper_bound" in c.attributes else 0) if ub and isinstance(ub.value, int) else "")
            return self.render(_tgt(die)) + n
        if t in RECORDS:
            nm = _name(die) or alias or "anon"
            key = "%s %s" % (RECORDS[t], nm)
            if self.public is not None and nm not in self.public:
                return key                # opaque/internal type: layout is not part of the API
            if "DW_AT_declaration" not in die.attributes and key not in self.records:
                self.records[key] = None  # placeholder against recursion
                self._pending.append((key, die))
            return key
        if t == "DW_TAG_enumeration_type":
            nm = _name(die) or alias or "anon"
            key = "enum %s" % nm
            if self.public is not None and nm not in self.public:
                return key
            if key not in self.enums:
                self.enums[key] = {_name(c): c.attributes["DW_AT_const_value"].value
                                   for c in die.iter_children() if c.tag == "DW_TAG_enumerator"}
            return key
        if t == "DW_TAG_subroutine_type":
            ps = [self.render(_tgt(c)) for c in die.iter_children() if c.tag == "DW_TAG_formal_parameter"]
            return "fn(%s)->%s" % (",".join(ps), self.render(_tgt(die)))
        if t == "DW_TAG_unspecified_type":
            return _name(die) or "?"
        return t

    def flush(self):
        while self._pending:
            key, die = self._pending.pop()
            fields = []
            for c in die.iter_children():
                if c.tag != "DW_TAG_member":
                    continue
                off = c.attributes.get("DW_AT_data_member_location")
                off = off.value if off is not None and isinstance(off.value, int) else None
                fields.append([_name(c), self.render(_tgt(c)), off])
            sz = die.attributes.get("DW_AT_byte_size")
            self.records[key] = {"size": sz.value if sz else None, "fields": fields}


def dynsyms(elf):
    """Exported (defined) dynamic symbols -> {name: {"kind", "vers": [nodes], "default"}}."""
    dyn = elf.get_section_by_name(".dynsym")
    versym = elf.get_section_by_name(".gnu.version")
    verdef = elf.get_section_by_name(".gnu.version_d")
    ndx2name = {}
    if verdef:
        for vd, aux in verdef.iter_versions():
            ndx2name[vd["vd_ndx"]] = next(aux).name
    out = {}
    for i, s in enumerate(dyn.iter_symbols()):
        if s["st_shndx"] in ("SHN_UNDEF", "SHN_ABS") or s["st_info"]["bind"] not in ("STB_GLOBAL", "STB_WEAK"):
            continue
        if s["st_info"]["type"] not in ("STT_FUNC", "STT_OBJECT"):
            continue
        ver, hidden = None, False
        if versym:
            nd = versym.get_symbol(i)["ndx"]
            if isinstance(nd, int):
                hidden = bool(nd & 0x8000)
                ver = ndx2name.get(nd & 0x7FFF)
                if (nd & 0x7FFF) == 1:  # base version = soname
                    ver = None
        e = out.setdefault(s.name, {"kind": "FUNC" if s["st_info"]["type"] == "STT_FUNC" else "OBJECT",
                                    "vers": [], "default": None})
        if ver and ver not in e["vers"]:
            e["vers"].append(ver)
        if not hidden:
            e["default"] = ver
    has_verdef = verdef is not None
    return out, has_verdef, sorted(set(ndx2name.values()))


def extract(path, prefix=None, public=None):
    with open(path, "rb") as f:
        elf = ELFFile(f)
        soname = None
        for sec in elf.iter_sections():
            if isinstance(sec, DynamicSection):
                for tag in sec.iter_tags():
                    if tag.entry.d_tag == "DT_SONAME":
                        soname = tag.soname
        syms, has_verdef, nodes = dynsyms(elf)
        if prefix:
            syms = {k: v for k, v in syms.items() if k.startswith(prefix)}
        tr = TypeRenderer(public)
        sigs = {}
        dw = elf.get_dwarf_info()
        for cu in dw.iter_CUs():
            for die in cu.get_top_DIE().iter_children():
                if die.tag not in ("DW_TAG_subprogram", "DW_TAG_variable"):
                    continue
                if "DW_AT_declaration" in die.attributes:
                    continue
                nm = _name(die)
                if nm is None and "DW_AT_specification" in die.attributes:
                    nm = _name(die.get_DIE_from_attribute("DW_AT_specification"))
                if nm not in syms or nm in sigs:
                    continue
                if die.tag == "DW_TAG_subprogram":
                    spec = die.get_DIE_from_attribute("DW_AT_specification") if "DW_AT_specification" in die.attributes else die
                    params, variadic = [], False
                    for c in die.iter_children():
                        if c.tag == "DW_TAG_formal_parameter":
                            params.append(tr.render(_tgt(c)))
                        elif c.tag == "DW_TAG_unspecified_parameters":
                            variadic = True
                    sigs[nm] = {"ret": tr.render(_tgt(spec)), "params": params, "variadic": variadic}
                else:
                    sigs[nm] = {"type": tr.render(_tgt(die))}
        tr.flush()
    model = {"soname": soname, "has_verdef": has_verdef, "nodes": nodes, "funcs": {}, "vars": {},
             "records": {k: v for k, v in tr.records.items() if v is not None}, "enums": tr.enums}
    for nm, s in syms.items():
        d = dict(s)
        d.update(sigs.get(nm, {"nodebug": True}))
        (model["funcs"] if s["kind"] == "FUNC" else model["vars"])[nm] = d
    return model


if __name__ == "__main__":
    m = extract(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(m, indent=1)[:4000])
