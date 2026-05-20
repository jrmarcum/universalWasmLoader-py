(module
  (global (export "version") i32 (i32.const 1))
  (func (export "calculate") (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add)
)
