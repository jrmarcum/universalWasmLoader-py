(module
  (import "env" "env_mul" (func $env_mul (param f32 f32) (result f32)))
  (import "env" "env_add" (func $env_add (param i32 i32) (result i32)))
  (func (export "scale") (param f32 f32) (result f32)
    local.get 0
    local.get 1
    call $env_mul)
  (func (export "combine") (param i32 i32) (result i32)
    local.get 0
    local.get 1
    call $env_add)
)
