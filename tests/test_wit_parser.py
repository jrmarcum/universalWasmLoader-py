from universal_wasm_loader._wit_parser import (
    kebab_to_camel,
    kebab_to_wasm_key,
    parse_wit,
    parse_wit_funcs,
    parse_wit_params,
    parse_wit_type,
)


def test_kebab_to_camel() -> None:
    assert kebab_to_camel("my-func") == "myFunc"
    assert kebab_to_camel("calculate") == "calculate"
    assert kebab_to_camel("is-positive") == "isPositive"
    assert kebab_to_camel("env-mul") == "envMul"


def test_kebab_to_wasm_key() -> None:
    assert kebab_to_wasm_key("my-func") == "my_func"
    assert kebab_to_wasm_key("env-add") == "env_add"
    assert kebab_to_wasm_key("calculate") == "calculate"


def test_parse_wit_type() -> None:
    for t in ("s32", "s64", "f32", "f64", "bool", "string"):
        assert parse_wit_type(t) == t
    assert parse_wit_type("unknown") == "s32"
    assert parse_wit_type("  f64  ") == "f64"


def test_parse_wit_params() -> None:
    result = parse_wit_params("a: s32, b: s32")
    assert result == [{"name": "a", "type": "s32"}, {"name": "b", "type": "s32"}]

    result = parse_wit_params("x: bool")
    assert result == [{"name": "x", "type": "bool"}]

    result = parse_wit_params("my-name: string")
    assert result == [{"name": "myName", "type": "string"}]

    assert parse_wit_params("") == []


def test_parse_wit_funcs_exports() -> None:
    body = """
    export calculate: func(a: s32, b: s32) -> s32;
    export is-positive: func(n: s32) -> bool;
    import callback: func(x: s32);
    """
    exports = parse_wit_funcs(body, "export")
    assert len(exports) == 2
    assert exports[0]["name"] == "calculate"
    assert exports[0]["camel_name"] == "calculate"
    assert exports[0]["wasm_key"] == "calculate"
    assert exports[0]["return_type"] == "s32"
    assert exports[1]["name"] == "is-positive"
    assert exports[1]["camel_name"] == "isPositive"
    assert exports[1]["wasm_key"] == "is_positive"
    assert exports[1]["return_type"] == "bool"


def test_parse_wit_funcs_imports() -> None:
    body = "import env-mul: func(a: f32, b: f32) -> f32;"
    imports = parse_wit_funcs(body, "import")
    assert len(imports) == 1
    assert imports[0]["name"] == "env-mul"
    assert imports[0]["camel_name"] == "envMul"
    assert imports[0]["wasm_key"] == "env_mul"
    assert imports[0]["return_type"] == "f32"


def test_parse_wit_funcs_no_return() -> None:
    body = "import log: func(msg: string);"
    imports = parse_wit_funcs(body, "import")
    assert imports[0]["return_type"] is None


def test_parse_wit_full() -> None:
    src = """
    package example:math@1.0.0;

    world math-world {
      export calculate: func(a: s32, b: s32) -> s32;
    }
    """
    result = parse_wit(src)
    assert result["package"] == "example:math@1.0.0"
    assert result["world"] == "math-world"
    assert len(result["exports"]) == 1
    assert result["exports"][0]["camel_name"] == "calculate"
    assert len(result["imports"]) == 0
