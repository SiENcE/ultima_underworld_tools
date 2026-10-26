# UWScript Compiler Internals

This page describes the code that `uwscript_compiler.py` generates, the engine rules it follows, and the shared VM that runs it. Read it if you want to read or hand-edit the generated assembly, extend the compiler, or put a conversation into the game. For the language itself see [uwscript-language-spec.md](uwscript-language-spec.md).

## Sources for the engine rules

- [docs/conversation_spec.txt](../../docs/conversation_spec.txt): the file format, opcodes, imported functions and text substitution.
- [Underworld Adventures](https://github.com/vividos/UnderworldAdventures), an engine that runs the original conversations. Its `conv/CodeVM.cpp` and `conv/CodeGraph.cpp` settle what the spec leaves open: the stack and frame layout, branch offsets, the `CALL`/`RET` addresses and how imported functions read their arguments.

The facts the compiler, the VM and the tests share are in [`uw_engine.py`](../uw_engine.py): the opcodes, the UW1 imported functions with their IDs and return types, and the game globals.

## Pipeline

1. **Lexer**: source text to tokens. Line breaks are kept, because statements end at them.
2. **Parser**: tokens to an AST. Blocks are parsed until their closing keyword, and a missing or stray `endif`/`endwhile`/`endfunction` is an error with the opening line.
3. **Collection pass**: registers functions, labels (per scope), globals and the locals of every function. It also infers which variables hold strings.
4. **Code generation**: the main program first (ending with `EXIT_OP`), then every function. It records which imported functions and game globals are used.
5. **Layout**: places the hidden slots after the globals, then writes the header (memory slots, import table, strings) and the code.

## Output files

`program.uws` compiles to:

- `program.asm`: the assembly. Its header has what the game tools need (`; String Block:`, `; Memory Slots:`, `; Imported Functions/Variables:`) followed by the strings, globals and function frames.
- `program_strings.txt`: the string block in the `strings.pak` dump format (`block: 0001; N strings.`, then `index: text`).

From there, `tools/conversations/uw_cnv_compiler.py` builds the game's binary format and can write it into a slot of `CNV.ARK` (see [Putting a conversation into the game](#putting-a-conversation-into-the-game)).

## Memory layout

| Addresses | Contents |
|-----------|----------|
| 0–30 | game globals (`play_name`, `npc_attitude`, ...). The import table says where each one goes; the game copies the values in when the conversation starts and back when it ends. |
| 31 | unused |
| 32 … | **UWScript globals** in declaration order (arrays are contiguous), then hidden slots: main-program temporaries and string snapshot slots |
| `Memory Slots` … | the stack, growing upwards |

`; Memory Slots: N` is the end of the globals, and the stack starts right after it. Everything below `N` is the conversation's private memory: the game saves it when the conversation ends and restores it the next time. `let name` without a value declares a global that is not initialised, so it keeps its saved value (see [Saved globals](#saved-globals)).

Globals are addressed absolutely (`PUSHI 32` is the address of the first global), so they work the same in the main program and in functions. The limit is 0x8000 words.

## Functions

### Call sequence

```
; caller                         ; callee
<push arg1>                      fn_name:
<push arg2>                      PUSHBP            ; save caller's frame pointer
CALL fn_name                     SPTOBP            ; BP now points at the saved frame pointer
POP                              PUSHI <n>         ; reserve n words for locals and temporaries
POP                              ADDSP
PUSH_REG     ; only if used      ...
                                 <push result>     ; 0 if there is no return value
                                 SAVE_REG          ; result -> result register
                                 BPTOSP            ; drop the frame
                                 POPBP
                                 RET
```

- Every function sets up a frame, including functions without parameters.
- The caller pops its arguments. The result travels in the result register, and the caller pushes it with `PUSH_REG` only when the call is part of an expression.
- Arguments of UWScript functions are passed by value; arrays are passed as their address.

### Frame offsets

The stack pointer points at the top value (a push increments it first). After `SPTOBP`, BP points at the saved frame pointer, and `PUSHI_EFF k` pushes the address BP + k. For a function with `N` parameters:

| `PUSHI_EFF` | Contents |
|-------------|----------|
| `-(N + 1)` … `-2` | parameters 1 … N (the first parameter has the most negative offset) |
| `-1` | return address |
| `0` | saved frame pointer |
| `1` … | locals in declaration order, then temporaries |

`CALL` pushes the address of its own operand word, and `RET` continues after it. `ADDSP n` reserves exactly n words; the game fills them with garbage, so the compiler always initialises locals.

### Branches and jumps

`JMP` and `CALL` take absolute word addresses. `BEQ`, `BNE` and `BRA` are relative to their operand word: target = address of the instruction + 1 + offset. The assembler and the VM compute offsets this way from labels.

| Label | Used for |
|-------|----------|
| `fn_<name>` | function entry points |
| `lbl_<name>` | user labels in the main program |
| `fn_<function>.<name>` | user labels inside a function (labels are per scope) |
| `L<n>_<kind>` | generated jump targets (`if`, `while`) |

## Imported functions (CALLI)

```
; set_quest(7, 3) in UWScript; the engine's order is (value, quest)
PUSHI <addr of quest>     ; last engine argument first
PUSHI <addr of value>     ; arg1 ends up right below the count
PUSHI 2                   ; argument count, on top
CALLI 16                  ; the ID from the import table
POP                       ; the caller removes count and arguments
POP
POP
PUSH_REG                  ; only if the result is used
```

- The function reads the count on top of the stack and the argument pointers below it, and leaves them there.
- Arguments are passed **by reference**. A plain variable is passed by its own address; any other expression is first stored in a temporary slot. Arrays are passed as the address of their first element.
- `set_quest(quest, value)` is reordered to the engine's `(value, quest)`. Every other function takes its arguments in the engine's order.
- Each function used is listed in the import table with its UW1 ID, name and return type: `; Import 0: Function babl_menu, ID: 0, Returns: int`. The game calls imported functions **by name**, so the name must match. `string_length` is imported as `length`.
- `menu` passes a 0-terminated array of string ids to `babl_menu`, `filtermenu` passes the strings and a 0/1 flag array to `babl_fmenu`, and `ask` calls `babl_ask` with no arguments.
- Fantasy console functions (IDs 100 and up, imported as `console_<name>`) take their arguments in source order, matching what `fantasy_console.py` reads. Like `freeze_string` (600), they are only allowed with `--target console`.

## Game globals

Using a game global like `play_name` adds an import record `; Import 3: Variable play_name, Addr: 0x0008`, and the code reads and writes address 8 like any global. The game looks the value up by name, puts it at that address when the conversation starts, and copies it back when the conversation ends, so `npc_attitude = 0` changes the NPC. `play_name` and `npc_name` hold string ids.

## Saved globals

The game keeps a conversation's private memory between talks. `babglobals.dat` gives the size for each conversation slot, and `bglobals.dat` in a saved game holds the values. A UWScript global keeps its value between talks if it is declared without a value (`let visits`), and if the slot's size in `babglobals.dat` covers its address. Globals declared with a value (`let x = 0`) are set again every time.

## Text substitution

The game expands codes in a string when it shows it:

| Code | Value shown |
|------|-------------|
| `@GI<addr>` / `@GS<addr>` | integer / string id at absolute address `addr` |
| `@SI<n>` / `@SS<n>` | integer / string id at BP + n (the same offsets as `PUSHI_EFF`) |

For `"text" + x + ...`, the compiler adds a new string such as `You have @GI33 gold left, @GS8.` and never rewrites an existing literal. Each part of the template is handled like this:

- Literal text, numbers and booleans are written into the template directly.
- In `say` and menu options, a plain variable is referenced in place.
- Anything else, and all values in strings that are stored, is evaluated into its own hidden global *snapshot slot* and referenced with `@GI`/`@GS`. Stored strings therefore keep their values and stay valid after the function that built them returns.
- A join that reads its own target (`s += "x"`) would make the template refer to itself the next time the line runs. For the game, the compiler refuses such a line if it can run again. With `--target console`, it calls `freeze_string` (600), which expands the template into a new string.

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
say "You have " + rest + " gold left, " + play_name + "."
```

compiles to (the strings and globals lists are shortened):

```
; String Block: 1
; Memory Slots: 34
; Imported Functions/Variables:
; Import 0: Variable play_name, Addr: 0x0008
; 1: "You have @GI33 gold left, @GS8."

START
PUSHI 32        ; gold = 50
PUSHI 50
STO
PUSHI 33        ; rest = pay(20)
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
PUSHI 1         ; one local
ADDSP
PUSHI_EFF 1     ; left = gold - amount
PUSHI 32
FETCHM
PUSHI_EFF -2
FETCHM
OPSUB
STO
PUSHI 32        ; gold = left
PUSHI_EFF 1
FETCHM
STO
PUSHI_EFF 1     ; return left
FETCHM
SAVE_REG
BPTOSP
POPBP
RET
```

(The `; ...` notes after instructions were added for this page; the compiler only writes comments on their own lines.)

## The shared VM

`uwscript_vm.py` is the one conversation VM in the repository:

- `python uwscript_vm.py program.uws|program.asm` runs UWScript programs.
- `tools/conversations/uw_cnv_runner.py` is a thin wrapper around it, for conversations decompiled from the game.
- `fantasy_console/fantasy_console.py` subclasses it and adds the graphics, sound and input functions.

It follows the engine rules above:
- It reads `; Memory Slots:` and the import table, places game globals at their import addresses, and calls imported functions by name. For hand-written assembly without an import table, it falls back to the standard UW1 IDs.
- Arithmetic is signed 16-bit and division truncates.
- `--set NAME=VALUE`, `--quest ID=VALUE` and `--item ID` set up the game state. `--globals FILE` saves the private globals, game globals and quest flags at the end and loads them at the start, so you can replay a second or third talk.
- It stops with an error and exit code 1 on unknown instructions or labels and on stack overflow or underflow.

Where it deliberately differs from Underworld Adventures:
- `RET` at the outermost level ends the conversation. CodeVM's check reads inverted: it ends the conversation when a function returns.
- Comparisons and division treat words as signed. CodeVM uses unsigned words; what the original game does is not documented.

The barter, inventory and world functions only print what they would do and return plausible values.

## Putting a conversation into the game

```bash
python uwscript/uwscript_compiler.py npc.uws                        # npc.asm + npc_strings.txt
python tools/conversations/uw_cnv_compiler.py npc.asm -o npc.bin    # game binary format
python tools/conversations/uw_cnv_decompiler.py npc.bin --decompile-binary   # check it
```

The `.asm` needs a `; Slot: XXXX` header line (the conversation slot, in hex) before `uw_cnv_compiler.py --update-cnv CNV.ARK` can write it into the game. The strings have to go into the game's string block with the `tools/strings` tools, using the block named in `; String Block:`.

The tests check the path as far as possible without the game. Every sample is compiled, assembled into a binary with the repo's assembler, and run on a reference interpreter transcribed from CodeVM; the result must match the VM. The test suite also decompiles a binary and runs it again. The conversations have not been run inside the original game yet.
