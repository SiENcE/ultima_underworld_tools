# Updated Ultima Underworld Conversation Development Manual

After analyzing the toolkit provided in the repository, I've enhanced this manual with practical workflows and detailed instructions for developing NPC conversations in Ultima Underworld.

## Table of Contents

1. [Introduction](#introduction)
2. [Conversation System Overview](#conversation-system-overview)
3. [Memory Model and Variables](#memory-model-and-variables)
4. [Conversation Assembly Language](#conversation-assembly-language)
5. [Control Flow Instructions](#control-flow-instructions)
6. [Working with Strings](#working-with-strings)
7. [Conversation Structure Patterns](#conversation-structure-patterns)
8. [Imported Functions Reference](#imported-functions-reference)
9. [Development Workflow](#development-workflow)
10. [Example Conversations](#example-conversations)
11. [Troubleshooting and Limitations](#troubleshooting-and-limitations)
12. [Tool Reference](#tool-reference)

## Introduction

Ultima Underworld uses a custom virtual machine with an assembly-like language for handling NPC conversations. This manual guides you through developing conversations using the Python toolkit provided, from simple dialogue trees to complex interactive scripts.

## Conversation System Overview

### Core Concepts

The conversation system in Ultima Underworld is built around a stack-based virtual machine with a 16-bit architecture. Each conversation is:

- Stored in the CNV.ARK file in a specific slot (0-255)
- Associated with a block of strings in STRINGS.PAK 
- Executed by a virtual processor with specific opcodes
- Able to access game variables and imported functions

### File Architecture

Conversations are stored in two primary files:

1. **CNV.ARK** - Contains the compiled bytecode for each conversation
   - In UW2, this file is compressed
   - Each conversation has a header, import table, and code section

2. **STRINGS.PAK** - Contains all text strings referenced by conversations
   - Uses Huffman compression
   - Organized into blocks, each with multiple strings

The conversation header contains:
- Conversation metadata
- String block ID to use
- Memory slot allocation
- Number of imported functions/variables

### Basic Workflow

1. Extract existing conversations for reference
2. Create or modify string blocks
3. Write conversation script in assembly (.asm)
4. Test using the conversation runner
5. Compile and pack into game files

## Memory Model and Variables

### Memory Organization

```
Memory Address    Contents
0000              Local (unnamed) variables
000n              Game globals (copied at conversation start)
0020              Private conversation globals (persistent between talks)
0020+n            Stack (grows upward)
```

### Variable Types

Conversations can use several types of variables:

1. **Quest Flags** (32 flags): Global variables accessible by any NPC
   - Stored in the savegame file
   - Used to track game progress and quests

2. **Game Globals**: System variables for game state
   - `play_*`: Player stats (health, mana, level, etc.)
   - `npc_*`: NPC stats (health, attitude, goal, etc.)
   - `game_*`: Game state (time, level, etc.)

3. **Private Globals**: Variables persistent for a specific NPC
   - Defined in `babglobals.dat` and stored in `bglobals.dat` during gameplay
   - Preserve state between conversations with the same NPC

4. **Local Variables**: Temporary variables used during the conversation
   - Lost when conversation ends
   - Allocated on the stack

### Accessing Variables

Variables are accessed via memory addresses:

```assembly
; Push immediate value 42
PUSHI 42

; Push memory address relative to base pointer (local var)
PUSHI_EFF 1

; Fetch value at memory address
FETCHM

; Store value to memory address
STO
```

## Conversation Assembly Language

### VM Architecture

The UW conversation VM is:
- Stack-based (operations work with values on the stack)
- Has a 16-bit memory model (64K address space)
- Uses a frame pointer (BP) and stack pointer (SP)
- Has a result register for imported function returns

### Basic Syntax

```assembly
; This is a comment
OPCODE [argument]  ; Inline comment

label_name:        ; Label definition
  INSTRUCTION
```

### Opcode Reference

| Opcode | Mnemonic | Description |
|--------|----------|-------------|
| 0x00   | NOP      | No operation |
| 0x01   | OPADD    | Add top two values on stack |
| 0x02   | OPMUL    | Multiply top two values |
| 0x03   | OPSUB    | Subtract s[0] from s[1] |
| 0x04   | OPDIV    | Divide s[1] by s[0] |
| 0x05   | OPMOD    | s[1] modulo s[0] |
| 0x06   | OPOR     | Logical OR |
| 0x07   | OPAND    | Logical AND |
| 0x08   | OPNOT    | Logical NOT |
| 0x09   | TSTGT    | Test greater than |
| 0x0A   | TSTGE    | Test greater than or equal |
| 0x0B   | TSTLT    | Test less than |
| 0x0C   | TSTLE    | Test less than or equal |
| 0x0D   | TSTEQ    | Test equality |
| 0x0E   | TSTNE    | Test not equal |
| 0x0F   | JMP      | Jump to absolute address |
| 0x10   | BEQ      | Branch if zero |
| 0x11   | BNE      | Branch if non-zero |
| 0x12   | BRA      | Branch always (relative) |
| 0x13   | CALL     | Call subroutine |
| 0x14   | CALLI    | Call imported function |
| 0x15   | RET      | Return from subroutine |
| 0x16   | PUSHI    | Push immediate value |
| 0x17   | PUSHI_EFF| Push effective address (BP+offset) |
| 0x18   | POP      | Pop and discard value |
| 0x19   | SWAP     | Swap top two stack values |
| 0x1A   | PUSHBP   | Push base pointer |
| 0x1B   | POPBP    | Pop to base pointer |
| 0x1C   | SPTOBP   | Set BP to SP (new frame) |
| 0x1D   | BPTOSP   | Set SP to BP (exit frame) |
| 0x1E   | ADDSP    | Reserve stack space |
| 0x1F   | FETCHM   | Fetch from memory |
| 0x20   | STO      | Store to memory |
| 0x21   | OFFSET   | Calculate array offset |
| 0x22   | START    | Start program |
| 0x23   | SAVE_REG | Save value to result register |
| 0x24   | PUSH_REG | Push result register |
| 0x26   | EXIT_OP  | End program |
| 0x27   | SAY_OP   | NPC says string |
| 0x29   | OPNEG    | Negate value |

## Control Flow Instructions

### Unconditional Control Flow

```assembly
; Jump to a label
JMP label_name    

; Branch relative (offset in words)
BRA 5             

; Call a subroutine
CALL label_name   

; Return from subroutine
RET               
```

### Conditional Branching

```assembly
; Branch if equal (when top of stack is 0)
BEQ label_true    

; Branch if not equal (when top of stack is not 0)
BNE label_false   
```

Pattern for handling menu choices:

```assembly
PUSH_REG       ; Get the result of menu function
PUSHI 1        ; Option 1
TSTEQ          ; Compare
BEQ option1    ; Branch if chosen

PUSH_REG
PUSHI 2        ; Option 2
TSTEQ
BEQ option2

; Default case
BRA main_menu
```

### Subroutines

Functions can be defined using labels and called with CALL:

```assembly
; Define a subroutine
show_greeting:
  PUSHI 1
  SAY_OP
  RET

; Call it
CALL show_greeting
```

## Working with Strings

### String Blocks

Strings in Ultima Underworld are stored in STRINGS.PAK in blocks. The format is:

```
block: NNNN; X strings.
0: First string
1: Second string
2: Third string
```

Where NNNN is the block ID in hexadecimal.

### Using Strings in Conversations

Strings are referenced by their index in the current string block:

```assembly
; Say string 5 from the current block
PUSHI 5
SAY_OP
```

### Menus and Player Choices

The `babl_menu` function (ID=0) shows player choices:

```assembly
; Create pointer to string array
PUSHI_EFF 1     
; Add strings to the array
PUSHI 1        ; First option
PUSHI 2        ; Second option
PUSHI 0        ; Null terminator for array
; Number of arguments (1)
PUSHI 1
; Call babl_menu
CALLI 0        

; Player's choice is now in the result register
PUSH_REG       ; Push to stack for processing
```

For conditional menus, use `babl_fmenu` (ID=1):

```assembly
; String array pointer
PUSHI_EFF 1
PUSHI 1        ; Option 1 string
PUSHI 2        ; Option 2 string
PUSHI 0        ; End of array

; Flags array pointer (1=show, 0=hide)
PUSHI_EFF 2
PUSHI 1        ; Show option 1
PUSHI 0        ; Hide option 2
PUSHI 0        ; End of array

; Call filtered menu
PUSHI 2        ; Two arguments
CALLI 1
```

### Text Substitution

Strings can contain special tokens for dynamic values:

- `@SI1` - String index 1
- `@GS8` - String from global variable 8
- `@PI2` - Integer value pointed to by stack position 2

## Conversation Structure Patterns

### Basic Conversation

```assembly
START

; Greeting
PUSHI 0
SAY_OP

; Farewell
PUSHI 1
SAY_OP

EXIT_OP
```

### Menu Loop

```assembly
START

; Greeting
PUSHI 0
SAY_OP

main_loop:
  ; Show menu
  PUSHI_EFF 1    ; Array pointer
  PUSHI 1        ; Option 1
  PUSHI 2        ; Option 2
  PUSHI 3        ; Option 3
  PUSHI 0        ; End of array
  PUSHI 1        ; One argument
  CALLI 0        ; Call menu

  ; Handle choice
  PUSH_REG
  PUSHI 1
  TSTEQ
  BEQ handle_1
  
  PUSH_REG
  PUSHI 2
  TSTEQ
  BEQ handle_2
  
  PUSH_REG
  PUSHI 3
  TSTEQ
  BEQ exit_conv
  
  BRA main_loop

handle_1:
  PUSHI 4
  SAY_OP
  BRA main_loop

handle_2:
  PUSHI 5
  SAY_OP
  BRA main_loop

exit_conv:
  PUSHI 6
  SAY_OP
  EXIT_OP
```

### Quest State Tracking

```assembly
; Check quest flag
PUSHI_EFF 1    
PUSHI 5        ; Quest ID
PUSHI 1        ; Argument count
CALLI 15       ; get_quest

; Check result
PUSH_REG
PUSHI 0        ; Not started
TSTEQ
BEQ quest_new

PUSH_REG
PUSHI 1        ; In progress
TSTEQ
BEQ quest_progress

; Complete
PUSHI 10
SAY_OP
BRA done

quest_new:
  ; Give quest
  PUSHI 11
  SAY_OP
  
  ; Set quest flag to "in progress"
  PUSHI_EFF 1
  PUSHI 1      ; New status
  PUSHI_EFF 2
  PUSHI 5      ; Quest ID
  PUSHI 2      ; Argument count
  CALLI 16     ; set_quest
  BRA done

quest_progress:
  PUSHI 12
  SAY_OP

done:
  EXIT_OP
```

## Imported Functions Reference

The most commonly used functions:

| ID | Name | Args | Return | Description |
|----|------|------|--------|-------------|
| 0 | babl_menu | 1 | int | Shows menu of options |
| 1 | babl_fmenu | 2 | int | Shows filtered menu |
| 2 | print | 1 | void | Prints non-spoken text |
| 3 | babl_ask | 0 | int | Gets player text input |
| 4 | compare | 2 | int | Compares two strings |
| 5 | random | 1 | int | Generates random number |
| 15 | get_quest | 1 | int | Gets quest flag value |
| 16 | set_quest | 2 | void | Sets quest flag value |
| 17 | sex | 2 | string | Gender-specific string |
| 31 | setup_to_barter | 0 | void | Starts bartering |

### Using Imported Functions

For each function call:
1. Push arguments in reverse order
2. Push number of arguments
3. Call the function with CALLI
4. Get result with PUSH_REG if needed

## Development Workflow

### Complete Process

1. **Explore existing conversations**:
   ```bash
   python tools/conversations/uw_cnv_decompiler.py CNV.ARK -o extracted
   ```

2. **Extract string blocks**:
   ```bash
   python tools/strings/uw-strings-extractor.py
   ```
   This creates `uw-strings.txt` and `uw-strings-metadata.json`

3. **Create/edit string block**:
   Edit `uw-strings.txt` to add your strings or modify existing ones

4. **Write conversation script**:
   Create an ASM file with proper headers:
   ```assembly
   ; My conversation
   ; Slot: 010C
   ; String Block: 0123
   
   START
   ; Your code here
   ```

5. **Test conversation**:
   ```bash
   python tools/conversations/uw_cnv_runner.py my_conversation.asm --strings uw-strings.txt
   ```

6. **Compile conversation**:
   ```bash
   python tools/conversations/uw_cnv_compiler.py my_conversation.asm
   ```

7. **Update game files**:
   - Separately or with direct CNV.ARK update:
   ```bash
   python tools/conversations/uw_cnv_compiler.py my_conversation.asm --update-cnv CNV.ARK
   ```
   - For strings:
   ```bash
   python tools/strings/uw-strings-packer.py
   ```

### Advanced: Translation Workflow

For creating translations:

1. Extract strings using the extractor
2. Use the translator tool:
   ```bash
   python tools/strings/uw-strings-translator.py uw-strings.txt uw-strings-de.txt --source English --target German
   ```
3. Pack the translated strings with the packer

## Example Conversations

### Simple Greeting

```assembly
; Simple greeting example
; Slot: 0100
; String Block: 0100

START
; Greeting based on meeting before
PUSHI_EFF 1
PUSHI 31         ; first_encounter global
PUSHI 1
CALLI 15         ; get_quest

PUSH_REG
PUSHI 0
TSTEQ            ; Is this the first meeting?
BEQ first_meeting

; Not first meeting
PUSHI 1
SAY_OP
BRA end_greeting

first_meeting:
  ; First time greeting
  PUSHI 0
  SAY_OP
  
  ; Set first encounter flag
  PUSHI_EFF 1
  PUSHI 1        ; Set to true
  PUSHI_EFF 2
  PUSHI 31       ; first_encounter global
  PUSHI 2
  CALLI 16       ; set_quest

end_greeting:
  PUSHI 2
  SAY_OP
  EXIT_OP
```

String block:
```
block: 0064; 3 strings.
0: Greetings, traveler! I'm Farmer Giles. Welcome to our village.
1: Hello again! Good to see you.
2: Safe travels!
```

### Quest Giver

```assembly
; Quest giver example
; Slot: 0101
; String Block: 0101

START
; Greeting
PUSHI 0
SAY_OP

; Check quest state (Quest ID 7)
PUSHI_EFF 1
PUSHI 7          ; Quest flag ID 
PUSHI 1
CALLI 15         ; get_quest

; Check quest state
PUSH_REG
PUSHI 2          ; Completed
TSTEQ
BEQ quest_done

PUSH_REG
PUSHI 1          ; In progress
TSTEQ
BEQ quest_active

; Quest not started
quest_new:
  PUSHI 1
  SAY_OP
  
  ; Show options
  PUSHI_EFF 1    ; String array
  PUSHI 2        ; Accept
  PUSHI 3        ; Decline
  PUSHI 0        ; End array
  PUSHI 1        ; Argument count
  CALLI 0        ; Show menu
  
  PUSH_REG
  PUSHI 1        ; Accepted?
  TSTEQ
  BEQ accept_quest
  
  ; Declined
  PUSHI 4
  SAY_OP
  EXIT_OP
  
accept_quest:
  ; Set quest to active
  PUSHI_EFF 1
  PUSHI 1        ; Status = in progress
  PUSHI_EFF 2
  PUSHI 7        ; Quest ID
  PUSHI 2
  CALLI 16       ; set_quest
  
  PUSHI 5
  SAY_OP
  EXIT_OP

quest_active:
  ; Check inventory for quest item
  PUSHI_EFF 1
  PUSHI 0        ; NPC inventory
  PUSHI_EFF 2
  PUSHI 120      ; Item ID (amulet)
  PUSHI 2
  CALLI 48       ; find_inv function
  
  PUSH_REG
  PUSHI 0
  TSTNE          ; Found item?
  BEQ no_item
  
  ; Item found!
  PUSHI 7
  SAY_OP
  
  ; Complete quest
  PUSHI_EFF 1
  PUSHI 2        ; Status = completed
  PUSHI_EFF 2
  PUSHI 7        ; Quest ID
  PUSHI 2
  CALLI 16       ; set_quest
  
  ; Give reward
  PUSHI_EFF 1
  PUSHI 210      ; Gold ring item
  PUSHI 1
  CALLI 26       ; do_inv_create
  
  PUSHI 8
  SAY_OP
  EXIT_OP
  
no_item:
  PUSHI 6
  SAY_OP
  EXIT_OP

quest_done:
  PUSHI 9
  SAY_OP
  EXIT_OP
```

String block:
```
block: 0065; 10 strings.
0: *The elderly woman smiles as you approach*
1: Oh, adventurer! My precious amulet was stolen by goblins. Please, will you retrieve it for me?
2: I'll find your amulet.
3: I cannot help right now.
4: I understand. Return if you change your mind.
5: Bless you! The goblins lair is to the east of the village.
6: Have you found my amulet yet? Please hurry, it means so much to me.
7: You found it! My precious amulet! Thank you, brave adventurer!
8: Please take this enchanted ring as a token of my gratitude.
9: Thank you again for your help. May the virtues guide your path.
```

### Merchant with Bartering

```assembly
; Merchant example
; Slot: 0102
; String Block: 0102

START
; Greeting
PUSHI 0
SAY_OP

main_menu:
  ; Show options
  PUSHI_EFF 1
  PUSHI 1        ; Buy
  PUSHI 2        ; Sell
  PUSHI 3        ; About yourself
  PUSHI 4        ; Leave
  PUSHI 0        ; End array
  PUSHI 1        ; Argument count
  CALLI 0        ; Menu function
  
  PUSH_REG
  PUSHI 1
  TSTEQ
  BEQ buy_option
  
  PUSH_REG
  PUSHI 2
  TSTEQ
  BEQ sell_option
  
  PUSH_REG
  PUSHI 3
  TSTEQ
  BEQ about_option
  
  PUSH_REG
  PUSHI 4
  TSTEQ
  BEQ exit_option
  
  BRA main_menu

buy_option:
  PUSHI 5
  SAY_OP
  
  ; Setup likes/dislikes
  PUSHI_EFF 1
  PUSHI 200      ; Weapons
  PUSHI 201      ; Armor
  PUSHI -1       ; End list
  
  PUSHI_EFF 2
  PUSHI 300      ; Food
  PUSHI -1       ; End list
  
  PUSHI 2
  CALLI 36       ; set_likes_dislikes
  
  ; Start bartering
  PUSHI 0
  CALLI 31       ; setup_to_barter
  
  BRA main_menu

sell_option:
  PUSHI 6
  SAY_OP
  
  ; Show inventory
  PUSHI_EFF 1    ; Item positions array
  PUSHI_EFF 2    ; Item IDs array
  PUSHI 2
  CALLI 18       ; show_inv
  
  PUSH_REG
  PUSHI 0
  TSTEQ          ; No items selected?
  BEQ main_menu
  
  ; Try to complete sale
  PUSHI_EFF 1
  PUSHI 10       ; Minimum value
  PUSHI_EFF 2
  PUSHI 50       ; Maximum value
  PUSHI_EFF 3
  PUSHI 0        ; Reserved
  PUSHI_EFF 4
  PUSHI 0        ; Reserved
  PUSHI_EFF 5
  PUSHI 0        ; Reserved
  PUSHI 5
  CALLI 24       ; do_offer
  
  PUSH_REG
  PUSHI 1
  TSTEQ          ; Accepted?
  BEQ sale_accepted
  
  ; Sale rejected
  PUSHI 8
  SAY_OP
  BRA main_menu
  
sale_accepted:
  PUSHI 7
  SAY_OP
  BRA main_menu

about_option:
  PUSHI 9
  SAY_OP
  BRA main_menu

exit_option:
  PUSHI 10
  SAY_OP
  EXIT_OP
```

String block:
```
block: 0066; 11 strings.
0: Welcome to my humble shop, traveler!
1: I'd like to buy something.
2: I have items to sell.
3: Tell me about yourself.
4: I must be going.
5: Here's what I have available. Quality goods at fair prices!
6: Show me what you're offering.
7: A pleasure doing business with you!
8: I'm afraid I can't accept that offer.
9: I've been a merchant for twenty years. My family has owned this shop for generations.
10: Come back soon! May your travels be profitable.
```

## Troubleshooting and Limitations

### Common Issues

1. **String Block Mismatch**: 
   - Error: Strings display as "[Invalid string ID]"
   - Solution: Double-check the String Block declaration in your ASM header, also check if it's hex and not decimal

2. **Stack Imbalance**:
   - Error: VM crashes or behaves unexpectedly
   - Solution: Ensure every PUSHI is balanced by a corresponding operation
   - Debug: Use the runner with `--debug` to track stack operations

3. **Branch Offset Errors**:
   - Error: Jumps to wrong locations
   - Solution: Use labels instead of manual offsets
   - The compiler will calculate correct offsets for you

4. **Function Argument Issues**:
   - Error: Function behaves unexpectedly
   - Solution: Check the exact number of arguments required
   - Remember to push the argument count as last parameter

5. **Memory Corruption**:
   - Error: Variables change unexpectedly
   - Solution: Be careful with memory addresses and array offsets
   - Avoid hard-coded addresses when possible

### Technical Limitations

1. **String Block Size**: Limited number of strings per block
   - UW1 blocks typically have 50-100 strings maximum

2. **Conversation Size**: Limited bytecode size per conversation
   - Large conversations may need to be split

3. **Quest Flags**: Only 32 quest flags available (0-31)
   - Flags 0-31 are stored as bits in a single 32-bit integer
   - Flags 32-35 are stored as individual bytes

4. **Memory Size**: 64K address space (16-bit)
   - Stack space depends on memory allocation in header

5. **UW2 Compatibility**: 
   - UW2 uses compressed ARK files
   - Use the same tools with UW2-specific flags

### Testing Tips

1. Use the runner with debug mode to trace execution:
   ```bash
   python tools/conversations/uw_cnv_runner.py my_conversation.asm --strings uw-strings.txt --debug
   ```

2. Test incrementally - add small sections and test frequently

3. Examine decompiled conversations from the original game for patterns

4. Create test string blocks for development before adding to the game

5. Monitor stack usage in debug mode to catch imbalances early

## Tool Reference

### uw-strings-analyzer.py

Analyzes STRINGS.PAK structure, showing:
- Huffman tree nodes
- Block information
- Sample string encodings

```bash
python tools/strings/uw-strings-analyzer.py strings.pak [--hexdump offset length]
```

### uw-strings-extractor.py

Extracts all strings to a text file:
```bash
python tools/strings/uw-strings-extractor.py
```

Outputs:
- `uw-strings.txt` - All strings in editable format
- `uw-strings-metadata.json` - Huffman tree and block metadata

### uw-strings-packer.py

Creates a new STRINGS.PAK from extracted files:
```bash
python tools/strings/uw-strings-packer.py
```

Requirements:
- `uw-strings.txt` - Edited string file
- `uw-strings-metadata.json` - Original metadata

### uw-strings-translator.py

Translates string blocks:
```bash
python tools/strings/uw-strings-translator.py uw-strings.txt uw-strings-de.txt --source English --target German
```

Options:
- `--backend` - Translation backend (ollama, transformers, dummy)
- `--model` - Specific translation model
- `--context` - Use contextual translation
- `--validate` - Check translation length limits

### uw_cnv_decompiler.py

Extracts and decompiles conversations:
```bash
python tools/conversations/uw_cnv_decompiler.py CNV.ARK -o output_dir
```

For a single binary:
```bash
python tools/conversations/uw_cnv_decompiler.py conversation_bin --decompile-binary
```

Outputs:
- `.bin` - Binary conversation data
- `.txt` - Conversation metadata and hex dump
- `.asm` - Decompiled assembly code

### uw_cnv_compiler.py

Compiles ASM to binary:
```bash
python tools/conversations/uw_cnv_compiler.py conversation.asm -o output.bin
```

Update CNV.ARK directly:
```bash
python tools/conversations/uw_cnv_compiler.py conversation.asm --update-cnv CNV.ARK
```

### uw_cnv_runner.py

Tests conversations without the game:
```bash
python tools/conversations/uw_cnv_runner.py conversation.asm --strings uw-strings.txt
```

Options:
- `--debug` - Show detailed execution trace

### UWScript (uwscript/)

Instead of writing assembly by hand, you can write conversations in UWScript, a small high-level language, and compile them to assembly:
```bash
python uwscript/uwscript_compiler.py my_conversation.uws      # writes my_conversation.asm + my_conversation_strings.txt
python uwscript/uwscript_vm.py my_conversation.uws            # compile and test in the terminal
```

See [uwscript/README.md](../uwscript/README.md) and the [language reference](../uwscript/docs/uwscript-language-spec.md).

---

By mastering this toolkit, you can create, test, and implement sophisticated conversations for Ultima Underworld. The provided tools handle every step of the development process, from extraction and analysis to testing and compilation.
