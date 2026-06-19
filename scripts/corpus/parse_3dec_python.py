"""Parse 3DEC engine-specific Python SDK HTML docs into the corpus JSON layout.

Source: the local Sphinx Python API pages shipped with ITASCA Software 9.0 at
``<DOC>/common/docproject/source/manual/scripting/python/doc/itasca.<module>.html``.
These are the same pages docs.itascacg.com mirrors online, and the same format
the FLAC ``python_sdk_docs`` were derived from, so the output matches
``flac/python_sdk_docs/modules/zone/{module.json,Zone.json}`` field-for-field.

For each requested module (dotted, e.g. ``block`` or ``block.contact``):
  - ``itasca.<dotted>.html``         -> ``modules/<path>/module.json``  (functions)
  - ``itasca.<dotted>.<Class>.html`` -> ``modules/<path>/<Class>.json`` (methods)

Array modules (``blockarray``, ``block.contactarray``, ...) carry functions only,
no class. ``<path>`` is the dotted name with dots turned into directory separators
(matching how FLAC lays out ``interface.element`` under ``modules/interface/element``).

Module functions and class methods are both registered in the engine index's
``quick_ref`` as full dotted paths (``itasca.block.Block.area``), which is how the
loader/search consume them; the shared ``itasca`` core skeleton is preserved.

Usage:
    uv run python scripts/corpus/parse_3dec_python.py
"""

import html
import json
import re
from pathlib import Path
from typing import Any

DOC = Path("C:/Program Files/Itasca/ItascaSoftware900/exe64/doc/common/docproject/source/manual/scripting/python/doc")
RESOURCES = Path("C:/Dev/Han/pfc-mcp/src/itasca_mcp/knowledge/resources")
OUT_PY = RESOURCES / "3dec" / "python_sdk_docs"
SRC_BASE = "https://docs.itascacg.com/itasca900/common/docproject/source/manual/scripting/python/doc"

# 3DEC ``itasca.block`` family, confirmed against the running bridge namespace
# (dir(itasca.block)). Each entry is a dotted module name; class presence is
# detected from a sibling ``itasca.<dotted>.<Class>.html`` page.
BLOCK_FAMILY = [
    "block",
    "block.contact",
    "block.contactarray",
    "block.face",
    "block.facearray",
    "block.gridpoint",
    "block.gridpointarray",
    "block.subcontact",
    "block.subcontactarray",
    "block.zone",
    "block.zonearray",
    "blockarray",
]


def _text(fragment: str) -> str:
    """Strip tags and unescape entities from an HTML fragment."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _first_paragraph(html_text: str) -> str:
    """The first <p> following the <h1> (the module/class summary line)."""
    m = re.search(r"<h1>.*?</h1>\s*<p[^>]*>(.*?)</p>", html_text, re.S)
    return _norm(_text(m.group(1))) if m else ""


def _parse_param(raw: str) -> dict[str, Any]:
    """Parse one ``sig-param`` like ``point: vec3`` or ``search_start=None``."""
    p = _norm(raw)
    out: dict[str, Any] = {}
    default = None
    if "=" in p:
        left, default = p.split("=", 1)
        default = default.strip()
    else:
        left = p
    if ":" in left:
        name, typ = left.split(":", 1)
        out["name"] = name.strip()
        out["type"] = typ.strip()
    else:
        out["name"] = left.strip()
    out["required"] = default is None
    if default is not None:
        out["default"] = default
    return out


def _parse_sig_block(block: str) -> dict[str, Any] | None:
    """Parse one ``<dl class="py function|method">`` block into an entry dict."""
    dt = re.search(r"<dt[^>]*>(.*?)</dt>", block, re.S)
    if not dt:
        return None
    dt_inner = dt.group(1)

    name_m = re.search(r'sig-name descname">(.*?)</span>\s*<span class="sig-paren"', dt_inner, re.S)
    if not name_m:
        return None
    name = _text(name_m.group(1)).strip()

    params = [_parse_param(_text(p)) for p in re.findall(r'<em class="sig-param">(.*?)</em>', dt_inner, re.S)]
    params = [p for p in params if p.get("name")]

    full = _norm(_text(dt_inner)).replace("→", "->")
    # 3DEC's Sphinx return typehints carry a trailing period ("int.", "Block
    # object."); drop it so signatures/return types match the FLAC corpus style.
    if full.endswith("."):
        full = full[:-1].rstrip()
    ret = ""
    if "->" in full:
        ret = full.split("->", 1)[1].strip()

    dd = re.search(r"<dd[^>]*>(.*?)</dd>", block, re.S)
    description = _norm(_text(dd.group(1))) if dd else ""

    entry: dict[str, Any] = {"name": name}
    entry["_sig_text"] = full  # internal; callers rewrite into a final signature
    entry["description"] = description
    if params:
        entry["parameters"] = params
    if ret:
        entry["returns"] = {"type": ret}
    return entry


def _functions(html_text: str, module_path: str) -> list[dict[str, Any]]:
    """All module-level functions, signatures prefixed with ``itasca.<dotted>.``."""
    out = []
    for block in re.findall(r'<dl class="py function">.*?</dl>', html_text, re.S):
        entry = _parse_sig_block(block)
        if not entry:
            continue
        sig = entry.pop("_sig_text")
        # Module function dt text already carries the ``itasca.<dotted>.`` prefix.
        if not sig.startswith("itasca."):
            sig = f"itasca.{module_path}.{sig}"
        entry["signature"] = sig
        out.append(_ordered_func(entry))
    return out


def _methods(html_text: str, inst: str) -> list[dict[str, Any]]:
    """All class methods, signatures prefixed with the lowercase instance name."""
    out = []
    for block in re.findall(r'<dl class="py method">.*?</dl>', html_text, re.S):
        entry = _parse_sig_block(block)
        if not entry:
            continue
        sig = entry.pop("_sig_text")
        entry["signature"] = f"{inst}.{sig}"
        out.append(_ordered_func(entry))
    return out


def _ordered_func(entry: dict[str, Any]) -> dict[str, Any]:
    """Reorder keys to match the FLAC corpus: name, signature, description, ..."""
    ordered: dict[str, Any] = {"name": entry["name"], "signature": entry["signature"]}
    if entry.get("description"):
        ordered["description"] = entry["description"]
    if "parameters" in entry:
        ordered["parameters"] = entry["parameters"]
    if "returns" in entry:
        ordered["returns"] = entry["returns"]
    return ordered


def _group_key(name: str) -> str:
    """Semantic group: drop a leading ``set_``, then the prefix before ``_``."""
    n = name[4:] if name.startswith("set_") else name
    return n.split("_")[0]


def _method_groups(methods: list[dict[str, Any]]) -> dict[str, str]:
    groups: dict[str, list[str]] = {}
    for m in methods:
        groups.setdefault(_group_key(m["name"]), []).append(m["name"])
    return {k: ", ".join(sorted(v)) for k, v in sorted(groups.items())}


def main() -> None:
    index = json.loads((OUT_PY / "index.json").read_text(encoding="utf-8"))
    index["description"] = "3DEC Python SDK documentation index for quick lookup and LLM-assisted API discovery"
    modules = index.setdefault("modules", {})
    objects = index.setdefault("objects", {})
    quick_ref = index.setdefault("quick_ref", {})

    for dotted in BLOCK_FAMILY:
        mod_html = (DOC / f"itasca.{dotted}.html").read_text(encoding="utf-8")
        rel_dir = Path("modules") / dotted.replace(".", "/")
        out_dir = OUT_PY / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        mod_desc = _first_paragraph(mod_html)
        funcs = _functions(mod_html, dotted)
        module_doc = {
            "module": f"itasca.{dotted}",
            "description": mod_desc,
            "import_statement": "import itasca",
            "source_url": f"{SRC_BASE}/itasca.{dotted}.html",
            "functions": funcs,
        }
        (out_dir / "module.json").write_text(
            json.dumps(module_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        module_file = f"3dec/python_sdk_docs/{rel_dir.as_posix()}/module.json"
        modules[dotted] = {
            "description": mod_desc,
            "file": module_file,
            "functions": [f["name"] for f in funcs],
        }
        for f in funcs:
            quick_ref[f"itasca.{dotted}.{f['name']}"] = f"{module_file}#{f['name']}"

        # Class page: last dotted segment, capitalised (block.zone -> Zone).
        class_name = dotted.split(".")[-1].capitalize()
        class_path = DOC / f"itasca.{dotted}.{class_name}.html"
        if class_path.exists():
            cls_html = class_path.read_text(encoding="utf-8")
            methods = _methods(cls_html, class_name.lower())
            cls_desc = _first_paragraph(cls_html) or f"{class_name} object instance in itasca.{dotted}."
            class_doc = {
                "class": class_name,
                "description": cls_desc,
                "source_url": f"{SRC_BASE}/itasca.{dotted}.{class_name}.html",
                "note": f"Do not instantiate directly; use itasca.{dotted} module functions.",
                "method_groups": _method_groups(methods),
                "methods": methods,
            }
            (out_dir / f"{class_name}.json").write_text(
                json.dumps(class_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            class_file = f"3dec/python_sdk_docs/{rel_dir.as_posix()}/{class_name}.json"
            objects[class_name] = {
                "description": cls_desc,
                "file": class_file,
                "note": class_doc["note"],
                "method_groups": class_doc["method_groups"],
            }
            for m in methods:
                quick_ref[f"itasca.{dotted}.{class_name}.{m['name']}"] = f"{class_file}#{m['name']}"

            print(f"  {dotted:<26} {len(funcs):>3} funcs  +  {class_name} ({len(methods)} methods)")
        else:
            print(f"  {dotted:<26} {len(funcs):>3} funcs")

    # Stable ordering for a clean diff.
    index["modules"] = {k: modules[k] for k in sorted(modules)}
    index["objects"] = {k: objects[k] for k in sorted(objects)}
    index["quick_ref"] = {k: quick_ref[k] for k in sorted(quick_ref)}

    (OUT_PY / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT_PY / 'index.json'}")
    print(f"  modules: {len(index['modules'])}  objects: {len(index['objects'])}  quick_ref: {len(index['quick_ref'])}")


if __name__ == "__main__":
    main()
