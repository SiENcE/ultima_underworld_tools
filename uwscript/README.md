# UWScript - A High-Level Language for Ultima Underworld Conversations

UWScript is a higher-level programming language designed to create conversations for Ultima Underworld games. It compiles down to the assembly code understood by the original game engine and the VM runner.

## Enhanced Version with Array Support

The enhanced version adds powerful array capabilities to UWScript:
- **Array Literals** - Create arrays with `[1, 2, 3, 4]` syntax
- **Array Indexing** - Access array elements with `arr[index]`
- **Array Variables** - Declare and manage array variables
- **Array Assignments** - Assign values to specific array indices

These features are especially useful for creating sprite data, managing dialogue options, and storing game state.

## Installation

Requires Python 3.6 or newer. The compiler (`uwscript_compiler.py`) and the VM (`uw_cnv_runner.py`) only use the standard library.

## Usage

Create UWScript files with the `.uws` extension, then compile them using:

```bash
python uwscript_compiler.py input.uws -o output.asm -b 1
```

Where:
- `input.uws` is your UWScript source file
- `output.asm` is the generated assembly file
- `-s strings.txt` sets the generated strings file (default: `input_strings.txt`)
- `-b 1` specifies the string block ID to use (default is 1)
- Add `-v` for verbose output
- Add `--debug` for detailed compiler debug information

The compiled assembly file can then be run with the VM in this folder:

```bash
python uw_cnv_runner.py output.asm --strings input_strings.txt
```

or on the [fantasy console](../fantasy_console/README.md).

## Folder Contents

- `uwscript_compiler.py` - UWScript to UW assembly compiler
- `uw_cnv_runner.py` - Conversation VM matching the compiler's output (also the base of the fantasy console). It has diverged from `tools/conversations/uw_cnv_runner.py`, so keep using this copy for UWScript.
- `uwscript_compiler_bug_unittest.py` - Regression tests (see `uwscript_compiler_bug_unittest.md`)
- `samples/` - Example UWScript programs
- `docs/uwscript-language-spec.md` - Full language specification
- `docs/UWScript_udl.xml` - Notepad++ syntax highlighting for `.uws` files

## Language Features

UWScript provides a much simpler syntax for creating interactive conversations:

- **Variables and Assignment** - Easy to use variable declarations and assignments
- **Arrays** - Create and manipulate arrays for complex data structures
- **Control Flow** - If/else statements, while loops, goto/label
- **Natural Dialogue** - Specialized commands for dialogue (say, ask, menu)
- **Game Integration** - Access to quest flags and game state
- **Function Support** - Define and call functions for code reuse

## Syntax Guide

### Variables

```
// Variable declaration and assignment
let player_name = "Avatar"
let gold = 100
let is_friendly = true

// Assignment to existing variables
gold = gold - 10
is_friendly = false

// Compound assignment
gold += 20  // Add 20 to gold
gold -= 5   // Subtract 5 from gold
```

### Arrays (Enhanced Version)

```
// Array declaration
let inventory = [
    "sword",
    "shield",
    "potion",
    "map"
]

// Array of numbers
let damage_values = [5, 10, 15, 20, 25]

// Access array elements (zero-based indexing)
let weapon = inventory[0]  // Gets "sword"
let healing = damage_values[2]  // Gets 15

// Modify array elements
inventory[3] = "compass"  // Replace "map" with "compass"
damage_values[1] += 5     // Increase second element by 5

// Nested arrays
let game_board = [
    [0, 1, 0],
    [1, 0, 1],
    [0, 1, 0]
]

// Access nested elements
let center_piece = game_board[1][1]  // Gets the center element (0)

// Arrays for sprite data
let sprite = [
    8, 8,  // Width, Height
    1, 0, 1, 0, 1, 0, 1, 0,  // Row 1 pixels
    0, 1, 0, 1, 0, 1, 0, 1,  // Row 2 pixels
    // etc...
]
```

### Control Flow

```
// If statement
if gold >= 50
    say "You have plenty of gold!"
elseif gold >= 10
    say "You have some gold."
else
    say "You're broke!"
endif

// While loop
let counter = 5
while counter > 0
    say "Counting: " + counter
    counter -= 1
endwhile

// Goto and labels
label start_conversation
say "Hello!"
// ...
goto start_conversation
```

### Dialogue

```
// Simple dialogue
say "Welcome to my shop!"

// Get player input
ask player_response
say "You said: " + player_response

// Menu of options
menu choice [
    "Tell me about your wares",
    "I'd like to buy something",
    "Goodbye"
]

// Menu with conditional options
filtermenu quest_choice [
    "Tell me about the castle", has_met_king,
    "Ask about the princess", knows_princess,
    "Goodbye", true
]
```

### Functions

```
// Function definition
function heal_player(amount)
    let health = get_quest(100) 
    health += amount
    if health > 100
        health = 100
    endif
    set_quest(100, health)
    return health
endfunction

// Function call
let new_health = heal_player(20)
say "Health restored to " + new_health
```

### Built-in Functions

```
// Get and set quest flags (game state)
let has_key = get_quest(5)
set_quest(6, 1)

// Random number
let roll = random(20)  // 1-20

// String functions
let str_equal = compare("hello", "HELLO")  // Case-insensitive
let len = string_length("hello")
let contains_word = contains("hello world", "world")

// World interaction
gronk_door(10, 15, 0)  // Open door at x=10, y=15

// Fantasy console functions
clear_screen(0)  // Clear screen to black
draw_line(10, 10, 50, 50, 2)  // Draw red line
draw_sprite(20, 30, my_sprite)  // Draw sprite from array
```

The fantasy console functions only work when running on the [fantasy console](../fantasy_console/README.md).

## Tips for Avoiding Compiler Issues

1. When working with arrays, remember:
   - Arrays are zero-indexed
   - Arrays can't be resized after creation
   - All array elements are 16-bit integers (0-65535)
   - Strings in arrays are stored as string IDs
   
2. Structure:
   - Ensure all blocks are properly terminated with `endif`, `endwhile`, etc.
   - Use proper indentation for readability
   - Avoid complex multi-level array operations

3. General:
   - Use `.uws` extension for your files
   - Start with code (e.g., variable declarations) early in the file
   - Minimize consecutive comments at the start of files

## License

Copyright (c) 2025
