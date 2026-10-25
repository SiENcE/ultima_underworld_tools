# UWScript

UWScript is a small, readable language for writing Ultima Underworld conversations. The compiler turns it into the game's conversation assembly plus a string block, and the VM runs the result in your terminal. The same toolchain drives the [fantasy console](../fantasy_console/README.md).

```uwscript
let visits = get_quest(10)

if visits == 0
    say "Welcome, stranger. I am the Gray Goblin."
else
    say "Back again? That makes " + (visits + 1) + " visits."
endif
set_quest(10, visits + 1)

menu choice ["Who are you?", "Goodbye"]
if choice == 1
    say "A collector of ancient artifacts."
endif
```

## Quick start

Requires Python 3.6+ and only the standard library.

```bash
cd uwscript

# Compile: writes samples/conversation_gray_goblin.asm and samples/conversation_gray_goblin_strings.txt
python uwscript_compiler.py samples/conversation_gray_goblin.uws

# Run the compiled conversation (finds <name>_strings.txt next to the .asm)
python uwscript_vm.py samples/conversation_gray_goblin.asm

# Or compile and run in one step
python uwscript_vm.py samples/conversation_gray_goblin.uws
```

### Compiler options

```
python uwscript_compiler.py program.uws [-o program.asm] [-s program_strings.txt] [-b 1] [-v] [--debug]
```

| Option | Default | Meaning |
|--------|---------|---------|
| `-o`, `--output` | `<input>.asm` | assembly file; `-` writes it to stdout |
| `-s`, `--strings` | `<output>_strings.txt` | string block file |
| `-b`, `--block` | `1` | string block id |
| `-v`, `--verbose` | | print the files written |
| `--debug` | | parser debug output and a traceback on errors |

Errors are printed as `program.uws: error: Line 12, column 5: ...` and the exit code is 1. Warnings (`program.uws: warning: ...`) don't stop the compilation.

### VM options

```
python uwscript_vm.py program.asm|program.uws [--strings FILE] [--quest ID=VALUE ...] [--debug]
```

Menus and `ask` read from stdin, so you can script a run with `printf '1\n2\n' | python uwscript_vm.py ...`. `get_quest` returns 0 unless the program set the flag or you preset it with `--quest 5=1`. On runtime errors (stack overflow, unknown instructions) the VM stops with a message and exit code 1. Numbers are signed 16-bit, as in the game.

## Folder contents

```
uwscript/
  uwscript_compiler.py     UWScript -> UW assembly + string block
  uwscript_vm.py           conversation VM (also the base of the fantasy console)
  test_uwscript.py         tests: python -m unittest test_uwscript
  samples/                 example programs (see below)
  docs/
    uwscript-language-spec.md   the language reference
    compiler-internals.md       generated code, memory layout, calling convention
    UWScript_udl.xml            Notepad++ syntax highlighting for .uws files
```

`uwscript_vm.py` is the VM that matches the compiler's output. It differs from `../tools/conversations/uw_cnv_runner.py`, which is meant for conversations decompiled from the game.

## Language at a glance

The full reference is [docs/uwscript-language-spec.md](docs/uwscript-language-spec.md).

| Feature | Syntax |
|---------|--------|
| Variables | `let gold = 100`, `gold -= 10` (`+= -= *= /= %=`) |
| Conditions | `if ... elseif ... else ... endif` with `== != < > <= >=`, `and`, `or`, `not`/`!` |
| Loops and jumps | `while ... endwhile`, `label name`, `goto name`, `exit` |
| Functions | `function name(a, b) ... return value ... endfunction`; recursion works, globals are visible |
| Arrays | `let items = ["sword", "map"]`, `let grid = [[1, 0], [0, 1]]`, `items[1] = "torch"`, `grid[r][c]`; arrays are passed to functions by address |
| Strings | `"Hello " + name + ", you have " + gold + " gold"`; `==` on strings compares the text |
| Dialogue | `say`, `ask name`, `menu choice [...]`, `filtermenu choice ["text", condition, ...]` |
| Game functions | `random`, `get_quest`, `set_quest`, `compare`, `contains`, `string_length`, `gronk_door` |
| Fantasy console | `clear_screen`, `draw_sprite`, `print`, `flip_display`, `is_key_pressed`, `play_tone`, ... |

### Things to know

- Variables are scoped per function, not per block. Everything declared in the main program is a global.
- Joined strings become text-substitution templates. A stored string (`let msg = "HP: " + hp`) keeps the values it had when it was built. Building a string from itself (`s += "x"`) works in the UWScript VM, and the compiler warns that the game itself cannot do it.
- Array sizes are fixed, constant indexes are checked when compiling, and computed indexes are not checked at runtime.
- `and`/`or` evaluate both sides.

## Samples

| Sample | Shows |
|--------|-------|
| `basics_hello.uws` | variables, if/else |
| `basics_arithmetic.uws` | arithmetic and compound assignment |
| `basics_comparisons.uws` | comparison operators |
| `basics_if_elseif_else.uws` | if/elseif/else and nesting |
| `basics_while_loops.uws`, `basics_while_nested.uws` | while loops, nested loops, combined conditions |
| `strings_substitution.uws`, `strings_countdown.uws` | values inside text |
| `strings_concatenation.uws` | chained joins, stored strings, `ask`, string comparison |
| `arrays_access.uws` | reading array elements |
| `arrays_multidimensional.uws` | 2D arrays, string arrays, arrays as parameters |
| `functions_basic.uws` | a function with a local variable |
| `functions_parameters.uws` | parameters, return values, recursion, globals |
| `dialogue_menu.uws` | a one-line menu |
| `conversation_gray_goblin.uws` | a complete conversation with menus |
| `conversation_shopkeeper.uws` | labels/goto, filtermenu, quest flags |
| `conversation_riddle_master.uws` | functions with `ask`, `compare` and quest progress |
| `selftest.uws` | checks the main features and prints PASS/FAIL |

## Tests

```bash
cd uwscript
python -m unittest test_uwscript -v
```

The tests compile and run programs in the VM with scripted input. They cover function calls and returns, stack balance in loops, builtins, menus, string building, arrays, compile errors, the command lines, and every sample. The fantasy console has its own tests in `../fantasy_console/fantasy_console_test.py`.

## Editor support

Import `docs/UWScript_udl.xml` into Notepad++ (*Language → User Defined Language → Import*) for highlighting of `.uws` files.
