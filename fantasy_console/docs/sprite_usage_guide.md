# FantasyUW Sprite System - Usage Guide

## Overview

The FantasyUW fantasy console now supports sprite rendering using arrays defined in UWScript. This allows you to create pixel art sprites and animate them efficiently.

## Array Support in UWScript

### Array Declaration

Arrays are declared using square brackets with comma-separated values:

```uwscript
let my_array = [1, 2, 3, 4, 5]
let colors = [2, 4, 6, 8]
let empty_array = []
```

### Array Access

Access array elements using square bracket notation:

```uwscript
let first_element = my_array[0]  // Gets first element (1)
let third_element = my_array[2]  // Gets third element (3)
```

### Array Assignment

Assign values to array elements:

```uwscript
my_array[0] = 10      // Set first element to 10
colors[1] = 15        // Set second element to 15
```

#### Multi-dimensional Data
```uwscript
// Sprite data as array
let player_sprite = [
    16, 16,  // 16x16 sprite
    // 256 pixel values follow...
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    // ... more rows
]
```

## Sprite Format

Sprites are defined as arrays with a specific format:

```
[width, height, pixel_data...]
```

- **width**: Width of the sprite in pixels (1-64)
- **height**: Height of the sprite in pixels (1-64)  
- **pixel_data**: Row-by-row pixel color data (0-15)

### Color Palette

The fantasy console uses a 16-color palette:

| Index | Color        | RGB       |
|-------|-------------|-----------|
| 0     | Black       | (0,0,0)   |
| 1     | White       | (255,255,255) |
| 2     | Red         | (255,0,0) |
| 3     | Green       | (0,255,0) |
| 4     | Blue        | (0,0,255) |
| 5     | Yellow      | (255,255,0) |
| 6     | Magenta     | (255,0,255) |
| 7     | Cyan        | (0,255,255) |
| 8     | Gray        | (128,128,128) |
| 9     | Light Gray  | (192,192,192) |
| 10    | Dark Red    | (128,0,0) |
| 11    | Dark Green  | (0,128,0) |
| 12    | Dark Blue   | (0,0,128) |
| 13    | Dark Yellow | (128,128,0) |
| 14    | Dark Magenta| (128,0,128) |
| 15    | Dark Cyan   | (0,128,128) |

## Sprite Functions

### draw_sprite(x, y, sprite_data)

Draws a sprite at the specified position.

**Parameters:**
- `x`: X coordinate (0-127)
- `y`: Y coordinate (0-127)
- `sprite_data`: Array containing sprite data

**Example:**
```uwscript
let player_sprite = [
    8, 8,                    // 8x8 sprite
    0, 0, 1, 1, 1, 1, 0, 0,  // Row 0
    0, 1, 1, 2, 2, 1, 1, 0,  // Row 1 (red eyes)
    0, 1, 1, 1, 1, 1, 1, 0,  // Row 2
    0, 1, 1, 3, 3, 1, 1, 0,  // Row 3 (green smile)
    0, 1, 1, 1, 1, 1, 1, 0,  // Row 4
    0, 1, 1, 1, 1, 1, 1, 0,  // Row 5
    0, 1, 1, 1, 1, 1, 1, 0,  // Row 6
    0, 0, 1, 1, 1, 1, 0, 0   // Row 7
]

draw_sprite(50, 50, player_sprite)
```

## Transparency

Color 0 (black) is treated as transparent when drawing sprites. This allows you to create sprites with irregular shapes.

## Example Sprites

### Simple 4x4 Heart
```uwscript
let heart = [
    4, 4,
    0, 2, 0, 2,  // Red heart shape
    2, 2, 2, 2,
    2, 2, 2, 2,
    0, 2, 0, 0
]
```

### 8x8 Smiley Face
```uwscript
let smiley = [
    8, 8,
    0, 0, 5, 5, 5, 5, 0, 0,  // Yellow circle
    0, 5, 5, 5, 5, 5, 5, 0,
    5, 5, 2, 5, 5, 2, 5, 5,  // Red eyes
    5, 5, 5, 5, 5, 5, 5, 5,
    5, 2, 5, 5, 5, 5, 2, 5,  // Red smile
    5, 5, 2, 2, 2, 2, 5, 5,
    0, 5, 5, 5, 5, 5, 5, 0,
    0, 0, 5, 5, 5, 5, 0, 0
]
```

## Animation Techniques

### Frame-based Animation

Create multiple sprite arrays for different animation frames:

```uwscript
let frame1 = [8, 8, /* frame 1 data */]
let frame2 = [8, 8, /* frame 2 data */]
let frame3 = [8, 8, /* frame 3 data */]

let current_frame = 0
let frame_timer = 0

label animation_loop
    frame_timer += 1
    if frame_timer >= 10  // Change frame every 10 game frames
        frame_timer = 0
        current_frame += 1
        if current_frame >= 3
            current_frame = 0
        endif
    endif
    
    if current_frame == 0
        draw_sprite(x, y, frame1)
    elseif current_frame == 1
        draw_sprite(x, y, frame2)
    else
        draw_sprite(x, y, frame3)
    endif
    
    flip_display()
    goto animation_loop
```

### Movement Animation

Combine sprite animation with position changes:

```uwscript
let sprite_x = 10
let direction = 1

label move_loop
    clear_screen(0)
    draw_sprite(sprite_x, 50, my_sprite)
    
    sprite_x += direction
    if sprite_x >= 120
        direction = -1
    endif
    if sprite_x <= 0
        direction = 1
    endif
    
    flip_display()
    goto move_loop
```

## Complete Examples

### Interactive Sprite Demo

Save as `interactive_demo.uws`:

```uwscript
let KEY_UP = 0
let KEY_DOWN = 1  
let KEY_LEFT = 2
let KEY_RIGHT = 3
let KEY_ESCAPE = 6

let player = [
    8, 8,
    0, 0, 3, 3, 3, 3, 0, 0,
    0, 3, 3, 1, 1, 3, 3, 0,
    3, 3, 1, 2, 2, 1, 3, 3,
    3, 3, 1, 1, 1, 1, 3, 3,
    3, 3, 1, 2, 2, 1, 3, 3,
    3, 3, 1, 1, 1, 1, 3, 3,
    0, 3, 3, 1, 1, 3, 3, 0,
    0, 0, 3, 3, 3, 3, 0, 0
]

let x = 64
let y = 64
let running = true

say "Use arrow keys to move! Press ESC to exit."

label game_loop
    clear_screen(0)
    
    // Handle input
    if is_key_pressed(KEY_UP)
        y -= 2
    endif
    if is_key_pressed(KEY_DOWN)
        y += 2
    endif
    if is_key_pressed(KEY_LEFT)
        x -= 2
    endif
    if is_key_pressed(KEY_RIGHT)
        x += 2
    endif
    if is_key_pressed(KEY_ESCAPE)
        running = false
    endif
    
    // Keep player on screen
    if x < 0
        x = 0
    endif
    if x > 120
        x = 120
    endif
    if y < 0
        y = 0
    endif
    if y > 120
        y = 120
    endif
    
    // Draw player
    draw_sprite(x, y, player)
    flip_display()
    
    if running
        goto game_loop
    endif

say "Thanks for playing!"
exit
```

### Sprite Animation

Save as `animation_demo.uws`:

```uwscript
// Two animation frames
let frame1 = [4, 4, 5, 5, 5, 5, 5, 2, 2, 5, 5, 2, 2, 5, 5, 5, 5, 5]
let frame2 = [4, 4, 5, 5, 5, 5, 5, 4, 4, 5, 5, 4, 4, 5, 5, 5, 5, 5]

let current_frame = 0
let timer = 0
let x = 10

label animate
    clear_screen(7)
    
    // Switch frames
    timer += 1
    if timer >= 30
        timer = 0
        current_frame += 1
        if current_frame >= 2
            current_frame = 0
        endif
    endif
    
    // Draw current frame
    if current_frame == 0
        draw_sprite(x, 60, frame1)
    else
        draw_sprite(x, 60, frame2)
    endif
    
    // Move sprite
    x += 1
    if x > 124
        x = 0
    endif
    
    flip_display()
    goto animate
```

## Troubleshooting

### Debug Output

Enable debug mode to see detailed execution:
```bash
python fantasy_console.py program.asm --debug
```

This will show:
- VM instruction execution
- Function calls with parameters
- Sprite drawing operations
- Memory operations

### Common Issues

**Sprite not appearing:**
- Check that width × height = number of pixel data elements
- Verify coordinates are within screen bounds (0-127)
- Make sure sprite data contains valid colors (0-15)

**Array errors:**
- Arrays must be declared with `let`
- Array indices start at 0
- Make sure array is big enough for the index you're accessing

**Compilation errors:**
- Check syntax: arrays use `[]`, function calls use `()`
- Make sure all statements end with newlines
- Verify all `if` statements have matching `endif`

### Performance Tips

1. **Pre-calculate sprites**: Define all sprite data at the beginning of your program
2. **Limit sprite size**: Larger sprites (>16x16) may impact performance
3. **Use transparency wisely**: Color 0 pixels are skipped, which can improve performance
4. **Batch drawing**: Group multiple sprite draws before calling `flip_display()`

## Assembly Code Generated

When you use `draw_sprite()`, the UWScript compiler generates (globals start at address 96):

```assembly
; let sprite = [2, 1, 3, 4] fills addresses 96-99; x is at 100, y at 101
; draw_sprite(x, y, sprite)
PUSHI 104                     ; temporary slot ...
PUSHI 96                      ; ... that holds the sprite's address
STO
PUSHI 100                     ; pointer to x
PUSHI 101                     ; pointer to y
PUSHI 104                     ; pointer to the sprite address
PUSHI 3                       ; 3 arguments
CALLI 106                     ; draw_sprite (ID 106)
POP                           ; the caller removes the argument count ...
POP                           ; ... and the three pointers
POP
POP
```

The sprite data is stored in consecutive memory locations as defined in your array.

## Debugging Sprites

If your sprites don't appear correctly:

1. **Check dimensions**: Ensure width × height matches the number of pixel data elements
2. **Verify colors**: Make sure all color values are 0-15
3. **Check coordinates**: Ensure x,y coordinates are within screen bounds (0-127)
4. **Test with simple sprites**: Start with a small solid-color sprite to verify basic functionality

## Complete Example Program

See `sprite_demo.uws` for a complete working example that demonstrates:
- Multiple sprite definitions
- Player movement
- Animation effects
- Input handling
- Game loop structure

This sprite system provides a solid foundation for creating retro-style games and animations in the FantasyUW console!
