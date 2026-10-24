# test_fantasy_console.py

import unittest
import pygame
import os
import sys
import tempfile

# The VM and the UWScript compiler live in ../uwscript
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uwscript'))
from fantasy_console import FantasyConsole
from uwscript_compiler import compile_uwscript

class FantasyConsoleTests(unittest.TestCase):
    """Test cases for the FantasyUW fantasy console"""
    
    def setUp(self):
        """Set up test environment"""
        # Suppress pygame output
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        pygame.init()
        
        # Create a console instance for testing
        self.console = FantasyConsole(debug=False)
        self.console.screen = pygame.Surface((128, 128))  # Mock screen
        
        # Create temp directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        
    def tearDown(self):
        """Clean up after tests"""
        pygame.quit()
        self.temp_dir.cleanup()
    
    def compile_and_load(self, script, string_block=1):
        """Compile UWScript to assembly and load it into the console"""
        # Compile the script
        result = compile_uwscript(script, string_block)
        
        # Write assembly to temp file
        asm_path = os.path.join(self.temp_dir.name, "test.asm")
        with open(asm_path, "w") as f:
            f.write(result["assembly"])
            
        # Write strings to temp file
        strings_path = os.path.join(self.temp_dir.name, "test_strings.txt")
        with open(strings_path, "w") as f:
            f.write(result["strings"])
            
        # Load assembly and strings
        self.console.load_string_blocks(strings_path)
        self.console.parse_asm(asm_path)
        self.console.initialize_memory()
        
        # Verify string_literals was populated
        if not self.console.string_literals:
            print("Warning: No string literals were loaded")
        
        return asm_path, strings_path
    
    def execute_until_complete(self, max_steps=10000):
        """Execute the VM until it finishes or reaches max steps"""
        self.console.pc = 0
        self.console.finished = False
        
        steps = 0
        while not self.console.finished and steps < max_steps:
            # Execute one instruction
            if self.console.pc < len(self.console.code):
                opcode = self.console.code[self.console.pc]
                handler = self.console.opcode_handlers.get(opcode)
                if handler:
                    handler()
                else:
                    self.console.pc += 1
            else:
                break
                
            steps += 1
            
        return steps
    
    def test_gfx_clear(self):
        """Test the clear screen function"""
        script = """
        // Test clear screen
        clear_screen(3)  // Color 3 (Green)
        exit
        """
        
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check that all pixels are set to the specified color
        for y in range(self.console.screen_height):
            for x in range(self.console.screen_width):
                self.assertEqual(self.console.display_buffer[y][x], 3)
    
    def test_gfx_pixel(self):
        """Test the set pixel function"""
        script = """
        // Test set pixel
        clear_screen(0)  // Clear to black
        set_pixel(10, 20, 5)  // Set pixel at (10, 20) to color 5 (Yellow)
        exit
        """
        
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check that the specific pixel is set
        self.assertEqual(self.console.display_buffer[20][10], 5)
        
        # Check that other pixels are still black
        self.assertEqual(self.console.display_buffer[0][0], 0)
    
    def test_gfx_line(self):
        """Test the line drawing function"""
        script = """
        // Test line drawing
        clear_screen(0)  // Clear to black
        draw_line(0, 0, 10, 10, 2)  // Red diagonal line
        exit
        """
        
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check endpoints of the line
        self.assertEqual(self.console.display_buffer[0][0], 2)
        self.assertEqual(self.console.display_buffer[10][10], 2)
        
        # Check a few points along the line
        self.assertEqual(self.console.display_buffer[5][5], 2)
    
    def test_gfx_rect(self):
        """Test the rectangle drawing function"""
        script = """
        // Test rectangle drawing
        clear_screen(0)  // Clear to black
        draw_rect(10, 10, 20, 15, 4)  // Blue rectangle
        exit
        """
        
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check corner pixels
        self.assertEqual(self.console.display_buffer[10][10], 4)
        self.assertEqual(self.console.display_buffer[10][29], 4)
        self.assertEqual(self.console.display_buffer[24][10], 4)
        self.assertEqual(self.console.display_buffer[24][29], 4)
        
        # Check interior pixel (should be black)
        self.assertEqual(self.console.display_buffer[15][15], 0)
    
    def test_gfx_fill_rect(self):
        """Test the filled rectangle function"""
        script = """
        // Test filled rectangle
        clear_screen(0)  // Clear to black
        fill_rect(10, 10, 20, 15, 6)  // Magenta filled rectangle
        exit
        """
        
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check corner pixels
        self.assertEqual(self.console.display_buffer[10][10], 6)
        self.assertEqual(self.console.display_buffer[10][29], 6)
        self.assertEqual(self.console.display_buffer[24][10], 6)
        self.assertEqual(self.console.display_buffer[24][29], 6)
        
        # Check interior pixel (should also be magenta)
        self.assertEqual(self.console.display_buffer[15][15], 6)
    
    def test_input_key_pressed(self):
        """Test the key pressed function"""
        script = """
        // Test key pressed function
        let key_state = 0
        
        // Check if UP key is pressed
        if is_key_pressed(0)  // UP key
            key_state = 1
        else
            key_state = 2
        endif
        
        exit
        """
        
        self.compile_and_load(script)
        
        # Simulate UP key being pressed
        self.console.keys_pressed.add(pygame.K_UP)
        
        self.execute_until_complete()
        
        # Check that key_state was set to 1 (key is pressed)
        # Fix: Use base_pointer offset instead of direct memory address
        self.assertEqual(self.console.get_mem(self.console.base_pointer), 1)
        
        # Reset and test key not pressed
        self.console.keys_pressed.clear()
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check that key_state was set to 2 (key not pressed)
        # Fix: Use base_pointer offset instead of direct memory address
        self.assertEqual(self.console.get_mem(self.console.base_pointer), 2)
    
    def test_complex_program(self):
        """Test a more complex program with multiple operations"""
        script = """
        // Complex test program
        let x = 64
        let y = 32
        let color = 3
        
        // Clear screen
        clear_screen(0)
        
        // Draw filled rectangle
        fill_rect(x - 10, y - 10, 20, 20, color)
        
        // Draw outline
        draw_rect(x - 12, y - 12, 24, 24, color + 1)
        
        // Draw connecting lines
        draw_line(0, 0, x, y, 7)
        draw_line(127, 0, x, y, 7)
        draw_line(0, 127, x, y, 7)
        draw_line(127, 127, x, y, 7)
        
        exit
        """
        
        self.compile_and_load(script)
        self.console.debug = True  # Enable debug output
        self.execute_until_complete()
        
        # Instead of checking the center pixel (which gets overwritten by the lines),
        # check a pixel that's inside the rectangle but not on any of the lines
        rect_x, rect_y = 55, 25  # Inside the filled rectangle but not on a line
        actual_color = self.console.display_buffer[rect_y][rect_x]
        self.assertEqual(actual_color, 3, 
                        f"Expected color 3 at rectangle point ({rect_x}, {rect_y}), got {actual_color}")
        
        # Optionally, also verify the center pixel is indeed 7 (from the lines)
        center_x, center_y = 64, 32
        center_color = self.console.display_buffer[center_y][center_x]
        self.assertEqual(center_color, 7,
                        f"Expected color 7 at center ({center_x}, {center_y}), got {center_color}")
    
    def test_variables_and_calculations(self):
        """Test variable usage and calculations"""
        script = """
        // Test variable usage
        let a = 10
        let b = 20
        let c = a + b      // 30
        let d = a * b      // 200
        let e = b - a      // 10
        let f = b / a      // 2
        let g = b % a      // 0
        let h = (a + b) * 2  // 60
        
        // Clear with color based on calculation
        clear_screen(c % 16)  // Should be color 14
        
        exit
        """
        
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check that screen was cleared with color 14
        self.assertEqual(self.console.display_buffer[0][0], 14)
    
    def test_conditional_execution(self):
        """Test conditional execution with if statements"""
        script = """
        // Test conditionals with debugging
        let a = 10
        let b = 20
        let result = 0
        
        if a < b
            result = 1
            say "Set result to 1"
        else
            result = 2
            say "Set result to 2"
        endif
        
        if a > b
            result = 3
            say "Set result to 3"
        endif
        
        if a == 10 and b == 20
            result = 4
            say "Set result to 4"
        endif
        
        exit
        """
        
        self.compile_and_load(script)
        self.console.debug = True  # Enable debug output
        self.execute_until_complete()
        
        # Check that variables have the correct values
        self.assertEqual(self.console.get_mem(self.console.base_pointer), 10)  # a
        self.assertEqual(self.console.get_mem(self.console.base_pointer+1), 20)  # b
        self.assertEqual(self.console.get_mem(self.console.base_pointer+2), 4)   # result
    
    def test_string_operations(self):
        """Test string handling and say operations"""
        script = """
        // Test string operations
        let name = "Console"
        say "Testing " + name
        exit
        """
        
        self.compile_and_load(script)
        self.execute_until_complete()
        
        # Check that strings were correctly generated
        # (This would normally be a SAY_OP instruction with the correct string ID)
        self.assertTrue("Testing Console" in self.console.string_literals or 
                      "Testing @SS0" in self.console.string_literals)

if __name__ == "__main__":
    unittest.main()
