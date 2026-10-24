# UWScript Language Specification (Complete)

UWScript is a high-level language for creating conversations in Ultima Underworld games and fantasy console applications. It provides a simpler syntax than raw assembly while maintaining full access to the game's functions and state.

## Table of Contents
1. [Basic Syntax](#basic-syntax)
2. [Data Types](#data-types)
3. [Arrays](#arrays)
4. [Variables and Assignment](#variables-and-assignment)
5. [Control Flow](#control-flow)
6. [Functions](#functions)
7. [Dialogue System](#dialogue-system)
8. [Built-in Functions](#built-in-functions)
9. [Fantasy Console Functions](#fantasy-console-functions)
10. [Operators](#operators)
11. [String Operations](#string-operations)
12. [Memory Model](#memory-model)
13. [EBNF Grammar](#ebnf-grammar)
14. [Compilation](#compilation)
15. [Examples](#examples)

## Basic Syntax

UWScript uses a statement-based syntax similar to BASIC or Pascal. Each statement typically occupies one line, and blocks are delimited with keywords rather than braces.

### Comments
```uwscript
// Single-line comments start with //
let x = 5  // Comments can appear at end of line

// Multi-line comments are achieved with multiple single-line comments
// This is line 1 of a multi-line comment
// This is line 2 of a multi-line comment
```

## Data Types

UWScript supports the following data types:

- **Integer**: Whole numbers (e.g., `42`, `-1`, `0`)
- **String**: Text enclosed in double quotes (e.g., `"Hello"`, `"Avatar"`)
- **Boolean**: `true` or `false`
- **Array**: Ordered collections of values (e.g., `[1, 2, 3]`, `["a", "b", "c"]`)

## Arrays

Arrays are ordered collections of values that can be accessed by index.

### Array Literals
```uwscript
// Basic array literal
let numbers = [1, 2, 3, 4, 5]

// Mixed-type arrays
let mixed = [42, "text", true, 100]

// Empty array
let empty = []

// Multi-line arrays (useful for sprite data)
let sprite = [
    8, 8,              // Width, Height
    1, 1, 0, 0, 0, 0, 1, 1,  // Row 1
    1, 0, 1, 1, 1, 1, 0, 1,  // Row 2
    0, 1, 1, 2, 2, 1, 1, 0,  // Row 3 (red eyes)
    0, 1, 1, 1, 1, 1, 1, 0,  // Row 4
    0, 1, 1, 3, 3, 1, 1, 0,  // Row 5 (green smile)
    0, 1, 1, 1, 1, 1, 1, 0,  // Row 6
    1, 0, 1, 1, 1, 1, 0, 1,  // Row 7
    1, 1, 0, 0, 0, 0, 1, 1   // Row 8
]
```

### Array Access
```uwscript
let numbers = [10, 20, 30, 40, 50]

// Access elements by index (0-based)
let first = numbers[0]   // 10
let third = numbers[2]   // 30

// Use expressions as indices
let i = 1
let second = numbers[i]  // 20
let fourth = numbers[i + 2]  // 40

// Multidimensional arrays (simulated with linear arrays)
let grid = [
    1, 2, 3,  // Row 0
    4, 5, 6,  // Row 1
    7, 8, 9   // Row 2
]

// Access grid[row][col] as grid[row * width + col]
let row = 1
let col = 2
let width = 3
let value = grid[row * width + col]  // Gets 6 (row 1, col 2)
```

### Array Assignment
```uwscript
let numbers = [10, 20, 30, 40, 50]

// Assign to array elements
numbers[0] = 15
numbers[2] = numbers[1] + 5

// Compound assignment to array elements
numbers[3] += 10     // numbers[3] = numbers[3] + 10
numbers[4] *= 2      // numbers[4] = numbers[4] * 2
```

## Variables and Assignment

### Variable Declaration
```uwscript
// Declaration with initialization
let name = "Gray Goblin"
let health = 50
let is_friendly = true
let items = ["sword", "shield", "potion"]
```

### Assignment
```uwscript
// Basic assignment
health = health - 10
is_friendly = false

// Compound assignment operators
health += 5   // Equivalent to: health = health + 5
health -= 2   // Equivalent to: health = health - 2
health *= 2   // Equivalent to: health = health * 2
health /= 2   // Equivalent to: health = health / 2
```

## Control Flow

### If Statements
```uwscript
// Simple if-else
if health <= 0
    say "I'm dying!"
    exit
endif

// If-elseif-else chain
if health <= 0
    say "I'm dying!"
elseif health < 20
    say "I'm badly wounded!"
elseif health < 50
    say "I'm injured."
else
    say "I'm fine!"
endif
```

### While Loops
```uwscript
let counter = 5
while counter > 0
    say "Counting down: " + counter
    counter -= 1
endwhile

// Complex conditions
let health = 100
let mana = 50
let turn = 0

while health > 0 and mana > 10 and turn < 5
    say "Combat turn " + turn
    health -= 20
    mana -= 15
    turn += 1
endwhile
```

### Labels and Goto
```uwscript
label start_conversation
say "Hello, traveler!"
// ... conversation logic ...
goto start_conversation  // Jump back to the label

label shop_menu
// ... shop logic ...
if continue_shopping
    goto shop_menu
endif
```

## Functions

UWScript supports user-defined functions with parameters and return values.

### Function Definition
```uwscript
// Function with parameters and return value
function calculate_damage(base_damage, strength, weapon_bonus)
    let total = base_damage + strength + weapon_bonus
    if total < 1
        total = 1  // Minimum damage
    endif
    return total
endfunction

// Function without parameters
function greet_player()
    say "Welcome, brave adventurer!"
    return 0
endfunction

// Function without return value (implicit return 0)
function heal_player(amount)
    let current_health = get_quest(100)
    current_health += amount
    if current_health > 100
        current_health = 100
    endif
    set_quest(100, current_health)
endfunction
```

### Function Calls
```uwscript
// Call function and use return value
let damage = calculate_damage(10, 15, 5)
say "You deal " + damage + " damage!"

// Call function without using return value
greet_player()
heal_player(25)

// Use function return in expressions
if calculate_damage(5, 10, 0) > 10
    say "That's a powerful attack!"
endif
```

### Function Scope
- Functions have their own local variable scope
- Parameters are accessed as local variables within the function
- Functions can access global variables
- Local variables shadow global variables of the same name

## Dialogue System

### Say Statements
```uwscript
// Simple dialogue
say "Hello, I am a shopkeeper."

// String concatenation with variables
let player_name = "Avatar"
say "Welcome, " + player_name + "!"
```

### Ask Statements
```uwscript
// Get user input
ask response
say "You said: " + response

// Store input in a variable
ask player_name
say "Nice to meet you, " + player_name + "!"
```

### Menu System
```uwscript
// Bracket notation (preferred for multi-line)
menu choice [
    "Tell me about your wares",
    "I'd like to buy something", 
    "What news from the outside?",
    "Goodbye"
]

// Comma-separated notation (for simple menus)
menu choice "Yes", "No", "Maybe"

// Handle menu choice
if choice == 1
    say "I sell the finest weapons in the land!"
elseif choice == 2
    say "Let me show you what I have..."
elseif choice == 3
    say "Strange times indeed..."
else
    say "Farewell, traveler!"
    exit
endif
```

### Filtered Menu System
```uwscript
// Some options can be disabled based on conditions
filtermenu choice [
    "Ask about the castle", has_met_king,
    "Ask about the princess", knows_princess and reputation > 50,
    "Ask about the quest", quest_active,
    "Buy healing potion", gold >= 50,
    "Leave", true
]

// Only enabled options will be shown to the player
```

## Built-in Functions

### Core Ultima Underworld Functions
```uwscript
// Random numbers
let roll = random(20)        // Returns 1-20
let coin_flip = random(2)    // Returns 1-2

// Quest flag management
let has_key = get_quest(5)   // Get quest flag 5
set_quest(6, 1)              // Set quest flag 6 to 1

// String operations
let str_equal = compare("hello", "HELLO")     // Case-insensitive: returns 1
let len = string_length("hello")              // Returns 5
let contains = contains("hello world", "world")  // Returns 1 (true)

// World interaction
gronk_door(10, 15, 0)  // Open door at coordinates (10, 15)
gronk_door(10, 15, 1)  // Close door at coordinates (10, 15)
```

## Fantasy Console Functions

UWScript can target fantasy consoles with additional graphics, sound, and input functions.

### Graphics Functions
```uwscript
// Screen management
clear_screen(0)              // Clear with color 0 (black)
flip_display()               // Update the display

// Drawing primitives
set_pixel(50, 50, 15)        // Set pixel at (50,50) to color 15
draw_line(0, 0, 127, 127, 2) // Draw red line from (0,0) to (127,127)
draw_rect(10, 10, 50, 30, 4) // Draw blue rectangle outline
fill_rect(20, 20, 30, 20, 3) // Draw filled green rectangle
draw_circle(64, 64, 25, 1)   // Draw white circle at center

// Sprite rendering
let player_sprite = [
    8, 8,                    // 8x8 sprite
    0, 0, 1, 1, 1, 1, 0, 0, // Row 0
    0, 1, 1, 2, 2, 1, 1, 0, // Row 1 (red eyes)
    // ... more pixel data
]
draw_sprite(50, 50, player_sprite)  // Draw sprite at (50, 50)

// Text rendering
print(10, 10, "Score: 1000", 15)   // Print text at (10,10) in white
```

### Sound Functions
```uwscript
// Play tones
play_tone(440, 500, 0)      // Play 440Hz for 500ms on channel 0
play_tone(880, 250, 1)      // Play 880Hz for 250ms on channel 1
```

### Input Functions
```uwscript
// Key constants
let KEY_UP = 0
let KEY_DOWN = 1
let KEY_LEFT = 2
let KEY_RIGHT = 3
let KEY_SPACE = 4
let KEY_RETURN = 5
let KEY_ESCAPE = 6

// Check key states
if is_key_pressed(KEY_UP)
    player_y -= 2
endif

if is_key_released(KEY_SPACE)
    // Fired projectile
endif
```

### Math Functions
```uwscript
// Trigonometry (angles in degrees)
let x_offset = math_cos(angle)       // Returns scaled integer
let y_offset = math_sin(angle)       // Returns scaled integer

// Other math
let distance = math_sqrt(dx * dx + dy * dy)
```

## Operators

### Arithmetic Operators
- `+`: Addition (numbers) or concatenation (strings)
- `-`: Subtraction
- `*`: Multiplication  
- `/`: Division (integer division)
- `%`: Modulo (remainder)

### Comparison Operators
- `==`: Equal to
- `!=`: Not equal to
- `>`: Greater than
- `<`: Less than
- `>=`: Greater than or equal to
- `<=`: Less than or equal to

### Logical Operators
- `and`: Logical AND
- `or`: Logical OR
- `not`: Logical NOT

### Assignment Operators
- `=`: Basic assignment
- `+=`: Add and assign
- `-=`: Subtract and assign
- `*=`: Multiply and assign
- `/=`: Divide and assign

### Unary Operators
- `-`: Negation (e.g., `-x`)
- `not`: Logical NOT (e.g., `not is_alive`)

## String Operations

### String Concatenation
```uwscript
let full_name = first_name + " " + last_name
say "Hello, " + player_name + "!"

// Automatic variable substitution (compiler feature)
let health = 75
say "Health: " + health  // Becomes "Health: @SI0" in assembly
```

### String Literals
```uwscript
// Basic strings
let message = "Hello, world!"

// Escape sequences
let formatted = "Name:\tAvatar\nLevel:\t5"  // Tab and newline
let quoted = "He said, \"Hello!\""          // Embedded quotes
let path = "C:\\Games\\UW"                  // Backslash
```

### String Substitution (Advanced)
The compiler automatically handles string concatenation with variables by generating UW text substitution codes:

- `@SI<n>`: Substitute integer variable at offset n
- `@SS<n>`: Substitute string variable at offset n

## Memory Model

### Variable Allocation
- Global variables are allocated sequentially starting from offset 0
- Function parameters are accessed as negative offsets from base pointer
- Local variables are allocated after parameters
- Arrays occupy consecutive memory slots
- Temporary variables are managed automatically

### Scoping Rules
- Global scope: Variables declared at program level
- Function scope: Parameters and local variables within functions
- Local variables shadow global variables of the same name
- No block-level scoping (unlike C/Java)

## EBNF Grammar

```ebnf
program = { statement } ;

statement = variable_declaration
          | assignment
          | if_statement
          | while_statement
          | function_definition
          | function_call_statement
          | return_statement
          | say_statement
          | ask_statement
          | menu_statement
          | filtermenu_statement
          | goto_statement
          | label_statement
          | exit_statement ;

variable_declaration = "let" identifier "=" expression eol ;

assignment = assignment_target assignment_operator expression eol ;
assignment_target = identifier | array_access ;
assignment_operator = "=" | "+=" | "-=" | "*=" | "/=" ;

if_statement = "if" expression eol
               { statement }
               { "elseif" expression eol { statement } }
               [ "else" eol { statement } ]
               "endif" eol ;

while_statement = "while" expression eol
                  { statement }
                  "endwhile" eol ;

function_definition = "function" identifier "(" [ parameter_list ] ")" eol
                      { statement }
                      "endfunction" eol ;
parameter_list = identifier { "," identifier } ;

function_call_statement = function_call eol ;

return_statement = "return" [ expression ] eol ;

say_statement = "say" expression eol ;

ask_statement = "ask" [ identifier ] eol ;

menu_statement = "menu" [ identifier ] ( array_literal | expression_list ) eol ;

filtermenu_statement = "filtermenu" [ identifier ] array_literal eol ;

goto_statement = "goto" identifier eol ;

label_statement = "label" identifier eol ;

exit_statement = "exit" eol ;

expression = logical_or ;

logical_or = logical_and { "or" logical_and } ;

logical_and = equality { "and" equality } ;

equality = comparison { ( "==" | "!=" ) comparison } ;

comparison = additive { ( ">" | "<" | ">=" | "<=" ) additive } ;

additive = multiplicative { ( "+" | "-" ) multiplicative } ;

multiplicative = unary { ( "*" | "/" | "%" ) unary } ;

unary = [ ( "-" | "not" ) ] postfix ;

postfix = primary { ( "[" expression "]" | "(" [ expression_list ] ")" ) } ;

primary = number
        | string
        | boolean
        | identifier
        | array_literal
        | "(" expression ")" ;

array_literal = "[" [ expression_list ] "]" ;

expression_list = expression { "," expression } ;

function_call = identifier "(" [ expression_list ] ")" ;

array_access = postfix "[" expression "]" ;

identifier = letter { letter | digit | "_" } ;

number = digit { digit } ;

string = '"' { character | escape_sequence } '"' ;

boolean = "true" | "false" ;

escape_sequence = "\\" ( "n" | "t" | '"' | "\\" ) ;

eol = newline | eof ;

comment = "//" { character } newline ;

(* Lexical elements *)
letter = "a".."z" | "A".."Z" ;
digit = "0".."9" ;
character = ? any Unicode character except newline ? ;
newline = ? newline character ? ;
eof = ? end of file ? ;
```

## Compilation

### Compiler Usage
```bash
python uwscript_compiler.py input.uws -o output.asm -s strings.txt -b 1 -v
```

Options:
- `input.uws`: Source file
- `-o output.asm`: Output assembly file
- `-s strings.txt`: Output strings file  
- `-b 1`: String block ID (default: 1)
- `-v`: Verbose output
- `--debug`: Enable debug mode

### Compilation Process
1. **Lexical Analysis**: Tokenize source code
2. **Parsing**: Build Abstract Syntax Tree (AST)
3. **Code Generation**: Convert AST to UW assembly
4. **String Extraction**: Collect string literals
5. **Optimization**: Temporary variable management

### Generated Files
- **Assembly File**: Contains UW VM instructions
- **Strings File**: Contains string literals in STRINGS.PAK format
- **Debug Info**: Variable mappings and compilation statistics

## Examples

### Complete Fantasy Console Game
```uwscript
// Simple Pong-like game
let KEY_UP = 0
let KEY_DOWN = 1
let KEY_ESCAPE = 6

let paddle_y = 60
let ball_x = 64
let ball_y = 32
let ball_dx = 1
let ball_dy = 1
let score = 0
let running = true

say "Use UP/DOWN arrows to move paddle. ESC to quit."

label game_loop
    // Clear screen
    clear_screen(0)
    
    // Handle input
    if is_key_pressed(KEY_UP) and paddle_y > 0
        paddle_y -= 2
    endif
    
    if is_key_pressed(KEY_DOWN) and paddle_y < 108
        paddle_y += 2
    endif
    
    if is_key_pressed(KEY_ESCAPE)
        running = false
    endif
    
    // Update ball
    ball_x += ball_dx
    ball_y += ball_dy
    
    // Ball collision with top/bottom
    if ball_y <= 0 or ball_y >= 127
        ball_dy = -ball_dy
    endif
    
    // Ball collision with left edge (paddle)
    if ball_x <= 5
        if ball_y >= paddle_y and ball_y <= paddle_y + 20
            ball_dx = -ball_dx
            score += 1
        else
            // Game over
            say "Game Over! Score: " + score
            exit
        endif
    endif
    
    // Ball collision with right edge
    if ball_x >= 127
        ball_dx = -ball_dx
    endif
    
    // Draw paddle
    fill_rect(2, paddle_y, 3, 20, 1)
    
    // Draw ball
    fill_rect(ball_x, ball_y, 2, 2, 2)
    
    // Draw score
    print(50, 5, "Score: " + score, 15)
    
    // Update display
    flip_display()
    
    if running
        goto game_loop
    endif

say "Thanks for playing!"
exit
```

### Interactive NPC Conversation
```uwscript
// Merchant NPC with inventory system
let player_gold = 100
let has_sword = false
let has_potion = false
let merchant_attitude = 5  // 1-10 scale

function check_affordability(price)
    if player_gold >= price
        return true
    else
        return false
    endif
endfunction

function complete_purchase(item_name, price)
    player_gold -= price
    say "You purchased " + item_name + " for " + price + " gold."
    say "Remaining gold: " + player_gold
endfunction

label start
say "Welcome to my humble shop, traveler!"

if merchant_attitude >= 8
    say "You're one of my best customers!"
elseif merchant_attitude <= 3
    say "I suppose I can spare a moment for you..."
endif

menu main_choice [
    "Show me your wares",
    "Tell me about this place", 
    "How much gold do I have?",
    "Goodbye"
]

if main_choice == 1
    goto show_wares
elseif main_choice == 2
    goto tell_about_place
elseif main_choice == 3
    say "You currently have " + player_gold + " gold pieces."
    goto start
else
    say "Safe travels, friend!"
    exit
endif

label show_wares
say "Here's what I have in stock:"

filtermenu purchase [
    "Iron Sword (75 gold)", check_affordability(75) and not has_sword,
    "Health Potion (25 gold)", check_affordability(25) and not has_potion,
    "Magic Scroll (150 gold)", check_affordability(150),
    "Back to main menu", true
]

if purchase == 1
    complete_purchase("Iron Sword", 75)
    has_sword = true
    merchant_attitude += 1
elseif purchase == 2
    complete_purchase("Health Potion", 25)
    has_potion = true
elseif purchase == 3
    complete_purchase("Magic Scroll", 150)
    merchant_attitude += 2
else
    goto start
endif

say "Is there anything else I can help you with?"
goto start

label tell_about_place
say "This village has stood for over two centuries."
say "We've weathered many storms, both literal and metaphorical."

if merchant_attitude >= 6
    say "Between you and me, there are strange happenings in the old ruins to the north."
    say "Might be worth investigating... if you're brave enough."
endif

goto start
```

This specification now covers all the features implemented in the UWScript compiler, including arrays, fantasy console functions, proper function support with parameters, and the complete EBNF grammar.