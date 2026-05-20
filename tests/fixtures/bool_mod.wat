(module
  (func (export "is_positive") (param i32) (result i32)
    local.get 0
    i32.const 0
    i32.gt_s)
  (func (export "is_even") (param i32) (result i32)
    local.get 0
    i32.const 2
    i32.rem_s
    i32.eqz)
)
