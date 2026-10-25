# UWScript Language Reference

UWScript is a small, line-based language for writing Ultima Underworld conversations (and programs for the [fantasy console](../../fantasy_console/README.md)). The compiler turns a `.uws` file into conversation assembly plus a string block; see [compiler-internals.md](compiler-internals.md) for what the generated code looks like.

## Contents

1. [Program structure](#1-program-structure)
2. [Values and types](#2-values-and-types)
3. [Variables](#3-variables)
4. [Operators](#4-operators)
5. [Strings](#5-strings)
6. [Arrays](#6-arrays)
7. [Control flow](#7-control-flow)
8. [Functions](#8-functions)
9. [Dialogue](#9-dialogue)
10. [Built-in functions](#10-built-in-functions)
11. [Compile errors](#11-compile-errors)
12. [Grammar](#12-grammar)
13. [Examples](#13-examples)

## 1. Program structure

A program is a list of statements, one per line. Blocks are closed with keywords (`endif`, `endwhile`, `endfunction`), and indentation is free.

```uwscript
// A comment runs to the end of the line
let visits = get_quest(10)     // comments may follow a statement

if visits == 0
    say "Welcome, stranger."
else
    say "Welcome back!"
endif
set_quest(10, visits + 1)
exit
```

- Statements end at the line break. Only the lists of `menu [...]`, `filtermenu [...]`, array literals and function call arguments may span several lines.
- The main program is every statement outside a function. It runs from the top and ends at `exit` or at the end of the file.
- Functions are defined at the top level, anywhere in the file, and can be called before their definition.
- Keywords: `if elseif else endif while endwhile function endfunction return let say ask menu filtermenu goto label exit and or not true false`.
- Identifiers start with a letter or `_` and continue with letters, digits or `_`. They are case-sensitive.

## 2. Values and types

Every value is a 16-bit word, like in the game's conversation VM.

| Type | Examples | Notes |
|------|----------|-------|
| Integer | `42`, `0`, `-1` | Signed 16-bit (−32768 to 32767). Results wrap around, so `300 * 300` is 24464 and the literal `65535` equals `-1`. Literals are written 0–65535; use `-` for negative values. Division truncates toward zero. |
| Boolean | `true`, `false` | Stored as 1 and 0. Any non-zero value counts as true. |
| String | `"Hello"` | A string is a *string id* into the conversation's string block (see [Strings](#5-strings)). |
| Array | `[1, 2, 3]` | A fixed block of words; see [Arrays](#6-arrays). |

The compiler tracks whether a variable holds a string or an integer, so that it prints correctly when you join it into text. A variable is a string when it is initialized with a string (a literal, a joined string, a string array element, a function that returns a string), filled by `ask`, or a parameter that receives a string at any call.

## 3. Variables

```uwscript
let gold = 100              // declare and initialize
gold = gold - 10            // assign
gold += 20                  // compound assignment: += -= *= /= %=
```

- A variable must be declared with `let` before it can be assigned. Declaring the same name again in the same scope reuses the variable.
- **Scope is per function, not per block.** Variables declared in the main program (also inside its `if`/`while` blocks) are *globals*. Variables declared inside a function are *locals* of that function, as are its parameters.
- Functions can read and assign globals. A local or parameter with the same name hides the global.
- Inside a function, `ask`, `menu` and `filtermenu` store into a global of that name if one exists (like an assignment); otherwise they declare a local.
- Globals keep their value for the whole conversation. Locals exist only while the function runs; every call, including recursive calls, gets fresh ones.
- Names of functions and built-in functions cannot be used as variable names.

### Saved globals

The game keeps a conversation's globals between talks with the same NPC. `let name` without a value (main program only) declares a global that is *not* set when the conversation starts, so it keeps the value from the last talk (0 the first time):

```uwscript
let visits                  // keeps its value between talks
visits += 1
if visits > 1
    say "You again? That makes " + visits + " visits."
endif
```

A `let` with a value sets the variable again every time. In the game, the size of the saved area per conversation is set in `babglobals.dat` (see [compiler-internals.md](compiler-internals.md#saved-globals)). In the VM, `--globals FILE` saves and restores the state between runs.

### Game globals

These variables are predefined. They read and change the player, the NPC and the game. The game fills them in when the conversation starts and takes changes back at the end, so `npc_attitude = 0` makes the NPC hostile.

| Variables | Meaning |
|-----------|---------|
| `play_name` (string), `play_level`, `play_sex` (0 male, 1 female) | the player |
| `play_hp`, `play_health`, `play_mana`, `play_hunger`, `play_poison`, `play_arms`, `play_power`, `play_drawn`, `new_player_exp` | more player properties |
| `npc_name` (string), `npc_whoami`, `npc_level`, `npc_talkedto` (1 after the first talk) | the NPC |
| `npc_attitude` (0 hostile, 1 upset, 2 mellow, 3 friendly), `npc_goal`, `npc_gtarg` | the NPC's mood and behaviour |
| `npc_hp`, `npc_health`, `npc_hunger`, `npc_arms`, `npc_power`, `npc_xhome`, `npc_yhome` | more NPC properties |
| `dungeon_level`, `game_days`, `game_time`, `game_mins`, `riddlecounter` | the game |

```uwscript
if npc_talkedto == 0
    say "Greetings, " + play_name + ". I am " + npc_name + "."
endif
npc_talkedto = 1
```

Game globals are assigned without `let`, and their names cannot be used for other variables. In the VM, set them with `--set npc_attitude=3 --set play_name=Shanra`.

## 4. Operators

From lowest to highest precedence:

| Precedence | Operators | Meaning |
|------------|-----------|---------|
| 1 | `or` | logical or (result 0 or 1) |
| 2 | `and` | logical and (result 0 or 1) |
| 3 | `==` `!=` | equal, not equal (on two strings: compares the text) |
| 4 | `<` `>` `<=` `>=` | comparisons (result 0 or 1) |
| 5 | `+` `-` | addition, subtraction; `+` also joins strings |
| 6 | `*` `/` `%` | multiplication, integer division, remainder |
| 7 | `-x` `not x` `!x` | negation, logical not |
| 8 | `f(x)` `a[i]` `( )` | call, indexing, grouping |

- `and`, `or` and `not` treat every non-zero value as true, so `1 and 2` is true. Both sides are always evaluated (no short-circuit).
- `not` binds tighter than comparisons: write `not (a == b)` rather than `not a == b`.
- Division truncates toward zero, and the remainder has the sign of the dividend (`-7 / 2` is `-3`, `-7 % 2` is `-1`). Division and remainder by zero give 0 in the VM.
- `-`, `*`, `/`, `%` and `<`/`>`/`<=`/`>=` cannot be used on strings. Inside text, put arithmetic in parentheses: `"n=" + (x - 1)`.

## 5. Strings

### Literals

```uwscript
say "He said \"Hello!\""            // \" quote, \\ backslash
say "Line one\nLine two"            // \n newline, \t tab
```

A string literal must close on the same line. Every distinct literal becomes one entry in the string block.

### Joining strings

`+` joins text when at least one side of the chain is a string:

```uwscript
let name = "Avatar"
let level = 3
say "Welcome, " + name + " of level " + level + "!"
say "Next level in " + (level + 1) * 100 + " points."   // (...) is computed first
say 7 + " gold coins"
```

The game cannot build strings at runtime, so the compiler creates a *string template* with [text substitution codes](compiler-internals.md#text-substitution) (`@GI12`, `@SS0`, ...). The game fills these in when the string is shown. In practice:

- In `say` and in menu options, variables are shown with their current value.
- **A joined string that is stored** (in a variable, an array element, a parameter or a return value) keeps the values from the moment it was built:

  ```uwscript
  let status = "HP: " + hp
  hp = 0
  say status          // still shows the old HP
  ```

- Each `+` expression in the source has one snapshot buffer. If the same line builds a string again (in a loop or a second call of the same function), strings stored from earlier runs show the newest values.
- `s += "more"` appends to a string variable (or string array element). The game cannot create strings at runtime, so a string built from itself (`s += ...`, `s = s + ...`, or a recursive `return "<" + f(n - 1) + ">"`) can only be built once. For conversations (the default `uw` target), the compiler refuses such a line if it can run again: in a loop, in a function, or in a program with labels. With `--target console`, the fantasy console expands the text when it is built, so it also works in loops.
- Joined strings may contain other joined strings. The VM expands substitutions up to 8 levels deep; the original game may expand only one level.
- Text that contains `@` followed by `GI`, `GS`, `SI` or `SS` and a number is read as a substitution code.

### Comparing strings

`==` and `!=` between two string values compare the text and ignore case: they call the built-in `compare`. Comparisons with integers compare the numbers.

```uwscript
ask answer
if answer == "echo"
    say "Correct!"
endif
```

## 6. Arrays

```uwscript
let numbers = [10, 20, 30, 40, 50]
let items = ["sword", "shield", "potion"]     // arrays of string ids
let board = [
    [1, 0, 1],
    [0, 1, 0]
]                                              // nested arrays must be rectangular

say "Second item: " + items[1]                 // indexes start at 0
numbers[2] = 35
numbers[3] += 1
board[1][2] = 1
say "Center: " + board[1][1]
```

- Arrays are created with `let` and an array literal, and their size is fixed. Array literals are only allowed in `let`.
- Elements are words: numbers, booleans or string ids. An array whose elements are all strings is a string array, and its elements print as text.
- Constant indexes are checked at compile time. Computed indexes are not checked at runtime, so stay within the size.
- An array used as a value (for example `f(numbers)`) is its *address*. Inside the function, the parameter is indexed like an array, and changes are visible to the caller:

  ```uwscript
  function double_all(values, count)
      let i = 0
      while i < count
          values[i] *= 2
          i += 1
      endwhile
  endfunction
  double_all(numbers, 5)
  ```

- Only declared arrays support several indexes (`board[r][c]`). A parameter holding an array address takes one index. `board[r]` alone is the address of row `r`; it can be read or passed to a function, but not assigned.

## 7. Control flow

```uwscript
if health <= 0
    say "I'm dying!"
elseif health < 50
    say "I'm injured."
else
    say "I'm fine!"
endif

while turn < 5 and health > 0
    health -= 10
    turn += 1
endwhile

label start                 // a jump target
menu choice ["Again", "Bye"]
if choice == 1
    goto start
endif
exit                        // end the conversation
```

- Labels belong to the main program or to the function they are written in, and `goto` can only jump within that scope. Label names must be unique within their scope.

## 8. Functions

```uwscript
function damage(base, bonus)
    let total = base + bonus
    if total < 1
        return 1
    endif
    return total
endfunction

let hit = damage(10, 5)
say "You deal " + damage(3, 4) + " damage."
damage(1, 1)               // the result may be ignored
```

- Parameters are passed by value, except arrays, which are passed by address. A call must pass exactly as many arguments as the function has parameters.
- `return value` returns a value, and `return` alone returns 0. A function that ends without `return` returns 0.
- Recursion works. Runaway recursion stops the VM with a "Stack overflow" error.
- `return` is only allowed inside functions; use `exit` in the main program. `exit` inside a function ends the whole conversation.
- Functions cannot be nested or defined inside `if`/`while` blocks, and they cannot reuse the name of a built-in function.

## 9. Dialogue

```uwscript
say "Hello, I am a shopkeeper."          // the NPC speaks

ask reply                                // the player types text; reply becomes a string
say "You said: " + reply

menu choice [                            // the player picks an option; choice is 1, 2, ...
    "Tell me about your wares",
    "Goodbye"
]
menu answer "Yes", "No"                  // short form on one line

filtermenu pick [                        // option text, condition pairs
    "Bronze sword (50 gold)", gold >= 50,
    "Health potion (10 gold)", gold >= 10,
    "Leave", true
]
```

- `menu` and `filtermenu` store the chosen option's position (starting at 1) in the variable, which is declared automatically. For `filtermenu`, the position counts *all* options, shown or hidden, so the code above can test `pick == 3` for "Leave" whatever is hidden.
- Options can be joined strings, for example `"Pay " + price + " gold"`.
- The variable after `ask`/`menu`/`filtermenu` is optional. In the short `menu` form, an identifier directly followed by `,` or the end of the line is the first option, not the variable: `menu a, b` shows the strings in `a` and `b`, while `menu choice a, b` also stores the result.

## 10. Built-in functions

All built-ins pass their arguments by reference, as the game expects; the compiler handles this. The compiler checks the number of arguments.

### Ultima Underworld functions

These are the game's imported functions (see [conversation_spec.txt](../../docs/conversation_spec.txt) §7.6). A function marked – returns nothing and cannot be used as a value. `print` with four arguments is the fantasy console's version.

**Dialogue and text**

| Function | Returns | Description |
|----------|---------|-------------|
| `print(text)` | – | show a text no one speaks (a scene description) |
| `compare(a, b)` | 0/1 | 1 if the strings are equal, ignoring case (`==` on strings uses it) |
| `contains(text, part)` | 0/1 | 1 if `text` contains `part`, ignoring case |
| `string_length(s)` | int | length of a string (the game's `length`) |
| `sex(female, male)` | string | `female` for a female avatar, else `male` |

**Quests and the world**

| Function | Returns | Description |
|----------|---------|-------------|
| `random(n)` | int | random number from 1 to n |
| `get_quest(quest)` | int | value of quest flag `quest` |
| `set_quest(quest, value)` | – | set quest flag `quest` to `value` |
| `gronk_door(x, y, close)` | int | open (`close` = 0) or close the door at tile (x, y) |
| `place_object(x, y, slot)` | – | put an object from `do_inv_create` into the world |
| `remove_talker()` | – | the NPC leaves |
| `set_attitude(a, b)`, `set_race_attitude(...)` | – | change attitudes (arguments not fully known) |
| `x_skills(a, b)`, `x_traps(a, b)` | int | skill and trap queries (arguments not fully known) |
| `x_obj_stuff(...9 args)` | – | set object properties in the inventory list |

**Inventory and bartering**

| Function | Returns | Description |
|----------|---------|-------------|
| `setup_to_barter()` | – | start bartering, showing the NPC's items |
| `show_inv(positions, ids)` | int | copy the player's barter items into two arrays (4 entries each) |
| `do_offer(a1, ..., a5[, a6, a7])` | 0/1 | does the NPC accept the current deal |
| `do_demand(refuse_text, agree_text)` | 0/1 | try to make the NPC hand over the items |
| `do_judgement()`, `do_decline()` | – | judge the deal, decline it |
| `give_to_npc(positions, count)` | int | give items from the player to the NPC |
| `give_ptr_npc(quantity, position)` | int | give one item (quantity -1 to ignore) |
| `take_from_npc(item)` | int | give the player an item (or a category if > 1000); 2 if no room |
| `take_id_from_npc(position)`, `take_from_npc_inv(n)` | int | give the player an item by inventory position |
| `do_inv_create(item)` | int | create an item for the NPC; returns its inventory position |
| `do_inv_delete(item)` | int | delete an item from the NPC |
| `check_inv_quality(position)` / `set_inv_quality(quality, position)` | int | read / set an item's quality |
| `count_inv(item)` | int | count items |
| `identify_inv(a, b, c, position)` | int | identify an item |
| `find_inv(where, item)` | int | find an item (`where` 0 NPC, 1 player); 0 if not found |
| `find_barter(item)`, `find_barter_total(a, b, c, d)` | int | find items in the barter area |
| `set_likes_dislikes(likes, dislikes)` | – | arrays of item types the NPC likes or dislikes, ending with -1 |

In the terminal VM, these functions print what they would do and return plausible values. `get_quest` returns 0 until the program sets a flag, `find_inv` finds only the items given with `--item ID`, and `sex` follows `--set play_sex=1`.

### Fantasy console functions

These exist only on the [fantasy console](../../fantasy_console/README.md) (128×128 pixels, 16 colors), so the compiler accepts them only with `--target console`.

| Function | Description |
|----------|-------------|
| `clear_screen([color])` | fill the screen (default black) |
| `set_pixel(x, y, color)` | set one pixel |
| `draw_line(x1, y1, x2, y2, color)` | draw a line |
| `draw_rect(x, y, w, h, color)` / `fill_rect(...)` | outline / filled rectangle |
| `draw_circle(x, y, radius, color)` | circle outline |
| `draw_sprite(x, y, sprite)` | draw an array `[width, height, pixel, ...]`; color 0 is transparent |
| `fill_circle(x, y, radius, color)` | filled circle |
| `print(x, y, text, color)` | draw text with the built-in 3×5 font |
| `get_pixel(x, y)` | color at a pixel, -1 outside the screen |
| `flip_display()` | show the frame (and end the current frame) |
| `play_tone(frequency, ms, channel)` | play a tone |
| `is_key_pressed(key)` / `is_key_released(key)` | keys: 0 up/W, 1 down/S, 2 left/A, 3 right/D, 4 space, 5 return, 6 escape, 7 Z, 8 X |
| `math_sin(deg)` / `math_cos(deg)` | sine/cosine × 100 |
| `math_sqrt(n)` | integer square root |
| `delay(ms)` | pause |
| `get_frame()` | frames shown so far |

## 11. Compile errors

The compiler stops at the first error and reports its line (and usually its column), for example:

```
shop.uws: error: Line 12, column 1: Missing 'endif' for 'if' started at line 4
```

It reports, among others: unknown characters, unterminated strings, numbers above 65535, missing or stray block keywords, statements that are neither an assignment nor a call (`x`, `a == 1`), undefined variables, functions and labels, wrong argument counts, arithmetic on strings, assigning a whole row of an array, `return` outside a function, nested function definitions, constant array indexes out of bounds, non-rectangular nested arrays, using a void function as a value, redeclaring a game global, programs that need more than 0x8000 words of globals, and, for the default `uw` target, fantasy console functions and strings built from themselves on lines that can run again.

### Targets

`--target uw` (the default) accepts only what the original game supports, so the output can become a real conversation. `--target console` also allows the fantasy console functions and the console's runtime string building.

## 12. Grammar

```ebnf
program        = { statement } ;
statement      = ( declaration | assignment | call | if | while | function
                 | return | say | ask | menu | filtermenu | goto | label | "exit" ) end ;
end            = [ comment ] ( newline | end_of_file ) ;

declaration    = "let" identifier [ "=" ( expression | array_literal ) ] ;   (* no value: saved global *)
assignment     = target ( "=" | "+=" | "-=" | "*=" | "/=" | "%=" ) expression ;
target         = identifier { "[" expression "]" } ;
call           = identifier "(" [ expression { "," expression } ] ")" ;

if             = "if" expression end block
                 { "elseif" expression end block }
                 [ "else" end block ] "endif" ;
while          = "while" expression end block "endwhile" ;
function       = "function" identifier "(" [ identifier { "," identifier } ] ")" end
                 block "endfunction" ;                     (* top level only *)
block          = { statement } ;
return         = "return" [ expression ] ;                (* inside functions only *)

say            = "say" expression ;
ask            = "ask" [ identifier ] ;
menu           = "menu" [ identifier ] ( "[" expression { "," expression } "]"
                                       | expression { "," expression } ) ;
filtermenu     = "filtermenu" [ identifier ]
                 "[" expression "," expression { "," expression "," expression } "]" ;
goto           = "goto" identifier ;
label          = "label" identifier ;

expression     = or_expr ;
or_expr        = and_expr { "or" and_expr } ;
and_expr       = equality { "and" equality } ;
equality       = comparison { ( "==" | "!=" ) comparison } ;
comparison     = additive { ( "<" | ">" | "<=" | ">=" ) additive } ;
additive       = term { ( "+" | "-" ) term } ;
term           = unary { ( "*" | "/" | "%" ) unary } ;
unary          = ( "-" | "not" | "!" ) unary | postfix ;
postfix        = primary { "[" expression "]" } | call ;
primary        = number | string | "true" | "false" | identifier | "(" expression ")" ;
array_literal  = "[" ( expression | array_literal ) { "," ( expression | array_literal ) } "]" ;
```

Inside `[...]` lists and call parentheses, line breaks and comments are allowed between elements.

## 13. Examples

The [samples](../samples) folder has runnable programs for each feature. Two longer examples follow.

### A fantasy console game
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

### An NPC conversation
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
