# UWScript Compiler Internals

This page describes the code that `uwscript_compiler.py` generates and the VM behaviour it relies on. Read it if you want to read or hand-edit the generated assembly, extend the compiler, or load the output into the game. For the language itself see [uwscript-language-spec.md](uwscript-language-spec.md). For the opcodes see [../../docs/conversation_spec.txt](../../docs/conversation_spec.txt).

## Pipeline

1. **Lexer**: source text to tokens. Comments and line breaks are kept, because statements end at line breaks.
2. **Parser**: tokens to an AST. Blocks are parsed until their closing keyword, and a missing or stray `endif`/`endwhile`/`endfunction` is an error with the opening line.
3. **Collection pass**: registers functions, labels (per scope), globals and the locals of every function. It also infers which variables hold strings: from initializers, from `ask`, from the arguments at call sites, and from functions that return strings.
4. **Code generation**: the main program first, ending with `EXIT_OP`, then every function.
5. **Layout**: places the compiler's hidden slots after the globals and renders the assembly and the string block.

## Output files

`program.uws` compiles to:

- `program.asm`: the assembly. Its header comments list the strings, globals and function frames.
- `program_strings.txt`: the string block in the `strings.pak` dump format (`block: 0001; N strings.`, then `index: text`). Newlines and tabs are written as `\n` and `\t`.

Use `-o`/`-s` to choose other names, and `-b` for the string block id (default 1). The VM loads `<program>_strings.txt` next to the `.asm` by default.

## Memory layout

| Addresses | Contents |
|-----------|----------|
| 0–31 | imported game globals (`play_name`, `npc_attitude`, ...), set up by the VM |
| 32–95 | the conversation's private memory slots in the VM (not used by UWScript) |
| 96 … | **UWScript globals**, in declaration order (arrays are contiguous) |
| after the globals | hidden slots: main-program temporaries, then string snapshot slots |
| 4192 … | the stack (frames of called functions) |

Globals are addressed absolutely: `PUSHI 96` pushes the address of the first global, and `FETCHM`/`STO` read and write it. Because the VM starts the main program with the frame pointer at 96, the addresses equal `BP + offset` in the main program. They stay valid inside functions, where `BP` points to the function's frame. Globals and hidden slots together may use up to 4096 words; the compiler reports an error if a program needs more.

## Functions

### Call sequence

```
; caller                         ; callee
<push arg1>                      fn_name:
<push arg2>                      PUSHBP            ; save caller's frame pointer
CALL fn_name                     SPTOBP            ; new frame
POP                              PUSHI <n>         ; reserve n words for locals and temporaries
POP                              ADDSP
PUSH_REG     ; only if used      ...
                                 <push result>     ; 0 if there is no return value
                                 SAVE_REG          ; result -> result register
                                 BPTOSP            ; drop the frame
                                 POPBP
                                 RET
```

- Every function sets up a frame, including functions without parameters, so locals never overlap with globals.
- The caller pops its arguments. The result travels in the result register, and the caller pushes it with `PUSH_REG` only when the call is part of an expression. A call used as a statement leaves the stack unchanged.
- The frame size `<n>` is the number of locals plus the deepest temporary use in the function. It is computed after the body is generated.

### Frame offsets

For a function with `N` parameters:

| Offset (`PUSHI_EFF`) | Contents |
|----------------------|----------|
| `-(N + 1)` … `-2` | parameters 1 … N (the first parameter has the most negative offset) |
| (BP − 2, BP − 1) | return address, saved frame pointer |
| `0` … | locals in declaration order, then temporaries |

The VM resolves a negative operand `k` of `PUSHI_EFF` to `BP + k - 1` (it skips the saved frame pointer, as in the original engine's code), so parameter 1 of 2 is `PUSHI_EFF -3`, which is `BP - 4`.

## Imported functions (CALLI)

Built-in functions follow the original engine's convention from `conversation_spec.txt` §7.6:

```
; set_quest(7, 3) in UWScript; the engine's order is (value, quest)
PUSHI <addr of quest>     ; last engine argument first
PUSHI <addr of value>     ; arg1 ends up right below the count
PUSHI 2                   ; argument count, pushed last
CALLI 16
POP                       ; the caller removes count and arguments
POP
POP
PUSH_REG                  ; only if the result is used
```

- Arguments are passed **by reference**. A plain variable is passed by its own address; any other expression is first stored in a temporary slot. Arrays are passed as the address of their first element.
- `set_quest(quest, value)` is reordered to the engine's `(value, quest)`.
- The fantasy console functions (IDs 100 and up) take their arguments in source order, and arrays go through a temporary that holds the array's address (`draw_sprite`). This matches what `fantasy_console.py` reads.
- `menu` passes a 0-terminated array of string ids to `babl_menu` (ID 0). `filtermenu` passes the strings and a 0/1 flag array to `babl_fmenu` (ID 1). `ask` calls `babl_ask` (ID 3) with no arguments.
- Temporaries come from a stack-like pool per scope: frame slots inside functions, hidden globals in the main program. They are freed after each call, so nested calls never share a slot while it is live.

## Text substitution

The game expands codes in a string when it shows it:

| Code | Value shown |
|------|-------------|
| `@GI<addr>` / `@GS<addr>` | integer / string id at absolute address `addr` |
| `@SI<n>` / `@SS<n>` | integer / string id at `BP + n` (no `-1` adjustment, unlike `PUSHI_EFF`) |

For `"text" + x + ...`, the compiler adds a new string such as `You have @GI97 gold left.`. It never rewrites an existing literal, so the same literal can still be used on its own. Each part of the template is handled like this:

- Literal text, numbers and booleans are written into the template directly.
- In `say` and menu options, a plain variable is referenced in place: `@GI`/`@GS` for globals, `@SI`/`@SS` for locals and parameters (a parameter at `PUSHI_EFF k` becomes `@S?(k-1)`).
- Anything else (expressions, array elements, call results, and all values when the string is stored) is evaluated into its own hidden global *snapshot slot* and referenced with `@GI`/`@GS`. Stored strings therefore keep their values and stay valid after the function that built them returns.
- `@?S` parts that point at another template are expanded again by the VM, up to 8 levels.
- A join that reads its own target (`s += "x"`, `s = s + "x"`, `a[i] += "x"`) or a recursive call of the current function would make the template refer to itself the next time the line runs. For those, the compiler calls imported function **600** (`freeze_string`, a UWScript VM extension) on the template. The VM expands the template immediately and returns the id of a new string holding the text. The compiler warns when it does this.

String id 0 is reserved and empty, because 0 terminates menu option lists. Real strings start at id 1.

## Example

```uwscript
let gold = 50
function pay(amount)
    let left = gold - amount
    gold = left
    return left
endfunction
let rest = pay(20)
say "You have " + rest + " gold left."
```

compiles to (header shortened):

```
; 1: "You have @GI97 gold left."
;   gold -> 96 (int)
;   rest -> 97 (int)
;   pay(amount): 1 frame slot(s)
;     amount -> -2 (param, int)
;     left -> 0 (local, int)

START
PUSHI 96        ; gold = 50
PUSHI 50
STO
PUSHI 97        ; rest = pay(20)
PUSHI 20
CALL fn_pay
POP
PUSH_REG
STO
PUSHI 1         ; say string 1
SAY_OP
EXIT_OP

; function pay(amount)
fn_pay:
PUSHBP
SPTOBP
PUSHI 1
ADDSP
PUSHI_EFF 0     ; left = gold - amount
PUSHI 96
FETCHM
PUSHI_EFF -2
FETCHM
OPSUB
STO
PUSHI 96        ; gold = left
PUSHI_EFF 0
FETCHM
STO
PUSHI_EFF 0     ; return left
FETCHM
SAVE_REG
BPTOSP
POPBP
RET
```

(The `; ...` notes after instructions were added for this page. The compiler only writes comments on their own lines.)

## Labels

| Label | Used for |
|-------|----------|
| `fn_<name>` | function entry points |
| `lbl_<name>` | user labels in the main program |
| `fn_<function>.<name>` | user labels inside a function (labels are per scope) |
| `L<n>_<kind>` | generated jump targets (`if`, `while`) |

The prefixes, and the `.` that identifiers cannot contain, keep labels of different scopes, functions and generated labels from clashing.

## The VM (`uwscript_vm.py`)

The VM runs the assembly in the terminal and is the base of the fantasy console. Its behaviour that matters for UWScript:

- `CALLI` restores the stack pointer after the handler runs and pushes nothing, matching the engine's stack effect. The handlers read their arguments with `pop_args()`/`arg_values()`, which return them in engine order (arg1 first).
- `get_quest` returns 0 for flags that are not set (preset them with `--quest ID=VALUE`). `set_quest` stores the value.
- Menus and `ask` read from stdin. When the input ends, the conversation ends cleanly.
- Arithmetic is signed 16-bit: `OPADD`, `OPSUB`, `OPMUL`, `OPDIV`, `OPMOD`, `OPNEG` and `PUSHI` wrap their results, division truncates toward zero, and memory addresses wrap at 65536.
- It stops with an error message and exit code 1 on unknown instructions or labels and on stack overflow/underflow.
- `python uwscript_vm.py program.uws` compiles in memory and runs the program, and `--debug` traces every instruction.

## Using the output in the game

The opcodes, the imported-function calling convention and the substitution codes follow `conversation_spec.txt`. Two parts are specific to this toolchain and were only tested in the VM:

- Globals at absolute address 96 and up. The game reserves a fixed number of memory slots per conversation, given in the conversation header; `tools/conversations/uw_cnv_compiler.py` reads it from a `; Memory Slots:` header comment, which the UWScript compiler does not write.
- Nested string templates (a joined string inside another joined string).
- Imported function 600 (`freeze_string`), which the compiler only emits for strings built from themselves and always reports with a warning.
