# FantasyUW: A Fantasy Console Based on Ultima Underworld VM

![UW Fantasy Console](docs/uw_vm_console.png)

FantasyUW is a fantasy console based on the Ultima Underworld VM, extending it with graphics, input, and sound capabilities while maintaining the core stack-based architecture.

## Enhanced Version Features

The enhanced version includes:
- **Sprite Data Support**: Draw sprites from structured data arrays
- **Circle Drawing**: Added circle primitive
- **Math Functions**: Sin, Cos, and Square Root for more advanced graphics
- **Sound Generation**: Basic tone generation
- **Key Release Detection**: Detect when keys are released in addition to presses

## Installation

```bash
pip install -r requirements.txt
```

The console imports the VM (`uw_cnv_runner.py`) and the compiler (`uwscript_compiler.py`) from [`../uwscript`](../uwscript/README.md), so keep the two folders side by side.

## How to Use

1. Write your program in [UWScript](../uwscript/README.md) (see `samples/`), or directly in UW assembly.

2. Compile and run it in one step (Windows):
   ```
   start.bat samples\fantasy_pong.uws
   ```
   or do it manually:
   ```
   python ../uwscript/uwscript_compiler.py samples/fantasy_pong.uws -o output.asm -s uw-strings.txt
   python fantasy_console.py output.asm --strings uw-strings.txt
   ```
   `standalone_jumprun.py` is a self-contained example that compiles and runs an embedded game.

3. Controls:
   - Arrow keys: Move the rectangle
   - Space: Change color
   - Escape: Exit the program

## Performance and Instruction Limits

### The 5000-Step Safety Limit

FantasyUW implements a safety limit of **5000 VM instructions per frame** to prevent infinite loops and maintain responsive frame rates. When this limit is exceeded, you'll see:

```
Warning: Reached max steps per frame (5000)
```

### Why the Limit Exists

The limit serves several purposes:
1. **Prevents infinite loops** from freezing the console
2. **Maintains consistent frame rates** (typically 30 FPS)
3. **Ensures responsive input handling**
4. **Prevents runaway programs** from consuming excessive CPU

### Understanding Instruction Count

Not all operations are equal in terms of instruction cost:

#### Low-Cost Operations (~1-5 instructions)
```uwscript
let x = 10        // Variable assignment: ~4 instructions
x = x + 1         // Simple arithmetic: ~5 instructions
if x > 5          // Simple comparison: ~3 instructions
```

#### Medium-Cost Operations (~10-20 instructions)
```uwscript
clear_screen(0)         // Simple graphics function: ~7 instructions
flip_display()          // Display update: ~2 instructions
is_key_pressed(KEY_UP)  // Input check: ~15 instructions
```

#### High-Cost Operations (~20-50+ instructions)
```uwscript
draw_circle(x, y, r, color)     // Complex graphics: ~25 instructions
random(100)                     // Function with complex logic: ~15 instructions
say "Hello " + player_name      // String processing: ~10+ instructions
```

#### Very High-Cost Operations (100+ instructions per iteration)
```uwscript
while i < 10
    let x = random(100) + 10    // ~20 instructions
    let y = random(100) + 10    // ~20 instructions  
    let r = random(20) + 5      // ~20 instructions
    draw_circle(x, y, r, 2)     // ~25 instructions
    i = i + 1                   // ~5 instructions
    // Total per iteration: ~90 instructions
    // 10 iterations: ~900 instructions
endwhile
```

### Real-World Example: Graphics-Heavy Program

Here's a program that can exceed the 5000-instruction limit:

```uwscript
let running = true
let effect = 0

function draw_many_circles()
    let i = 0
    while i < 8  // 8 circles = ~720 instructions
        let x = random(100) + 14    // ~20 instructions
        let y = random(80) + 20     // ~20 instructions
        let radius = random(20) + 5 // ~20 instructions
        draw_circle(x, y, radius, 2) // ~25 instructions
        i = i + 1                   // ~5 instructions
        // Total per iteration: ~90 instructions
    endwhile
endfunction

label game_loop
    clear_screen(0)              // ~7 instructions
    
    if is_key_pressed(6)         // ~18 instructions
        running = false
    endif
    
    if is_key_pressed(4)         // ~18 instructions  
        effect = effect + 1
    endif
    
    say "Effect: " + effect      // ~10 instructions
    
    draw_many_circles()          // ~720 instructions
    draw_line(0, 0, 127, 127, 15) // ~25 instructions
    draw_line(0, 127, 127, 0, 15) // ~25 instructions
    
    flip_display()               // ~2 instructions
    // Total per frame: ~825 base instructions
    // With VM overhead: potentially 2000-5000+ instructions
    
    if running
        goto game_loop
    endif
exit
```

**This program can easily exceed 5000 instructions** due to:
- Multiple function calls with stack overhead
- Complex graphics operations
- Temporary variable management
- Loop execution with function calls inside

### Diagnosing Performance Issues

Enable debug mode to see instruction execution:
```bash
python fantasy_console.py program.asm --debug
```

Look for patterns like:
- **Repeated temp variable allocation**: `PUSHI_EFF 1000`, `PUSHI_EFF 1001`, etc.
- **Excessive function calls**: Many `CALLI` instructions in a single frame
- **Complex loops**: Loops with function calls inside them

### Performance Optimization Strategies

#### 1. Reduce Work Per Frame
```uwscript
// Instead of drawing 10 circles per frame:
while i < 10
    draw_circle(random(100), random(100), 5, 2)
    i = i + 1
endwhile

// Draw fewer circles:
while i < 3
    draw_circle(random(100), random(100), 5, 2)
    i = i + 1
endwhile
```

#### 2. Break Up Heavy Operations
```uwscript
// Add frame breaks in long loops:
while i < 10
    draw_circle(random(100), random(100), 5, 2)
    i = i + 1
    
    // Break every 3 circles
    if i % 3 == 0
        flip_display()
    endif
endwhile
```

#### 3. Move Heavy Work to Functions
```uwscript
// Put flip_display() inside heavy functions:
function draw_scene()
    // ... heavy graphics work ...
    flip_display()  // Break execution here
endfunction

label game_loop
    handle_input()
    draw_scene()  // Execution breaks inside this function
    goto game_loop
```

#### 4. Use Simpler Graphics Operations
```uwscript
// Instead of many circles:
while i < 10
    draw_circle(x, y, r, color)  // ~25 instructions each
    i = i + 1
endwhile

// Use simpler operations:
while i < 10
    set_pixel(x, y, color)       // ~7 instructions each
    i = i + 1
endwhile
```

### Adjusting the Instruction Limit

For complex programs that legitimately need more instructions per frame, you can increase the limit:

```python
# In fantasy_console.py, modify this line:
self.max_steps_per_frame = 10000  # Increased from 5000
```

**Trade-offs:**
- ✅ Allows more complex per-frame operations
- ❌ Potential for lower frame rates
- ❌ Risk of unresponsive input
- ❌ Higher CPU usage

### Performance Guidelines Summary

1. **Keep loops small** - Avoid large loops without frame breaks
2. **Limit function calls** - Each call has significant overhead
3. **Use flip_display() strategically** - It breaks instruction counting
4. **Profile with debug mode** - Identify bottlenecks
5. **Consider the 5000-instruction budget** - Design accordingly

## Function Reference

The fantasy console extends the UW VM with these functions:

### Graphics Functions (100-199)
- **100: GFX_CLEAR** - Clear screen with a color (~7 instructions)
- **101: GFX_PIXEL** - Set a pixel (~7 instructions)
- **102: GFX_LINE** - Draw a line (~25 instructions)
- **103: GFX_RECT** - Draw a rectangle outline (~20 instructions)
- **104: GFX_FILL_RECT** - Draw a filled rectangle (~15 instructions)
- **105: GFX_CIRCLE** - Draw a circle outline (~25 instructions)
- **106: GFX_SPRITE** - Draw a sprite from sprite data (~30+ instructions)
- **107: GFX_PRINT** - Print text on screen (~10 instructions)
- **109: GFX_FLIP** - Update the display (~2 instructions) **[FRAME BREAK]**

### Sound Functions (200-299)
- **200: SND_PLAY_TONE** - Play a tone with specified frequency and duration (~10 instructions)

### Input Functions (300-399)
- **300: INPUT_KEY_PRESSED** - Check if a key is currently pressed (~15 instructions)
- **301: INPUT_KEY_RELEASED** - Check if a key was just released (~15 instructions)

### Math Functions (500-599)
- **501: MATH_SIN** - Calculate sine (~8 instructions)
- **502: MATH_COS** - Calculate cosine (~8 instructions)
- **503: MATH_SQRT** - Calculate square root (~8 instructions)

### System Functions (900-999)
- **900: SYS_DELAY** - Delay execution for specified milliseconds (~5 instructions)

## Function Mapping for UWScript compiler

The UWScript compiler maps high-level functions to VM function IDs:

```
clear_screen(color) -> CALLI 100
set_pixel(x, y, color) -> CALLI 101
draw_line(x1, y1, x2, y2, color) -> CALLI 102
draw_rect(x, y, width, height, color) -> CALLI 103
fill_rect(x, y, width, height, color) -> CALLI 104
draw_circle(x, y, radius, color) -> CALLI 105
draw_sprite(x, y, sprite_data) -> CALLI 106
print(x, y, text, color) -> CALLI 107
flip_display() -> CALLI 109
play_tone(frequency, duration, channel) -> CALLI 200
is_key_pressed(key_code) -> CALLI 300
is_key_released(key_code) -> CALLI 301
math_sin(angle) -> CALLI 501
math_cos(angle) -> CALLI 502
math_sqrt(value) -> CALLI 503
sys_delay(milliseconds) -> CALLI 900
```

### Key Codes
- 0: UP arrow
- 1: DOWN arrow
- 2: LEFT arrow
- 3: RIGHT arrow
- 4: SPACE
- 5: RETURN/ENTER
- 6: ESCAPE

## Sprite Data Format

The enhanced sprite system uses a structured data format:

```
sprite_data[0]: width
sprite_data[1]: height
sprite_data[2...]: pixel data (row by row)
```

Pixel data values:
- 0: Transparent (doesn't overwrite background)
- 1-15: Color index from palette

Example of creating a 8x8 sprite in UWScript:
```
// Create an 8x8 sprite (checkerboard pattern)
let sprite = [
    8, 8,  // Width, Height
    1, 0, 1, 0, 1, 0, 1, 0,  // Row 1
    0, 1, 0, 1, 0, 1, 0, 1,  // Row 2
    1, 0, 1, 0, 1, 0, 1, 0,  // Row 3
    0, 1, 0, 1, 0, 1, 0, 1,  // Row 4
    1, 0, 1, 0, 1, 0, 1, 0,  // Row 5
    0, 1, 0, 1, 0, 1, 0, 1,  // Row 6
    1, 0, 1, 0, 1, 0, 1, 0,  // Row 7
    0, 1, 0, 1, 0, 1, 0, 1   // Row 8
]

// Draw the sprite at position (50, 50)
draw_sprite(50, 50, sprite)
```

## Extending the Console

The modular design makes it easy to add new functions through the `imported_functions` dictionary. Some ideas for further extensions:

1. **Graphics**:
   - Add tilemap support
   - Implement proper text rendering
   - Add scaling and rotation for sprites

2. **Sound**:
   - Add simple music playback
   - Add sound effects library

3. **Input**:
   - Add mouse support
   - Implement gamepad input

4. **File I/O**:
   - Add save/load functionality
   - Implement asset loading

5. **Math**:
   - Add more advanced math functions
   - Implement collision detection

## Example: Drawing with Arrays

Here's an example using arrays to create and draw a simple sprite:

```
// Define colors
let BLACK = 0
let WHITE = 1
let RED = 2
let GREEN = 3
let BLUE = 4

// Create a simple face sprite (8x8)
let face_sprite = [
    8, 8,  // Width, Height
    0, 0, 1, 1, 1, 1, 0, 0,  // Row 1
    0, 1, 0, 0, 0, 0, 1, 0,  // Row 2
    1, 0, 1, 0, 1, 0, 0, 1,  // Row 3
    1, 0, 0, 0, 0, 0, 0, 1,  // Row 4
    1, 0, 1, 0, 0, 1, 0, 1,  // Row 5
    1, 0, 0, 1, 1, 0, 0, 1,  // Row 6
    0, 1, 0, 0, 0, 0, 1, 0,  // Row 7
    0, 0, 1, 1, 1, 1, 0, 0   // Row 8
]

// Main program
clear_screen(BLACK)
let x = 60
let y = 60

// Game loop
label game_loop
    // Clear screen each frame
    clear_screen(BLACK)
    
    // Draw the sprite
    draw_sprite(x, y, face_sprite)
    
    // Update position based on input
    if is_key_pressed(KEY_LEFT)
        x -= 1
    endif
    if is_key_pressed(KEY_RIGHT)
        x += 1
    endif
    if is_key_pressed(KEY_UP)
        y -= 1
    endif
    if is_key_pressed(KEY_DOWN)
        y += 1
    endif
    
    // Exit on ESCAPE
    if is_key_pressed(KEY_ESCAPE)
        goto game_end
    endif
    
    // Update display
    flip_display()
    
    // Continue loop
    goto game_loop

label game_end
say "Goodbye!"
exit
```

## Further Reading

- [docs/sprite_usage_guide.md](docs/sprite_usage_guide.md) - Sprite system guide
- [docs/fantasy_console_concept.md](docs/fantasy_console_concept.md) - Design concept
- [samples/fantasy_game_astro_wars_readme.md](samples/fantasy_game_astro_wars_readme.md) - Walkthrough of a complete game
