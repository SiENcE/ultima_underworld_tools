#!/usr/bin/env python3
"""
Standalone Jump & Run Game for FantasyUW Console
Compile and run this directly without external dependencies
"""

import os
import sys
import tempfile

# The UWScript source code
GAME_SOURCE = '''// Minimal Horizontal Scrolling Jump & Run Game
// Key codes
let KEY_UP = 0
let KEY_LEFT = 2
let KEY_RIGHT = 3
let KEY_ESCAPE = 6

// Player sprite (8x8)
let player_sprite = [
    8, 8,
    0, 0, 1, 1, 1, 1, 0, 0,
    0, 1, 2, 1, 1, 2, 1, 0,
    1, 1, 1, 3, 3, 1, 1, 1,
    1, 1, 4, 4, 4, 4, 1, 1,
    1, 1, 4, 4, 4, 4, 1, 1,
    1, 1, 6, 1, 1, 6, 1, 1,
    0, 1, 6, 1, 1, 6, 1, 0,
    0, 0, 1, 0, 0, 1, 0, 0
]

// Ground tile (8x8)
let ground_tile = [
    8, 8,
    6, 6, 6, 6, 6, 6, 6, 6,
    6, 5, 6, 6, 6, 5, 6, 6,
    6, 6, 6, 5, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 5, 6,
    6, 5, 6, 6, 5, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 5, 6, 6, 6, 6, 5,
    6, 6, 6, 6, 6, 6, 6, 6
]

// Platform tile (8x8)
let platform_tile = [
    8, 8,
    8, 8, 8, 8, 8, 8, 8, 8,
    8, 9, 8, 8, 8, 9, 8, 8,
    8, 8, 8, 9, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 9, 8,
    8, 9, 8, 8, 9, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 9, 8, 8, 8, 8, 9,
    8, 8, 8, 8, 8, 8, 8, 8
]

// Small level map (16x12)
let level = [
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,2,2,2,0,0,0,2,2,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,2,2,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
]

// Player state
let player_x = 16
let player_y = 64
let player_vel_x = 0
let player_vel_y = 0
let on_ground = false
let camera_x = 0
let running = true

say "Arrow keys to move, UP to jump, ESC to quit"

label game_loop
    // Input
    player_vel_x = 0
    
    if is_key_pressed(KEY_LEFT)
        player_vel_x = -2
    endif
    
    if is_key_pressed(KEY_RIGHT)
        player_vel_x = 2
    endif
    
    if is_key_pressed(KEY_UP) and on_ground
        player_vel_y = -4
    endif
    
    if is_key_pressed(KEY_ESCAPE)
        running = false
    endif
    
    // Physics
    player_x += player_vel_x
    player_y += player_vel_y
    player_vel_y += 1
    
    // Collision
    let tile_x = player_x / 8
    let tile_y = (player_y + 7) / 8
    
    on_ground = false
    
    if tile_x >= 0 and tile_x < 16 and tile_y >= 0 and tile_y < 12
        let map_index = tile_y * 16 + tile_x
        let tile_type = level[map_index]
        
        if tile_type > 0 and player_vel_y >= 0
            player_y = tile_y * 8 - 8
            player_vel_y = 0
            on_ground = true
        endif
    endif
    
    // Bounds
    if player_x < 0
        player_x = 0
    endif
    if player_x > 120
        player_x = 120
    endif
    
    // Camera
    camera_x = player_x - 60
    if camera_x < 0
        camera_x = 0
    endif
    if camera_x > 0
        camera_x = 0
    endif
    
    // Draw
    clear_screen(7)
    
    let y = 0
    while y < 12
        let x = 0
        while x < 16
            let screen_x = x * 8 - camera_x
            let screen_y = y * 8
            
            if screen_x >= -8 and screen_x < 128
                let map_idx = y * 16 + x
                let tile_type = level[map_idx]
                
                if tile_type == 1
                    draw_sprite(screen_x, screen_y, ground_tile)
                elseif tile_type == 2
                    draw_sprite(screen_x, screen_y, platform_tile)
                endif
            endif
            
            x += 1
        endwhile
        y += 1
    endwhile
    
    let player_screen_x = player_x - camera_x
    draw_sprite(player_screen_x, player_y, player_sprite)
    
    flip_display()
    
    if running
        goto game_loop
    endif

say "Game Over!"
exit'''

def compile_and_run():
    """Compile the UWScript and run it in the fantasy console"""
    
    # Check if we can import the required modules
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, here)
        sys.path.insert(0, os.path.join(here, '..', 'uwscript'))
        from uwscript_compiler import compile_uwscript
        from fantasy_console import FantasyConsole
    except ImportError as e:
        print(f"Error: Could not import required modules: {e}")
        print("Make sure fantasy_console.py is next to this script and uwscript_compiler.py is in ../uwscript")
        return False
    
    print("=== FantasyUW Jump & Run Game ===")
    print("Compiling UWScript...")
    
    try:
        # Compile the UWScript source
        result = compile_uwscript(GAME_SOURCE, block_id=1)
        
        # Create temporary files for assembly and strings
        with tempfile.NamedTemporaryFile(mode='w', suffix='.asm', delete=False) as asm_file:
            asm_file.write(result['assembly'])
            asm_path = asm_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as strings_file:
            strings_file.write(result['strings'])
            strings_path = strings_file.name
        
        print("Starting game...")
        print("\nControls:")
        print("- Left/Right arrows: Move")
        print("- Up arrow: Jump")
        print("- ESC: Quit")
        print("\nClose the game window or press ESC to exit.")
        
        # Create and run the fantasy console
        console = FantasyConsole(debug=False)
        
        # Load the strings and assembly
        console.load_string_blocks(strings_path)
        if not console.parse_asm(asm_path):
            print("Error: Failed to parse assembly code")
            return False
        
        console.initialize_memory()
        
        # Run the game
        console.execute_game_loop()
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up temporary files
        try:
            if 'asm_path' in locals():
                os.unlink(asm_path)
            if 'strings_path' in locals():
                os.unlink(strings_path)
        except:
            pass

def show_instructions():
    """Show game instructions and features"""
    print("=== Jump & Run Game Features ===")
    print()
    print("Game Elements:")
    print("- Player: Colorful character sprite with red eyes and blue shirt")
    print("- Ground: Brown dirt tiles at the bottom")
    print("- Platforms: Gray stone platforms you can jump on")
    print("- Sky: Cyan background")
    print()
    print("Physics:")
    print("- Gravity pulls the player down")
    print("- Jump only works when on solid ground")
    print("- Horizontal scrolling camera follows the player")
    print()
    print("Level Design:")
    print("- 16x12 tile map (128x96 pixels)")
    print("- Each tile is 8x8 pixels")
    print("- Platforms placed at different heights for platforming")
    print("- Solid ground at the bottom prevents falling off the world")
    print()

if __name__ == "__main__":
    show_instructions()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("\nTo run the game, simply execute this script without arguments:")
        print("python standalone_jumprun.py")
        sys.exit(0)
    
    if compile_and_run():
        print("Game finished successfully!")
    else:
        print("Game failed to run. Check the error messages above.")
        sys.exit(1)
