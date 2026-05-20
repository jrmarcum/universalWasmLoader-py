from __future__ import annotations

import re

_PRIMITIVE_TYPES = frozenset({"s32", "s64", "f32", "f64", "bool", "string"})


def kebab_to_camel(name: str) -> str:
    parts = name.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def kebab_to_wasm_key(name: str) -> str:
    return name.replace("-", "_")


def parse_wit_type(raw: str) -> str:
    t = raw.strip()
    return t if t in _PRIMITIVE_TYPES else "s32"


def parse_wit_params(raw: str) -> list[dict[str, str]]:
    if not raw.strip():
        return []
    result: list[dict[str, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        name_raw, type_raw = part.split(":", 1)
        result.append({"name": kebab_to_camel(name_raw.strip()), "type": parse_wit_type(type_raw)})
    return result


def parse_wit_funcs(body: str, keyword: str) -> list[dict]:  # type: ignore[type-arg]
    pattern = re.compile(
        rf"\b{keyword}\s+([\w-]+)\s*:\s*func\s*\(([^)]*)\)\s*(?:->\s*([\w-]+))?",
        re.MULTILINE,
    )
    funcs: list[dict] = []  # type: ignore[type-arg]
    for m in pattern.finditer(body):
        name = m.group(1)
        funcs.append(
            {
                "name": name,
                "camel_name": kebab_to_camel(name),
                "wasm_key": kebab_to_wasm_key(name),
                "params": parse_wit_params(m.group(2) or ""),
                "return_type": parse_wit_type(m.group(3)) if m.group(3) else None,
            }
        )
    return funcs


def parse_wit(src: str) -> dict:  # type: ignore[type-arg]
    pkg_match = re.search(r"package\s+([\w:@.\-/]+)\s*;", src)
    world_match = re.search(r"world\s+([\w-]+)\s*\{([^}]*)\}", src, re.DOTALL)
    body = world_match.group(2) if world_match else src
    return {
        "package": pkg_match.group(1) if pkg_match else "",
        "world": world_match.group(1) if world_match else "",
        "imports": parse_wit_funcs(body, "import"),
        "exports": parse_wit_funcs(body, "export"),
    }
