# universalWasmLoader-py

Universal WASM loader for Python — the Python port of
[universalWasmLoader-js](https://github.com/jrmarcum/universalWasmLoader-js). Loads and
instantiates WebAssembly modules and, when a companion `.wit` file is present, applies the
Canonical ABI so you call WIT exports with idiomatic Python values (`int`/`float`, `bool`,
`str`) instead of raw i32/pointer pairs.

- **PyPI package:** `universal-wasm-loader`
- **WASM runtime:** [`wasmtime`](https://pypi.org/project/wasmtime/) ≥ 26.0.0
- **License:** MIT

## Install

```sh
pip install universal-wasm-loader
```

## Usage

`wasm_import()` loads a `.wasm` module and hands you its exports as a dict of
**ready-to-call Python functions** — pull one out, bind it to a name, and call it
like any other function:

```python
import asyncio
from universal_wasm_loader import wasm_import

async def main():
    # Load the module. Exports come back as a dict of callables.
    exports = await wasm_import("./math.wasm")

    # Turn a WASM export into a Python function and call it.
    # (companion math.wit -> `calculate: func(a: s32, b: s32) -> s32`)
    calculate = exports["calculate"]
    print(calculate(1, 2))        # 3

asyncio.run(main())
```

When a companion `<name>.wit` sits next to the `.wasm`, the **Canonical ABI** is
applied automatically: kebab-case WIT names become camelCase keys, and arguments
and results are idiomatic Python values (`bool`, `str`) — no manual i32/pointer
handling:

```python
# strings_50.wasm + strings_50.wit -> greet, shout, str-len
exports = await wasm_import("./strings_50.wasm")

greet = exports["greet"]
print(greet("World"))             # "Hello, World!"   (str in, str out)
print(exports["strLen"]("hello")) # 5                 (WIT export `str-len`)
```

`create_singleton()` (one shared instance) and `InstancePool()` (N instances for
concurrent workloads) are also exported. See the
[project on GitHub](https://github.com/jrmarcum/universalWasmLoader-py) for the
full API, examples, and source.
