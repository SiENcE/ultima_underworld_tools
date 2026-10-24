# FantasyUW: A Fantasy Console Concept

## Overview

FantasyUW is a fantasy console built on top of the Ultima Underworld conversation VM and UWScript compiler. It extends the original 16-bit stack-based virtual machine with modular import functions for graphics, sound, input, and I/O operations while maintaining the elegant simplicity of the original architecture.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FantasyUW Console                        │
├─────────────────────────────────────────────────────────────┤
│  UWScript Source (.uws)                                     │
│  ├─ Game Logic      ├─ Graphics Calls    ├─ Sound Calls    │
│  ├─ Input Handling  ├─ File Operations   ├─ Math Functions │
└─────────────────────┬───────────────────────────────────────┘
                      │ Compilation
                      ▼
┌─────────────────────────────────────────────────────────────┐
│               UWScript Compiler                             │
│  ┌─────────────────┬─────────────────┬─────────────────┐   │
│  │   Lexer         │    Parser       │  Code Generator │   │
│  │                 │                 │                 │   │
│  └─────────────────┴─────────────────┴─────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │ Generates
                      ▼
┌─────────────────────────────────────────────────────────────┐
│             UW Assembly + Strings                           │
│  Assembly Instructions        String Literals              │
│  ├─ Core VM Opcodes          ├─ Game Text                  │
│  ├─ CALLI Instructions       ├─ UI Strings                 │
│  └─ Memory Operations        └─ Debug Messages             │
└─────────────────────┬───────────────────────────────────────┘
                      │ Execution
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 FantasyUW VM                                │
│  ┌─────────────────────────────────────────────────────────┤
│  │                Core UW VM                               │
│  │  ┌─────────────┬─────────────┬─────────────┬──────────┐ │
│  │  │   Memory    │    Stack    │   Opcodes   │ Strings  │ │
│  │  │   64K RAM   │  Operations │  Handlers   │ Manager  │ │
│  │  └─────────────┴─────────────┴─────────────┴──────────┘ │
│  └─────────────────────────────────────────────────────────┤
│  │            Import Function Router                       │
│  │        (CALLI Instruction Handler)                     │
│  └─────────────────────────────────────────────────────────┤
│  │                Console Modules                          │
│  │  ┌──────────┬──────────┬──────────┬──────────┬────────┐ │
│  │  │Graphics  │  Sound   │  Input   │   File   │  Math  │ │
│  │  │ Module   │  Module  │  Module  │  Module  │ Module │ │
│  │  │          │          │          │          │        │ │
│  │  │ ID:100+  │ ID:200+  │ ID:300+  │ ID:400+  │ID:500+ │ │
│  │  └──────────┴──────────┴──────────┴──────────┴────────┘ │
│  └─────────────────────────────────────────────────────────┤
│  │              Hardware Abstraction                       │
│  │  ┌──────────┬──────────┬──────────┬──────────┬────────┐ │
│  │  │ Display  │  Audio   │Keyboard/ │   Disk   │ Timer  │ │
│  │  │ Buffer   │ Output   │ Gamepad  │   I/O    │        │ │
│  │  └──────────┴──────────┴──────────┴──────────┴────────┘ │
│  └─────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
```

## Core Specifications

### Display
- **Resolution**: 128x128 pixels (configurable)
- **Color Depth**: 16 colors (4-bit palette)
- **Memory**: 8KB video RAM + 64 bytes palette
- **Sprites**: 8x8 and 16x16 sprite support
- **Tilemap**: 16x16 tile background layer

### Audio
- **Channels**: 4 simultaneous audio channels
- **Waveforms**: Square, triangle, sawtooth, noise
- **Sample Rate**: 22050 Hz
- **Effects**: Volume, pitch bend, basic filters

### Input
- **Keyboard**: Full keyboard support
- **Gamepad**: 8-button gamepad (D-pad, A, B, X, Y)
- **Mouse**: Basic mouse support (optional)

### Memory
- **RAM**: 64KB addressable space
- **Cartridge**: Up to 512KB ROM space
- **Save Data**: 1KB persistent storage

## Import Function Modules

### Graphics Module (Function IDs 100-199)

```python
# Core graphics functions
FUNC_GFX_CLEAR = 100           # Clear screen
FUNC_GFX_PIXEL = 101           # Set/get pixel
FUNC_GFX_LINE = 102            # Draw line
FUNC_GFX_RECT = 103            # Draw rectangle
FUNC_GFX_FILL_RECT = 104       # Draw filled rectangle
FUNC_GFX_CIRCLE = 105          # Draw circle
FUNC_GFX_SPRITE = 106          # Draw sprite
FUNC_GFX_PRINT = 107           # Print text
FUNC_GFX_SET_PALETTE = 108     # Set color palette
FUNC_GFX_FLIP = 109            # Flip display buffer

# Advanced graphics
FUNC_GFX_TILEMAP = 110         # Draw tilemap
FUNC_GFX_SCROLL = 111          # Scroll screen
FUNC_GFX_CLIP = 112            # Set clipping region
```

### Sound Module (Function IDs 200-299)

```python
# Sound functions
FUNC_SND_PLAY_TONE = 200       # Play tone
FUNC_SND_PLAY_SAMPLE = 201     # Play sound sample
FUNC_SND_PLAY_MUSIC = 202      # Play background music
FUNC_SND_STOP = 203            # Stop sound/music
FUNC_SND_SET_VOLUME = 204      # Set channel volume
FUNC_SND_LOAD_SAMPLE = 205     # Load sound sample
```

### Input Module (Function IDs 300-399)

```python
# Input functions
FUNC_INPUT_KEY_PRESSED = 300   # Check if key is pressed
FUNC_INPUT_KEY_RELEASED = 301  # Check if key was released
FUNC_INPUT_BUTTON = 302        # Check gamepad button
FUNC_INPUT_MOUSE = 303         # Get mouse state
FUNC_INPUT_TEXT = 304          # Get text input
```

### File Module (Function IDs 400-499)

```python
# File I/O functions
FUNC_FILE_OPEN = 400           # Open file
FUNC_FILE_READ = 401           # Read from file
FUNC_FILE_WRITE = 402          # Write to file
FUNC_FILE_CLOSE = 403          # Close file
FUNC_FILE_LOAD_SPRITE = 404    # Load sprite data
FUNC_FILE_SAVE_DATA = 405      # Save game data
FUNC_FILE_LOAD_DATA = 406      # Load game data
```

### Math Module (Function IDs 500-599)

```python
# Extended math functions
FUNC_MATH_SIN = 500            # Sine function
FUNC_MATH_COS = 501            # Cosine function
FUNC_MATH_SQRT = 502           # Square root
FUNC_MATH_ABS = 503            # Absolute value
FUNC_MATH_MIN = 504            # Minimum of two values
FUNC_MATH_MAX = 505            # Maximum of two values
FUNC_MATH_CLAMP = 506          # Clamp value between min/max
```

## UWScript Extensions

### New Keywords and Functions

```uwscript
// Graphics
clear_screen()
set_pixel(x, y, color)
draw_line(x1, y1, x2, y2, color)
draw_rect(x, y, width, height, color)
draw_sprite(sprite_id, x, y)
print_text(text, x, y, color)

// Sound
play_tone(frequency, duration, channel)
play_sample(sample_id, channel)
play_music(music_id)
stop_sound(channel)

// Input
let key_pressed = is_key_pressed(KEY_SPACE)
let button_a = is_button_pressed(BTN_A)

// File operations
load_sprite_data("player.spr")
save_game_data(slot, data)
let data = load_game_data(slot)

// Math
let angle_sin = sin(angle)
let distance = sqrt(dx*dx + dy*dy)
```

### Example Game Loop

```uwscript
// Simple game example
let player_x = 64
let player_y = 64
let score = 0
let game_running = true

// Game initialization
clear_screen()
load_sprite_data("sprites.dat")

label game_loop
    // Clear screen
    clear_screen()
    
    // Handle input
    if is_key_pressed(KEY_LEFT) and player_x > 0
        player_x -= 1
    endif
    
    if is_key_pressed(KEY_RIGHT) and player_x < 120
        player_x += 1
    endif
    
    if is_key_pressed(KEY_UP) and player_y > 0
        player_y -= 1
    endif
    
    if is_key_pressed(KEY_DOWN) and player_y < 120
        player_y += 1
    endif
    
    // Update game logic
    score += 1
    
    // Draw everything
    draw_sprite(0, player_x, player_y)  // Player sprite
    print_text("Score: " + score, 8, 8, 15)
    
    // Flip display buffer
    flip_display()
    
    // Check for exit
    if is_key_pressed(KEY_ESCAPE)
        game_running = false
    endif
    
    if game_running
        goto game_loop
    endif

// Game over
say "Game Over! Final Score: " + score
exit
```

## Implementation Strategy

### Phase 1: Core Graphics
- Implement basic display buffer and pixel operations
- Add simple drawing functions (pixel, line, rectangle)
- Create color palette system
- Basic text rendering

### Phase 2: Input System
- Keyboard input handling
- Basic gamepad support
- Event queue system

### Phase 3: Sound System
- Simple tone generation
- Sound effect playback
- Basic music system

### Phase 4: Advanced Features
- Sprite system
- Tilemap support
- File I/O operations
- Save/load functionality

### Phase 5: Development Tools
- Sprite editor integration
- Sound editor
- Map editor
- Debugger enhancements

## Module Structure

Each module would be implemented as a separate Python class that extends the base VM:

```python
class GraphicsModule:
    def __init__(self, vm):
        self.vm = vm
        self.display_buffer = bytearray(128 * 128)  # 128x128 pixels
        self.palette = [0] * 16  # 16 color palette
        
    def handle_function(self, func_id):
        if func_id == 100:  # FUNC_GFX_CLEAR
            self.clear_screen()
        elif func_id == 101:  # FUNC_GFX_PIXEL
            self.set_pixel()
        # ... more functions
    
    def clear_screen(self):
        self.display_buffer = bytearray(128 * 128)
    
    def set_pixel(self):
        color = self.vm.pop()
        y = self.vm.pop()
        x = self.vm.pop()
        if 0 <= x < 128 and 0 <= y < 128:
            self.display_buffer[y * 128 + x] = color & 0xF
```

## Benefits

1. **Familiar Architecture**: Developers familiar with the UW VM can easily transition
2. **Modular Design**: Features can be added incrementally without breaking existing code
3. **High-Level Language**: UWScript provides modern programming constructs
4. **Extensible**: New modules can be added without modifying the core VM
5. **Educational**: Simple enough for learning game development
6. **Retro Feel**: Constraints encourage creative solutions

## Development Environment

The FantasyUW development environment would include:

- **Code Editor**: Syntax highlighting for UWScript
- **Compiler**: Enhanced UWScript compiler with console-specific functions
- **Emulator**: Real-time testing environment
- **Asset Tools**: Sprite and sound editors
- **Debugger**: Step-through debugging with memory inspection
- **Export Tools**: Create distributable cartridge files

This fantasy console concept leverages the robust foundation of the UW VM while adding the multimedia capabilities needed for game development, creating a unique retro computing experience that's both powerful and approachable.