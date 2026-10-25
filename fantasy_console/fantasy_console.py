# fantasy_console.py - Enhanced version with sprite data support

import pygame
import sys
import os
import argparse
import time

# The VM and the UWScript compiler live in ../uwscript
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uwscript'))
from uwscript_vm import UltimaUnderworldVM, load_program

class FantasyConsole(UltimaUnderworldVM):
    """Fantasy console based on the Ultima Underworld VM"""
    
    def __init__(self, debug=False):
        super().__init__(debug)
        
        # Initialize pygame
        pygame.init()
        
        # Initialize sound
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        except:
            print("Warning: Sound initialization failed")
        
        # Display settings
        self.screen_width = 128
        self.screen_height = 128
        self.pixel_scale = 4  # Scale up for visibility
        self.screen = pygame.display.set_mode((self.screen_width * self.pixel_scale, 
                                               self.screen_height * self.pixel_scale))
        pygame.display.set_caption("FantasyUW Console")
        
        # Color palette (16 colors)
        self.palette = [
            (0, 0, 0),          # 0: Black
            (255, 255, 255),    # 1: White
            (255, 0, 0),        # 2: Red
            (0, 255, 0),        # 3: Green
            (0, 0, 255),        # 4: Blue
            (255, 255, 0),      # 5: Yellow
            (255, 0, 255),      # 6: Magenta
            (0, 255, 255),      # 7: Cyan
            (128, 128, 128),    # 8: Gray
            (192, 192, 192),    # 9: Light Gray
            (128, 0, 0),        # 10: Dark Red
            (0, 128, 0),        # 11: Dark Green
            (0, 0, 128),        # 12: Dark Blue
            (128, 128, 0),      # 13: Dark Yellow
            (128, 0, 128),      # 14: Dark Magenta
            (0, 128, 128),      # 15: Dark Cyan
        ]
        
        # Display buffer
        self.display_buffer = [[0 for _ in range(self.screen_width)] 
                               for _ in range(self.screen_height)]
        
        # Initialize string literals - this will be populated when loading programs
        self.string_literals = []
        
        # Register new imported functions
        self._register_console_functions()
        
        # Input state
        self.keys_pressed = set()
        self.previous_keys_pressed = set()
        
        # Game clock
        self.clock = pygame.time.Clock()
        self.fps = 30
        self.frame_delay = 1.0 / self.fps
        
        # Execution control
        self.max_steps_per_frame = 5000  # Prevent infinite loops
        self.display_update_requested = False
        
    def _register_console_functions(self):
        """Register new functions for the fantasy console"""
        # Keep original UW VM functions with their original IDs
        # (these are already registered in the parent class)
        
        # Graphics functions (100-199)
        self.imported_functions[100] = self.func_gfx_clear
        self.imported_functions[101] = self.func_gfx_pixel
        self.imported_functions[102] = self.func_gfx_line
        self.imported_functions[103] = self.func_gfx_rect
        self.imported_functions[104] = self.func_gfx_fill_rect
        self.imported_functions[105] = self.func_gfx_circle
        self.imported_functions[106] = self.func_gfx_sprite
        self.imported_functions[107] = self.func_gfx_print
        self.imported_functions[109] = self.func_gfx_flip
        
        # Sound functions (200-299)
        self.imported_functions[200] = self.func_snd_play_tone
        
        # Input functions (300-399)
        self.imported_functions[300] = self.func_input_key_pressed
        self.imported_functions[301] = self.func_input_key_released
        
        # Math functions (500-599)
        self.imported_functions[501] = self.func_math_sin
        self.imported_functions[502] = self.func_math_cos
        self.imported_functions[503] = self.func_math_sqrt
        
        # System functions (900-999)
        self.imported_functions[900] = self.func_sys_delay
    
    # Graphics functions
    
    def func_gfx_clear(self):
        """Clear the screen (ID: 100)"""
        args = self.pop()  # Number of arguments
        
        if args >= 1:
            ptr = self.pop()
            color = self.get_mem(ptr) & 0xF  # Ensure it's in range 0-15
        else:
            color = 0  # Default to black
        
        # Clear buffer
        for y in range(self.screen_height):
            for x in range(self.screen_width):
                self.display_buffer[y][x] = color
        
        self.log(f"GFX_CLEAR: Cleared screen with color {color}")
        self.result_register = 1  # Success
        
    def func_gfx_pixel(self):
        """Set a pixel (ID: 101)"""
        args = self.pop()  # Number of arguments
        
        if args >= 3:
            ptr_color = self.pop()
            ptr_y = self.pop()
            ptr_x = self.pop()
            
            color = self.get_mem(ptr_color) & 0xF
            y = self.get_mem(ptr_y)
            x = self.get_mem(ptr_x)
            
            if 0 <= x < self.screen_width and 0 <= y < self.screen_height:
                self.display_buffer[y][x] = color
                
            self.log(f"GFX_PIXEL: Set pixel at ({x}, {y}) to color {color}")
            self.result_register = 1  # Success
        else:
            self.log("GFX_PIXEL: Not enough arguments")
            self.result_register = 0  # Failure
        
    def func_gfx_line(self):
        """Draw a line (ID: 102)"""
        args = self.pop()  # Number of arguments
        
        if args >= 5:
            ptr_color = self.pop()
            ptr_y2 = self.pop()
            ptr_x2 = self.pop()
            ptr_y1 = self.pop()
            ptr_x1 = self.pop()
            
            color = self.get_mem(ptr_color) & 0xF
            y2 = self.get_mem(ptr_y2)
            x2 = self.get_mem(ptr_x2)
            y1 = self.get_mem(ptr_y1)
            x1 = self.get_mem(ptr_x1)
            
            # Clip coordinates to screen bounds
            x1 = max(0, min(self.screen_width - 1, x1))
            y1 = max(0, min(self.screen_height - 1, y1))
            x2 = max(0, min(self.screen_width - 1, x2))
            y2 = max(0, min(self.screen_height - 1, y2))
            
            # Simple line drawing (Bresenham's algorithm)
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            sx = 1 if x1 < x2 else -1
            sy = 1 if y1 < y2 else -1
            err = dx - dy
            
            while True:
                if 0 <= x1 < self.screen_width and 0 <= y1 < self.screen_height:
                    self.display_buffer[y1][x1] = color
                    
                if x1 == x2 and y1 == y2:
                    break
                    
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    x1 += sx
                if e2 < dx:
                    err += dx
                    y1 += sy
            
            self.log(f"GFX_LINE: Drew line from ({x1}, {y1}) to ({x2}, {y2}) with color {color}")
            self.result_register = 1  # Success
        else:
            self.log("GFX_LINE: Not enough arguments")
            self.result_register = 0  # Failure
        
    def func_gfx_rect(self):
        """Draw a rectangle outline (ID: 103)"""
        args = self.pop()  # Number of arguments
        
        if args >= 5:
            ptr_color = self.pop()
            ptr_height = self.pop()
            ptr_width = self.pop()
            ptr_y = self.pop()
            ptr_x = self.pop()
            
            color = self.get_mem(ptr_color) & 0xF
            height = max(1, self.get_mem(ptr_height))
            width = max(1, self.get_mem(ptr_width))
            y = self.get_mem(ptr_y)
            x = self.get_mem(ptr_x)
            
            # Draw horizontal lines
            for i in range(max(0, x), min(self.screen_width, x + width)):
                if 0 <= y < self.screen_height:
                    self.display_buffer[y][i] = color
                if 0 <= y + height - 1 < self.screen_height:
                    self.display_buffer[y + height - 1][i] = color
            
            # Draw vertical lines
            for i in range(max(0, y), min(self.screen_height, y + height)):
                if 0 <= x < self.screen_width:
                    self.display_buffer[i][x] = color
                if 0 <= x + width - 1 < self.screen_width:
                    self.display_buffer[i][x + width - 1] = color
            
            self.log(f"GFX_RECT: Drew rectangle at ({x}, {y}) with size {width}x{height} and color {color}")
            self.result_register = 1  # Success
        else:
            self.log("GFX_RECT: Not enough arguments")
            self.result_register = 0  # Failure
        
    def func_gfx_fill_rect(self):
        """Draw a filled rectangle (ID: 104)"""
        args = self.pop()  # Number of arguments
        
        if args >= 5:
            ptr_color = self.pop()
            ptr_height = self.pop()
            ptr_width = self.pop()
            ptr_y = self.pop()
            ptr_x = self.pop()
            
            color = self.get_mem(ptr_color) & 0xF
            height = max(1, self.get_mem(ptr_height))
            width = max(1, self.get_mem(ptr_width))
            y = self.get_mem(ptr_y)
            x = self.get_mem(ptr_x)
            
            # Fill rectangle - ensure coordinates are interpreted correctly
            for j in range(max(0, y), min(self.screen_height, y + height)):
                for i in range(max(0, x), min(self.screen_width, x + width)):
                    self.display_buffer[j][i] = color
            
            self.log(f"GFX_FILL_RECT: Filled rectangle at ({x}, {y}) with size {width}x{height} and color {color}")
            self.result_register = 1  # Success
        else:
            self.log("GFX_FILL_RECT: Not enough arguments")
            self.result_register = 0  # Failure
    
    def func_gfx_print(self):
        """Print text on screen (ID: 107)"""
        args = self.pop()  # Number of arguments
        
        if args >= 4:
            ptr_color = self.pop()
            ptr_text = self.pop()
            ptr_y = self.pop()
            ptr_x = self.pop()
            
            color = self.get_mem(ptr_color) & 0xF
            text_id = self.get_mem(ptr_text)
            y = self.get_mem(ptr_y)
            x = self.get_mem(ptr_x)
            
            # Get the text from string block
            text = self.get_string(text_id)
            
            # We would need a font system for proper text rendering
            # For now, just log it
            self.log(f"GFX_PRINT: '{text}' at ({x}, {y}) with color {color}")
            
            # Simple text rendering as a colored line
            if 0 <= y < self.screen_height:
                for i in range(len(text)):
                    px = x + i
                    if 0 <= px < self.screen_width:
                        self.display_buffer[y][px] = color
            
            self.result_register = 1  # Success
        else:
            self.log("GFX_PRINT: Not enough arguments")
            self.result_register = 0  # Failure
        
    def func_gfx_flip(self):
        """Update the display (ID: 109)"""
        args = self.pop()  # Number of arguments (should be 0)
        
        # Mark that display update is requested
        self.display_update_requested = True
        
        self.log("GFX_FLIP: Display update requested")
        self.result_register = 1  # Success

    def func_gfx_circle(self):
        """Draw a circle (ID: 105)"""
        args = self.pop()  # Number of arguments
        
        if args >= 4:
            ptr_color = self.pop()
            ptr_radius = self.pop()
            ptr_y = self.pop()
            ptr_x = self.pop()
            
            color = self.get_mem(ptr_color) & 0xF
            radius = self.get_mem(ptr_radius)
            y = self.get_mem(ptr_y)
            x = self.get_mem(ptr_x)
            
            # Simple midpoint circle algorithm
            f = 1 - radius
            ddf_x = 1
            ddf_y = -2 * radius
            dx = 0
            dy = radius
            
            # Draw initial points at the cardinal directions
            if 0 <= x < self.screen_width and 0 <= y + radius < self.screen_height:
                self.display_buffer[y + radius][x] = color
            if 0 <= x < self.screen_width and 0 <= y - radius < self.screen_height:
                self.display_buffer[y - radius][x] = color
            if 0 <= x + radius < self.screen_width and 0 <= y < self.screen_height:
                self.display_buffer[y][x + radius] = color
            if 0 <= x - radius < self.screen_width and 0 <= y < self.screen_height:
                self.display_buffer[y][x - radius] = color
            
            while dx < dy:
                if f >= 0:
                    dy -= 1
                    ddf_y += 2
                    f += ddf_y
                dx += 1
                ddf_x += 2
                f += ddf_x
                
                # Draw the eight octants
                if 0 <= x + dx < self.screen_width and 0 <= y + dy < self.screen_height:
                    self.display_buffer[y + dy][x + dx] = color
                if 0 <= x - dx < self.screen_width and 0 <= y + dy < self.screen_height:
                    self.display_buffer[y + dy][x - dx] = color
                if 0 <= x + dx < self.screen_width and 0 <= y - dy < self.screen_height:
                    self.display_buffer[y - dy][x + dx] = color
                if 0 <= x - dx < self.screen_width and 0 <= y - dy < self.screen_height:
                    self.display_buffer[y - dy][x - dx] = color
                if 0 <= x + dy < self.screen_width and 0 <= y + dx < self.screen_height:
                    self.display_buffer[y + dx][x + dy] = color
                if 0 <= x - dy < self.screen_width and 0 <= y + dx < self.screen_height:
                    self.display_buffer[y + dx][x - dy] = color
                if 0 <= x + dy < self.screen_width and 0 <= y - dx < self.screen_height:
                    self.display_buffer[y - dx][x + dy] = color
                if 0 <= x - dy < self.screen_width and 0 <= y - dx < self.screen_height:
                    self.display_buffer[y - dx][x - dy] = color
            
            self.log(f"GFX_CIRCLE: Drew circle at ({x}, {y}) with radius {radius} and color {color}")
            self.result_register = 1  # Success
        else:
            self.log("GFX_CIRCLE: Not enough arguments")
            self.result_register = 0  # Failure

    def func_gfx_sprite(self):
        """Optimized sprite rendering (replace existing func_gfx_sprite)"""
        args = self.pop()
        
        if args >= 3:
            ptr_sprite_data = self.pop()
            ptr_y = self.pop()
            ptr_x = self.pop()
            
            sprite_data_addr = self.get_mem(ptr_sprite_data)
            y = self.get_mem(ptr_y)
            x = self.get_mem(ptr_x)
            
            # Read sprite dimensions
            width = self.get_mem(sprite_data_addr)
            height = self.get_mem(sprite_data_addr + 1)
            
            # Validate dimensions
            if width <= 0 or height <= 0 or width > 64 or height > 64:
                self.log(f"GFX_SPRITE: Invalid sprite dimensions {width}x{height}")
                self.result_register = 0
                return
            
            # Early culling - don't render if completely off screen
            if x >= self.screen_width or y >= self.screen_height or x + width <= 0 or y + height <= 0:
                self.result_register = 1  # Success but skipped
                return
            
            # OPTIMIZATION: Batch pixel operations
            pixel_index = 2
            
            for sy in range(height):
                screen_y = y + sy
                
                # Skip rows that are off screen
                if screen_y < 0 or screen_y >= self.screen_height:
                    pixel_index += width
                    continue
                    
                for sx in range(width):
                    screen_x = x + sx
                    
                    # Skip pixels that are off screen
                    if screen_x < 0 or screen_x >= self.screen_width:
                        pixel_index += 1
                        continue
                    
                    # Get pixel color
                    pixel_color = self.get_mem(sprite_data_addr + pixel_index) & 0xF
                    pixel_index += 1
                    
                    # Only draw non-transparent pixels
                    if pixel_color != 0:
                        self.display_buffer[screen_y][screen_x] = pixel_color
            
            self.result_register = 1  # Success
        else:
            self.log("GFX_SPRITE: Not enough arguments")
            self.result_register = 0

    # Sound functions
    
    def func_snd_play_tone(self):
        """Play a tone (ID: 200)"""
        args = self.pop()  # Number of arguments
        
        if args >= 3:
            ptr_channel = self.pop()
            ptr_duration = self.pop()
            ptr_frequency = self.pop()
            
            channel = self.get_mem(ptr_channel) % 4  # 4 channels
            duration = self.get_mem(ptr_duration)  # in milliseconds
            frequency = self.get_mem(ptr_frequency)  # in Hz
            
            # For a proper implementation, we'd generate the actual sound
            # For this minimal version, we'll just log it
            self.log(f"SND_PLAY_TONE: Playing {frequency}Hz for {duration}ms on channel {channel}")
            
            # If pygame.mixer is initialized, we could generate a simple tone
            try:
                import pygame.mixer
                if pygame.mixer.get_init():
                    # Create a sound sample
                    sample_rate = 22050
                    bits = -16  # signed 16-bit
                    duration_sec = duration / 1000.0
                    
                    # Create a sound buffer of the right size
                    buffer_size = int(sample_rate * duration_sec)
                    
                    # Generate a sine wave
                    import math
                    import numpy as np
                    
                    arr = np.sin(2 * math.pi * frequency * np.arange(buffer_size) / sample_rate)
                    arr = (arr * 32767).astype(np.int16)
                    
                    # Create a Sound object and play it
                    sound = pygame.mixer.Sound(arr)
                    sound.play()
            except:
                # Fall back to silent operation if sound generation fails
                pass
            
            self.result_register = 1  # Success
        else:
            self.log("SND_PLAY_TONE: Not enough arguments")
            self.result_register = 0  # Failure
    
    # Input functions
    
    def func_input_key_pressed(self):
        """Check if a key is pressed (ID: 300)"""
        args = self.pop()  # Number of arguments
        
        if args >= 1:
            ptr_key = self.pop()
            key_code = self.get_mem(ptr_key)
            
            # Map key code to pygame key constant
            pygame_key = self._map_key_code(key_code)
            
            # Check if key is in pressed keys set
            is_pressed = pygame_key in self.keys_pressed
            
            self.log(f"INPUT_KEY_PRESSED: Key {key_code} is {'pressed' if is_pressed else 'not pressed'}")
            self.result_register = 1 if is_pressed else 0
        else:
            self.log("INPUT_KEY_PRESSED: Not enough arguments")
            self.result_register = 0  # Failure
    
    def func_input_key_released(self):
        """Check if a key was just released (ID: 301)"""
        args = self.pop()  # Number of arguments
        
        if args >= 1:
            ptr_key = self.pop()
            key_code = self.get_mem(ptr_key)
            
            # Map key code to pygame key constant
            pygame_key = self._map_key_code(key_code)
            
            # Check if key was in previous keys but not in current keys
            is_released = pygame_key in self.previous_keys_pressed and pygame_key not in self.keys_pressed
            
            self.log(f"INPUT_KEY_RELEASED: Key {key_code} is {'released' if is_released else 'not released'}")
            self.result_register = 1 if is_released else 0
        else:
            self.log("INPUT_KEY_RELEASED: Not enough arguments")
            self.result_register = 0  # Failure

    # Math functions
    
    def func_math_sin(self):
        """Sine function (ID: 501)"""
        args = self.pop()  # Number of arguments
        
        if args >= 1:
            ptr_angle = self.pop()
            angle = self.get_mem(ptr_angle)
            
            # Convert angle to radians (assuming input is in degrees)
            import math
            radians = math.radians(angle)
            result = int(math.sin(radians) * 100)  # Scale for integer math
            
            self.log(f"MATH_SIN: sin({angle}°) = {result/100.0}")
            self.result_register = result
        else:
            self.log("MATH_SIN: Not enough arguments")
            self.result_register = 0  # Failure

    def func_math_cos(self):
        """Cosine function (ID: 502)"""
        args = self.pop()  # Number of arguments
        
        if args >= 1:
            ptr_angle = self.pop()
            angle = self.get_mem(ptr_angle)
            
            # Convert angle to radians (assuming input is in degrees)
            import math
            radians = math.radians(angle)
            result = int(math.cos(radians) * 100)  # Scale for integer math
            
            self.log(f"MATH_COS: cos({angle}°) = {result/100.0}")
            self.result_register = result
        else:
            self.log("MATH_COS: Not enough arguments")
            self.result_register = 0  # Failure

    def func_math_sqrt(self):
        """Square root function (ID: 503)"""
        args = self.pop()  # Number of arguments
        
        if args >= 1:
            ptr_value = self.pop()
            value = self.get_mem(ptr_value)
            
            if value < 0:
                result = 0  # Avoid imaginary numbers
            else:
                import math
                result = int(math.sqrt(value))
            
            self.log(f"MATH_SQRT: sqrt({value}) = {result}")
            self.result_register = result
        else:
            self.log("MATH_SQRT: Not enough arguments")
            self.result_register = 0  # Failure
    
    # System functions
    
    def func_sys_delay(self):
        """Delay execution for a number of milliseconds (ID: 900)"""
        args = self.pop()  # Number of arguments
        
        if args >= 1:
            ptr_ms = self.pop()
            ms = self.get_mem(ptr_ms)
            
            # Convert to seconds and delay
            delay_sec = ms / 1000.0
            time.sleep(delay_sec)
            
            self.log(f"SYS_DELAY: Delayed for {ms} milliseconds")
            self.result_register = 1  # Success
        else:
            self.log("SYS_DELAY: Not enough arguments")
            self.result_register = 0  # Failure
    
    def _map_key_code(self, key_code):
        """Map UW key codes to pygame key constants"""
        key_map = {
            0: pygame.K_UP,
            1: pygame.K_DOWN,
            2: pygame.K_LEFT,
            3: pygame.K_RIGHT,
            4: pygame.K_SPACE,
            5: pygame.K_RETURN,
            6: pygame.K_ESCAPE,
        }
        return key_map.get(key_code, pygame.K_UNKNOWN)
        
    def update_display(self):
        """Update the pygame display with the current buffer"""
        self.screen.fill((0, 0, 0))
        
        for y in range(self.screen_height):
            for x in range(self.screen_width):
                color = self.palette[self.display_buffer[y][x]]
                pygame.draw.rect(
                    self.screen,
                    color,
                    (x * self.pixel_scale, y * self.pixel_scale, self.pixel_scale, self.pixel_scale)
                )
        
        pygame.display.flip()
        self.display_update_requested = False
        
    def handle_input(self):
        """Handle pygame events and update input state"""
        # Save the previous state
        self.previous_keys_pressed = self.keys_pressed.copy()
        self.keys_pressed.clear()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            # Track key press/release events
            elif event.type == pygame.KEYDOWN:
                self.log(f"Key pressed: {event.key}")
            elif event.type == pygame.KEYUP:
                self.log(f"Key released: {event.key}")
        
        # Get current key state
        keys = pygame.key.get_pressed()
        
        # Map pygame keys to our key codes
        key_map = {
            pygame.K_UP: 0,
            pygame.K_DOWN: 1,
            pygame.K_LEFT: 2,
            pygame.K_RIGHT: 3,
            pygame.K_SPACE: 4,
            pygame.K_RETURN: 5,
            pygame.K_ESCAPE: 6,
            # Add more keys as needed
        }
        
        # Store pressed keys
        for pygame_key in key_map.keys():
            if keys[pygame_key]:
                self.keys_pressed.add(pygame_key)
                
        # For debugging
        if keys[pygame.K_ESCAPE]:
            self.log("ESC key is pressed!")
        
    def execute_game_loop(self):
        """Optimized game loop with performance monitoring"""
        import time
        
        self.pc = 0
        self.finished = False
        last_frame_time = time.time()
        frame_count = 0
        performance_counter = 0
        
        # Main game loop
        while not self.finished:
            frame_start = time.time()
            
            # Handle input
            self.handle_input()
            
            # Execute VM instructions with optimized limits
            steps = 0
            max_steps = 10000  # Increased for complex games
            
            should_execute_more = True
            
            while should_execute_more and not self.finished and not self.waiting_response and self.pc < len(self.code):
                # Execute one instruction
                try:
                    opcode = self.code[self.pc]
                    handler = self.opcode_handlers.get(opcode)
                    
                    if handler:
                        handler()
                    else:
                        print(f"Unknown opcode: 0x{opcode:02X} at PC={self.pc}")
                        self.pc += 1
                    
                    steps += 1
                    
                    # OPTIMIZATION: Stop on display update for frame pacing
                    if self.display_update_requested:
                        should_execute_more = False
                    elif steps >= max_steps:
                        print(f"Warning: Frame exceeded {max_steps} steps")
                        should_execute_more = False
                    
                except Exception as e:
                    print(f"VM Error at PC={self.pc}: {e}")
                    self.finished = True
                    break
            
            # Update display
            self.update_display()
            
            # Performance monitoring
            frame_time = time.time() - frame_start
            frame_count += 1
            performance_counter += 1
            
            if performance_counter >= 60:  # Every 60 frames
                avg_fps = 60 / (time.time() - last_frame_time + 0.001)  # Avoid div by zero
                if avg_fps < 20:
                    print(f"WARNING: Low performance! FPS: {avg_fps:.1f}")
                elif frame_count % 300 == 0:  # Every 5 seconds
                    print(f"Performance: {avg_fps:.1f} FPS")
                
                last_frame_time = time.time()
                performance_counter = 0
            
            # Limit frame rate
            target_frame_time = 1.0 / self.fps
            if frame_time < target_frame_time:
                time.sleep(target_frame_time - frame_time)
            
            # Handle waiting response
            if self.waiting_response:
                pass
        
        pygame.quit()

    # PATCH 4: Add performance profiling function
    def profile_vm_performance(self):
        """Add this method to FantasyConsole class for performance debugging"""
        instruction_counts = {}
        
        # Count instruction frequency
        pc = 0
        while pc < len(self.code):
            opcode = self.code[pc]
            opcode_name = self.get_opcode_name(opcode) if hasattr(self, 'get_opcode_name') else f"0x{opcode:02X}"
            
            if opcode_name not in instruction_counts:
                instruction_counts[opcode_name] = 0
            instruction_counts[opcode_name] += 1
            
            # Skip operands for instructions that have them
            if opcode in [0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x16, 0x17]:  # Instructions with operands
                pc += 2
            else:
                pc += 1
        
        # Print top instruction types
        print("\n=== VM Instruction Profile ===")
        sorted_instructions = sorted(instruction_counts.items(), key=lambda x: x[1], reverse=True)
        for opcode, count in sorted_instructions[:10]:
            print(f"{opcode}: {count} times")
        print("===============================\n")


def main():
    """Main function to run the FantasyUW console"""
    parser = argparse.ArgumentParser(description='FantasyUW Console')
    parser.add_argument('program', help='program to run: assembly (.asm) or UWScript source (.uws)')
    parser.add_argument('--strings', help='string block file (default: <program>_strings.txt)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--fps', type=int, help='Target frames per second', default=30)
    parser.add_argument('--profile', action='store_true', help='Print an instruction profile before running')
    args = parser.parse_args()
    
    if not os.path.exists(args.program):
        print(f"Error: Program file '{args.program}' not found")
        return 1
    
    print("=== FantasyUW Console ===")
    
    # Create console
    console = FantasyConsole(debug=args.debug)
    console.fps = args.fps
    console.frame_delay = 1.0 / args.fps
    
    # Load (or compile) the program and its strings
    error = load_program(console, args.program, args.strings, target='console')
    if error:
        print(f"Error: {error}")
        return 1
    if args.profile:
        console.profile_vm_performance()
    
    # Initialize memory
    console.initialize_memory()
    
    # Run the console
    try:
        console.execute_game_loop()
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("Program execution complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
