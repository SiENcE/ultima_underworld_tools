import argparse
import os
import random

class UltimaUnderworldVM:
    """Virtual Machine for Ultima Underworld Conversations"""
    
    def __init__(self, debug=False):
        # Memory model
        self.memory = [0] * 65536  # Full 16-bit address space (64K)
        self.stack = []            # Stack storage (primarily for tracking)
        self.stack_pointer = 0     # Stack pointer
        self.base_pointer = 0      # Base/frame pointer  
        self.result_register = 0   # Result register for imported functions
        self.pc = 0                # Program counter
        
        # Conversation-specific data
        self.string_blocks = {}    # Dictionary of string blocks by ID
        self.current_string_block = None  # Currently active string block
        self.string_block_id = 0    # Current string block ID
        self.code = []             # Parsed code
        self.labels = {}           # Jump labels from ASM
        self.call_level = 1        # Call nesting level
        
        # Conversation state
        self.finished = False
        self.waiting_response = False
        
        # Memory layout tracking
        self.unnamed_vars_count = 0
        self.imported_globals_count = 0 
        self.first_memory_slot = 0
        self.memory_slots = 0
        
        # Debug mode
        self.debug = debug
        
        # Initialize opcode handlers
        self.init_opcode_handlers()
        
        # Imported function handlers
        self.imported_functions = {
            0: self.func_babl_menu,
            1: self.func_babl_fmenu,
            2: self.func_print,
            3: self.func_babl_ask,
            4: self.func_compare,
            5: self.func_random,
            7: self.func_contains,
            11: self.func_length,
            15: self.func_get_quest,
            16: self.func_set_quest,
            17: self.func_sex,
            18: self.func_show_inv,
            19: self.func_give_to_npc,
            20: self.func_give_ptr_npc,
            21: self.func_take_from_npc,
            22: self.func_take_id_from_npc,
            23: self.func_identify_inv,
            24: self.func_do_offer,
            25: self.func_do_demand,
            26: self.func_do_inv_create,
            27: self.func_do_inv_delete,
            28: self.func_check_inv_quality,
            29: self.func_set_inv_quality,
            30: self.func_count_inv,
            31: self.func_setup_to_barter,
            32: self.func_end_barter,
            33: self.func_do_judgement,
            34: self.func_do_decline,
            36: self.func_set_likes_dislikes,
            37: self.func_gronk_door,
            38: self.func_set_race_attitude,
            39: self.func_place_object,
            40: self.func_take_from_npc_inv,
            41: self.func_add_to_npc_inv,
            42: self.func_remove_talker,
            43: self.func_set_attitude,
            44: self.func_x_skills,
            45: self.func_x_traps,
            47: self.func_x_obj_stuff,
            48: self.func_find_inv,
            49: self.func_find_barter,
            50: self.func_find_barter_total
        }
    
    def log(self, *args, **kwargs):
        """Log messages only when debug mode is enabled"""
        if self.debug:
            print(*args, **kwargs)
    
    def init_opcode_handlers(self):
        """Initialize the opcode handler mapping"""
        self.opcode_handlers = {
            0x00: self.op_nop,
            0x01: self.op_add,
            0x02: self.op_mul,
            0x03: self.op_sub,
            0x04: self.op_div,
            0x05: self.op_mod,
            0x06: self.op_or,
            0x07: self.op_and,
            0x08: self.op_not,
            0x09: self.op_tstgt,
            0x0A: self.op_tstge,
            0x0B: self.op_tstlt,
            0x0C: self.op_tstle,
            0x0D: self.op_tsteq,
            0x0E: self.op_tstne,
            0x0F: self.op_jmp,
            0x10: self.op_beq,
            0x11: self.op_bne,
            0x12: self.op_bra,
            0x13: self.op_call,
            0x14: self.op_calli,
            0x15: self.op_ret,
            0x16: self.op_pushi,
            0x17: self.op_pushi_eff,
            0x18: self.op_pop,
            0x19: self.op_swap,
            0x1A: self.op_pushbp,
            0x1B: self.op_popbp,
            0x1C: self.op_sptobp,
            0x1D: self.op_bptosp,
            0x1E: self.op_addsp,
            0x1F: self.op_fetchm,
            0x20: self.op_sto,
            0x21: self.op_offset,
            0x22: self.op_start,
            0x23: self.op_save_reg,
            0x24: self.op_push_reg,
            0x26: self.op_exit_op,
            0x27: self.op_say_op,
            0x29: self.op_opneg
        }
    
    def load_string_blocks(self, filename):
        """Load multiple string blocks from file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_block_id = None
            current_block = []
            
            for line in lines:
                line = line.strip()
                
                # Check for block header
                if line.startswith("block:"):
                    # Save previous block if exists
                    if current_block_id is not None and current_block:
                        self.string_blocks[current_block_id] = current_block
                    
                    # Parse new block header
                    parts = line.split(";")[0].strip()
                    current_block_id = parts.split(":")[1].strip()
                    if current_block_id.startswith("0"):
                        # Convert from hex (like 0f0c) to decimal
                        current_block_id = int(current_block_id, 16)
                    else:
                        current_block_id = int(current_block_id)
                    
                    current_block = ['']  # Initialize with empty string at index 0
                    
                    if self.debug:
                        print(f"Found string block: {current_block_id}")
                    continue
                
                # Process string entry
                if current_block_id is not None and ":" in line:
                    parts = line.split(":", 1)
                    if parts[0].strip().isdigit():
                        idx = int(parts[0].strip())
                        text = parts[1].strip()
                        
                        # Extend the block if needed
                        while len(current_block) <= idx:
                            current_block.append('')
                        
                        current_block[idx] = text
            
            # Save the last block
            if current_block_id is not None and current_block:
                self.string_blocks[current_block_id] = current_block
                
            print(f"Loaded {len(self.string_blocks)} string blocks")
            
        except Exception as e:
            print(f"Error loading string blocks: {e}")
            import traceback
            traceback.print_exc()
    
    def set_string_block(self, block_id):
        """Set the active string block"""
        if block_id in self.string_blocks:
            self.current_string_block = self.string_blocks[block_id]
            self.string_block_id = block_id
            print(f"Using string block: {block_id} with {len(self.current_string_block)} strings")
            return True
        else:
            print(f"String block {block_id} not found")
            return False
    
    def process_text_substitutions(self, text):
        """
        Process UW text substitutions in a string.
        
        Format: @XY<num>
        X: G=global, S=stack, P=pointer
        Y: S=string, I=integer  
        """
        import re
        
        def substitute_match(match):
            full_match = match.group(0)
            source = match.group(1)  # G, S, or P
            type_char = match.group(2)  # S or I  
            num = int(match.group(3))
            
            try:
                if source == 'S':  # Stack variable
                    # Stack variables are relative to base pointer
                    addr = self.base_pointer + num
                    value = self.get_mem(addr)
                    
                    if type_char == 'I':
                        return str(value)
                    elif type_char == 'S':
                        return self.get_string_raw(value)
                        
                elif source == 'G':  # Game global
                    # Game globals are at the start of memory
                    value = self.get_mem(num)
                    
                    if type_char == 'I':
                        return str(value)
                    elif type_char == 'S':
                        return self.get_string_raw(value)
                        
                elif source == 'P':  # Pointer variable
                    # Pointer variables point to memory addresses
                    ptr_addr = self.base_pointer + num
                    ptr_value = self.get_mem(ptr_addr)
                    value = self.get_mem(ptr_value)
                    
                    if type_char == 'I':
                        return str(value)
                    elif type_char == 'S':
                        return self.get_string_raw(value)
                        
            except Exception as e:
                self.log(f"Error processing substitution {full_match}: {e}")
                return f"[ERROR:{full_match}]"
            
            return full_match
        
        # Pattern to match @XY<num>
        pattern = r'@([GSP])([SI])(-?\d+)'
        return re.sub(pattern, substitute_match, text)

    def get_string_raw(self, string_id):
        """Get string without substitution processing (to avoid recursion)"""
        if not self.current_string_block:
            return f"[No string block loaded]"
        
        if 0 <= string_id < len(self.current_string_block):
            return self.current_string_block[string_id]
        else:
            return f"[Invalid string ID: {string_id}]"

    def get_string(self, string_id):
        """Get a string from the current string block with text substitution processing"""
        if not self.current_string_block:
            return f"[No string block loaded]"
        
        if 0 <= string_id < len(self.current_string_block):
            raw_string = self.current_string_block[string_id]
            # Process text substitutions
            return self.process_text_substitutions(raw_string)
        else:
            return f"[Invalid string ID: {string_id}]"
    
    def _resolve_argument(self, arg_str, opcode_name, current_pc):
        """Resolve an instruction argument, handling labels if needed."""
        # First check if it's a symbolic label
        if arg_str in self.labels:
            target_pos = self.labels[arg_str]
            
            # Branch instructions use relative offsets
            if opcode_name in ['BEQ', 'BNE', 'BRA']:
                # Calculate relative offset from current position
                # PC will be at the next instruction (current_pc + 2) when branch is evaluated
                offset = target_pos - (current_pc + 2)
                self.log(f"Branch from {current_pc} to label '{arg_str}' at {target_pos}, offset={offset}")
                return offset
            
            # JMP and CALL use absolute positions
            elif opcode_name in ['JMP', 'CALL']:
                self.log(f"{opcode_name} to label '{arg_str}' at position {target_pos}")
                return target_pos
        
        # Try hex values
        if arg_str.startswith('0x'):
            try:
                return int(arg_str, 16)
            except ValueError:
                print(f"Warning: Invalid hex value '{arg_str}', using 0")
                return 0
        
        # Try decimal values
        try:
            return int(arg_str)
        except ValueError:
            # If we get here, it's an invalid argument
            print(f"Warning: Unknown label or invalid number '{arg_str}', using 0")
            return 0
    
    def parse_asm(self, filename):
        """Parse the ASM file into executable code"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Extract string literals from assembly code comments
            self.string_literals = []
            for line in lines:
                if line.strip().startswith("; ") and ": \"" in line:
                    try:
                        # Extract string literal from comment
                        parts = line.split(": \"")
                        if len(parts) > 1:
                            string_literal = parts[1].strip("\"\n")
                            self.string_literals.append(string_literal)
                    except:
                        pass
            
            # Extract metadata from comments
            for line in lines[:20]:  # Check first few lines for metadata
                line = line.strip()
                if "; Slot:" in line:
                    slot_str = line.split('Slot:')[1].strip()
                    if slot_str.startswith("0x"):
                        self.slot_idx = int(slot_str, 16)
                    elif "0" <= slot_str[0] <= "9":
                        self.slot_idx = int(slot_str, 16) if slot_str.startswith("0") else int(slot_str)
                    self.log(f"Found slot ID: 0x{self.slot_idx:04X}")
                    
                elif "; String Block:" in line:
                    block_str = line.split('String Block:')[1].strip()
                    self.string_block = int(block_str)
                    self.log(f"Found string block: {self.string_block}")
                    self.set_string_block(self.string_block)
            
            # First pass to identify labels
            self.labels = {}
            pc = 0
            for line in lines:
                line = line.strip()
                # Skip comments and empty lines
                if not line.strip() or line.strip().startswith(';'):
                    continue
                    
                if ':' in line and not line.startswith(';'):
                    # This is a label definition
                    label = line.split(':')[0].strip()
                    self.labels[label] = pc
                    self.log(f"Found label '{label}' at position {pc}")
                elif not line.startswith(';'):
                    # This is an instruction
                    if ' ' in line:
                        # Opcode with argument
                        pc += 2
                    else:
                        # Single opcode
                        pc += 1
            
            self.log(f"Identified {len(self.labels)} labels: {self.labels}")
            
            # Second pass to load the code
            self.code = []
            pc = 0
            for line in lines:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line.strip() or line.strip().startswith(';'):
                    continue
                    
                # Skip label definitions
                if ':' in line and not line.startswith(';'):
                    continue
                    
                # Parse the instruction
                if ' ' in line:
                    # Opcode with argument
                    parts = line.split(' ', 1)
                    opcode_name = parts[0].strip().upper()
                    arg_str = parts[1].strip()
                    
                    # Handle special cases with comments
                    if ';' in arg_str:
                        arg_str = arg_str.split(';')[0].strip()
                    
                    # Get opcode value
                    opcode_val = self.get_opcode(opcode_name)
                    
                    # Parse the argument - handle symbolic labels
                    arg_val = self._resolve_argument(arg_str, opcode_name, pc)
                    
                    # Add to code
                    self.code.append(opcode_val)
                    self.code.append(arg_val)
                    
                    self.log(f"Instruction at {pc}: {opcode_name} {arg_val}")
                    pc += 2
                else:
                    # Single opcode
                    opcode_name = line.upper()
                    opcode_val = self.get_opcode(opcode_name)
                    
                    self.code.append(opcode_val)
                    self.log(f"Instruction at {pc}: {opcode_name}")
                    pc += 1
            
            print(f"Parsed {len(self.code)} instruction values")
            if self.labels:
                print(f"Found {len(self.labels)} labels")
            
            return True
            
        except Exception as e:
            print(f"Error parsing ASM: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_opcode(self, opcode_name):
        """Convert opcode name to numeric value"""
        opcode_map = {
            'NOP': 0x00,
            'OPADD': 0x01,
            'OPMUL': 0x02,
            'OPSUB': 0x03,
            'OPDIV': 0x04,
            'OPMOD': 0x05,
            'OPOR': 0x06,
            'OPAND': 0x07,
            'OPNOT': 0x08,
            'TSTGT': 0x09,
            'TSTGE': 0x0A,
            'TSTLT': 0x0B,
            'TSTLE': 0x0C,
            'TSTEQ': 0x0D,
            'TSTNE': 0x0E,
            'JMP': 0x0F,
            'BEQ': 0x10,
            'BNE': 0x11,
            'BRA': 0x12,
            'CALL': 0x13,
            'CALLI': 0x14,
            'RET': 0x15,
            'PUSHI': 0x16,
            'PUSHI_EFF': 0x17,
            'POP': 0x18,
            'SWAP': 0x19,
            'PUSHBP': 0x1A,
            'POPBP': 0x1B,
            'SPTOBP': 0x1C,
            'BPTOSP': 0x1D,
            'ADDSP': 0x1E,
            'FETCHM': 0x1F,
            'STO': 0x20,
            'OFFSET': 0x21,
            'START': 0x22,
            'SAVE_REG': 0x23,
            'PUSH_REG': 0x24,
            'STRCMP': 0x25,
            'EXIT_OP': 0x26,
            'SAY_OP': 0x27,
            'RESPOND_OP': 0x28,
            'OPNEG': 0x29
        }
        return opcode_map.get(opcode_name, 0)
    
    def get_opcode_name(self, opcode):
        """Get the string representation of an opcode"""
        opcode_names = {
            0x00: "NOP",
            0x01: "OPADD",
            0x02: "OPMUL",
            0x03: "OPSUB",
            0x04: "OPDIV",
            0x05: "OPMOD",
            0x06: "OPOR",
            0x07: "OPAND",
            0x08: "OPNOT",
            0x09: "TSTGT",
            0x0A: "TSTGE",
            0x0B: "TSTLT",
            0x0C: "TSTLE",
            0x0D: "TSTEQ",
            0x0E: "TSTNE",
            0x0F: "JMP",
            0x10: "BEQ",
            0x11: "BNE",
            0x12: "BRA",
            0x13: "CALL",
            0x14: "CALLI",
            0x15: "RET",
            0x16: "PUSHI",
            0x17: "PUSHI_EFF",
            0x18: "POP",
            0x19: "SWAP",
            0x1A: "PUSHBP",
            0x1B: "POPBP",
            0x1C: "SPTOBP",
            0x1D: "BPTOSP",
            0x1E: "ADDSP",
            0x1F: "FETCHM",
            0x20: "STO",
            0x21: "OFFSET",
            0x22: "START",
            0x23: "SAVE_REG",
            0x24: "PUSH_REG",
            0x25: "STRCMP",
            0x26: "EXIT_OP",
            0x27: "SAY_OP",
            0x28: "RESPOND_OP",
            0x29: "OPNEG"
        }
        return opcode_names.get(opcode, f"UNKNOWN(0x{opcode:02X})")
    
    def initialize_memory(self):
        """Initialize memory with default values for the game variables"""
        # These correspond to the imported globals in the C# reference
        game_globals = [0] * 32
        game_globals[0] = 0         # play_hunger
        game_globals[1] = 30        # play_health
        game_globals[2] = 0         # play_arms
        game_globals[3] = 0         # play_power
        game_globals[4] = 30        # play_hp
        game_globals[5] = 30        # play_mana
        game_globals[6] = 3         # play_level
        game_globals[7] = 0         # new_player_exp
        game_globals[8] = 0         # play_name
        game_globals[9] = 0         # play_poison
        game_globals[10] = 0        # play_drawn
        game_globals[11] = 0        # play_sex
        game_globals[12] = 32       # npc_xhome
        game_globals[13] = 32       # npc_yhome
        game_globals[14] = 0x010C   # npc_whoami - Conversation Slot
        game_globals[15] = 0        # npc_hunger
        game_globals[16] = 30       # npc_health
        game_globals[17] = 30       # npc_hp
        game_globals[18] = 0        # npc_arms
        game_globals[19] = 0        # npc_power
        game_globals[20] = 8        # npc_goal
        game_globals[21] = 3        # npc_attitude - friendly
        game_globals[22] = 0        # npc_gtarg
        game_globals[23] = 0        # npc_talkedto
        game_globals[24] = 0        # npc_level
        game_globals[25] = 0        # npc_name
        game_globals[26] = 1        # dungeon_level
        game_globals[27] = 0        # riddlecounter
        game_globals[28] = 1        # game_time
        game_globals[29] = 1        # game_days
        game_globals[30] = 1        # game_mins
        game_globals[31] = 0        # first_encounter flag (0 -> first time talking)
        
        # Set the game globals in memory
        self.imported_globals_count = len(game_globals)
        for i, value in enumerate(game_globals):
            self.memory[i] = value
        
        # CRITICAL FIX: Adjust memory layout to avoid stack collision with user variables
        # Set up memory layout based on the spec
        self.first_memory_slot = self.imported_globals_count  # 32
        self.memory_slots = self.imported_globals_count + 32  # 64 
        self.base_pointer = self.memory_slots  # 64
        
        # FIXED: Move stack much further away to avoid collision with arrays
        # Arrays can be large (up to 100+ elements), so give plenty of space
        self.stack_pointer = self.memory_slots + 512  # Start stack at 64 + 512 = 576
        
        print(f"Memory layout: globals=0-31, base_ptr={self.base_pointer}, stack_ptr={self.stack_pointer}")
    
    #def get_mem(self, address):
    #    """Get a value from memory, handling overflow"""
    #    if address >= 65536:
    #        address -= 65536
    #    return self.memory[address]
    def get_mem(self, address):
        """Get a value from memory, handling overflow"""
        if address >= 65536:
            address %= 65536  # Wrap around for 16-bit addressing
        return self.memory[address]
    
    def set_mem(self, address, value):
        """Set a value in memory, handling overflow"""
        if address >= 65536:
            address -= 65536
        self.memory[address] = value
    
    def push(self, value):
        """Push a value onto the stack"""
        self.set_mem(self.stack_pointer, value)
        self.stack_pointer += 1
        self.stack.append(value)  # For tracking/debugging
    
    def pop(self):
        """Pop a value from the stack"""
        self.stack_pointer -= 1
        value = self.get_mem(self.stack_pointer)
        #self.set_mem(self.stack_pointer, 0)  # Clear the value
        if self.stack:
            self.stack.pop()  # For tracking/debugging
        return value
    
    def debug_memory(self, start, count):
        """Print memory contents for debugging"""
        print(f"Memory from {start} to {start + count - 1}:")
        for i in range(start, start + count):
            print(f"  [{i:04X}]: {self.get_mem(i)}")
    
    def debug_stack(self):
        """Print current stack contents for debugging"""
        print(f"Stack (BP={self.base_pointer}, SP={self.stack_pointer}):")
        for i in range(self.base_pointer, self.stack_pointer):
            print(f"  [{i:04X}]: {self.get_mem(i)}")
    
    def execute(self):
        """Execute the conversation code"""
        self.pc = 0
        
        # Execute until finished or waiting for response
        while not self.finished and not self.waiting_response and self.pc < len(self.code):
            opcode = self.code[self.pc]
            handler = self.opcode_handlers.get(opcode)
            
            if handler:
                handler()
            else:
                print(f"Unknown opcode: 0x{opcode:02X} at PC={self.pc}")
                self.pc += 1
            
            # Safety check to avoid infinite loops
            if self.pc >= len(self.code):
                self.log("End of code reached")
                self.finished = True
    
    def resume_conversation(self, choice=None):
        """Resume conversation after player response"""
        if choice is not None:
            self.result_register = choice
        
        self.waiting_response = False
        self.execute()
    
    # Opcode implementations
    def op_nop(self):
        """Do nothing"""
        self.log("NOP")
        self.pc += 1
        
    def op_add(self):
        """Add top two values on stack"""
        b = self.pop()
        a = self.pop()
        self.push(a + b)
        self.log(f"OPADD: {a} + {b} = {a + b}")
        self.pc += 1
        
    def op_mul(self):
        """Multiply top two values on stack"""
        b = self.pop()
        a = self.pop()
        self.push(a * b)
        self.log(f"OPMUL: {a} * {b} = {a * b}")
        self.pc += 1
        
    def op_sub(self):
        """Subtract top value from second value on stack"""
        b = self.pop()
        a = self.pop()
        self.push(a - b)
        self.log(f"OPSUB: {a} - {b} = {a - b}")
        self.pc += 1
        
    def op_div(self):
        """Divide second value by top value on stack"""
        b = self.pop()
        a = self.pop()
        if b == 0:  # Avoid division by zero
            self.push(0)
            self.log(f"OPDIV: {a} / {b} = 0 (division by zero)")
        else:
            self.push(a // b)  # Integer division
            self.log(f"OPDIV: {a} / {b} = {a // b}")
        self.pc += 1
        
    def op_mod(self):
        """Modulo operation on top two stack values"""
        b = self.pop()
        a = self.pop()
        if b == 0:  # Avoid division by zero
            self.push(0)
            self.log(f"OPMOD: {a} % {b} = 0 (division by zero)")
        else:
            self.push(a % b)
            self.log(f"OPMOD: {a} % {b} = {a % b}")
        self.pc += 1
        
    def op_or(self):
        """Logical OR of top two values"""
        b = self.pop()
        a = self.pop()
        self.push(a | b)  # Bitwise OR as per the C# implementation
        self.log(f"OPOR: {a} | {b} = {a | b}")
        self.pc += 1
        
    def op_and(self):
        """Logical AND of top two values"""
        b = self.pop()
        a = self.pop()
        self.push(a & b)  # Bitwise AND as per the C# implementation
        self.log(f"OPAND: {a} & {b} = {a & b}")
        self.pc += 1
        
    def op_not(self):
        """Logical NOT of top value"""
        a = self.pop()
        result = 1 if a == 0 else 0
        self.push(result)
        self.log(f"OPNOT: !{a} = {result}")
        self.pc += 1
        
    def op_tstgt(self):
        """Test if second value is greater than top value"""
        b = self.pop()
        a = self.pop()
        result = 1 if a > b else 0
        self.push(result)
        self.log(f"TSTGT: {a} > {b} = {result}")
        self.pc += 1
        
    def op_tstge(self):
        """Test if second value is greater than or equal to top value"""
        b = self.pop()
        a = self.pop()
        result = 1 if a >= b else 0
        self.push(result)
        self.log(f"TSTGE: {a} >= {b} = {result}")
        self.pc += 1
        
    def op_tstlt(self):
        """Test if second value is less than top value"""
        b = self.pop()
        a = self.pop()
        result = 1 if a < b else 0
        self.push(result)
        self.log(f"TSTLT: {a} < {b} = {result}")
        self.pc += 1
        
    def op_tstle(self):
        """Test if second value is less than or equal to top value"""
        b = self.pop()
        a = self.pop()
        result = 1 if a <= b else 0
        self.push(result)
        self.log(f"TSTLE: {a} <= {b} = {result}")
        self.pc += 1
        
    def op_tsteq(self):
        """Test equality of top two values"""
        b = self.pop()
        a = self.pop()
        result = 1 if a == b else 0
        self.push(result)
        self.log(f"TSTEQ: {a} == {b} = {result}")
        self.pc += 1
        
    def op_tstne(self):
        """Test inequality of top two values"""
        b = self.pop()
        a = self.pop()
        result = 1 if a != b else 0
        self.push(result)
        self.log(f"TSTNE: {a} != {b} = {result}")
        self.pc += 1
        
    def op_jmp(self):
        """Jump to absolute address"""
        target = self.code[self.pc + 1]
        self.log(f"JMP: Jumping from {self.pc} to {target}")
        self.pc = target
        
    def op_beq(self):
        """Branch if equal (zero)"""
        offset = self.code[self.pc + 1]
        value = self.pop()
        if value == 0:
            self.log(f"BEQ: Branching from {self.pc} by {offset} (value is 0)")
            self.pc = self.pc + offset  # Fixed: offset is relative to instruction after branch
        else:
            self.log(f"BEQ: Not branching (value is {value})")
            self.pc += 2
            
    def op_bne(self):
        """Branch if not equal (non-zero)"""
        offset = self.code[self.pc + 1]
        value = self.pop()
        if value != 0:
            self.log(f"BNE: Branching from {self.pc} by {offset} (value is {value})")
            self.pc = self.pc + offset  # Fixed: offset is relative to instruction after branch
        else:
            self.log(f"BNE: Not branching (value is 0)")
            self.pc += 2
            
    def op_bra(self):
        """Branch always"""
        offset = self.code[self.pc + 1]
        self.log(f"BRA: Branching from {self.pc} by {offset}")
        self.pc = self.pc + offset  # Fixed: offset is relative to instruction after branch
        
    def op_call(self):
        """Call subroutine"""
        target = self.code[self.pc + 1]
        self.log(f"CALL: From {self.pc} to {target}, pushing return addr {self.pc + 2}")
        self.push(self.pc + 2)  # Push return address
        self.pc = target
        self.call_level += 1
        
    #def op_calli(self):
    #    """Call imported function"""
    #    func_id = self.code[self.pc + 1]
    #    self.log(f"CALLI: Calling imported function {func_id}")
    #    
    #    if func_id in self.imported_functions:
    #        self.imported_functions[func_id]()
    #    else:
    #        print(f"Warning: Unknown imported function ID {func_id}")
    #    
    #    self.pc += 2
    def op_calli(self):
        """Call imported function"""
        func_id = self.code[self.pc + 1]
        
        #print(f"CALLI: Calling function {func_id} with stack: {self.stack}")
        
        if func_id in self.imported_functions:
            self.imported_functions[func_id]()
        else:
            print(f"WARNING: Unknown function ID {func_id}")
        
        #print(f"CALLI: After call, result_register = {self.result_register}")
        
        # Fix: Push the result register onto the stack after function call
        self.push(self.result_register)
        
        self.pc += 2
        
    def op_ret(self):
        """Return from subroutine"""
        self.call_level -= 1
        if self.call_level < 0:
            self.log("RET: Ending conversation (call_level < 0)")
            self.finish_conversation()
        else:
            return_addr = self.pop()
            self.log(f"RET: Returning to {return_addr}, call_level now {self.call_level}")
            self.pc = return_addr
        
    def op_pushi(self):
        """Push immediate value onto stack"""
        value = self.code[self.pc + 1]
        self.log(f"PUSHI: Pushing immediate value {value}")
        self.push(value)
        self.pc += 2
        
    def op_pushi_eff(self):
        """Push effective address onto stack"""
        offset = self.code[self.pc + 1]
        if offset >= 0:
            effective_addr = self.base_pointer + offset
        else:
            # Handle negative offsets as per C# implementation
            offset -= 1  # Skip over base ptr
            effective_addr = self.base_pointer + offset
            
        self.log(f"PUSHI_EFF: BP={self.base_pointer}, offset={offset}, pushing effective addr {effective_addr}")
        self.push(effective_addr)
        self.pc += 2
        
    def op_pop(self):
        """Pop value from stack and discard it"""
        value = self.pop()
        self.log(f"POP: Discarding value {value}")
        self.pc += 1
        
    def op_swap(self):
        """Swap the top two stack values"""
        b = self.pop()
        a = self.pop()
        self.log(f"SWAP: Swapping {a} and {b}")
        self.push(b)
        self.push(a)
        self.pc += 1
        
    def op_pushbp(self):
        """Push base pointer onto stack"""
        self.log(f"PUSHBP: Pushing base pointer {self.base_pointer}")
        self.push(self.base_pointer)
        self.pc += 1
        
    def op_popbp(self):
        """Pop base pointer from stack"""
        new_bp = self.pop()
        self.log(f"POPBP: Setting base pointer from {self.base_pointer} to {new_bp}")
        self.base_pointer = new_bp
        self.pc += 1
        
    def op_sptobp(self):
        """Set base pointer to stack pointer"""
        self.log(f"SPTOBP: Setting base pointer from {self.base_pointer} to {self.stack_pointer}")
        self.base_pointer = self.stack_pointer
        self.pc += 1
        
    def op_bptosp(self):
        """Set stack pointer to base pointer"""
        self.log(f"BPTOSP: Setting stack pointer from {self.stack_pointer} to {self.base_pointer}")
        # Clear the stack above the base pointer for tracking
        while len(self.stack) > (self.stack_pointer - self.base_pointer):
            self.stack.pop()
        self.stack_pointer = self.base_pointer
        self.pc += 1
        
    def op_addsp(self):
        """Reserve space on stack"""
        count = self.pop()
        self.log(f"ADDSP: Reserving {count} slots on stack")
        for _ in range(count + 1):  # C# impl adds 1 to the count
            self.push(0)
        self.pc += 1
        
    def op_fetchm(self):
        """Fetch from memory"""
        addr = self.pop()
        value = self.get_mem(addr)
        self.log(f"FETCHM: Fetching from addr {addr}, got value {value}")
        self.push(value)
        self.pc += 1
        
    def op_sto(self):
        """Store to memory"""
        value = self.pop()
        addr = self.pop()
        self.log(f"STO: Storing value {value} at addr {addr}")
        self.set_mem(addr, value)
        self.pc += 1
        
    def op_offset(self):
        """Calculate array offset"""
        index = self.pop()
        base_addr = self.pop()
        result = base_addr + index - 1
        self.log(f"OFFSET: base_addr={base_addr}, index={index}, result={result}")
        self.push(result)
        self.pc += 1
        
    def op_start(self):
        """Start program execution"""
        self.log("START: Program execution started")
        self.pc += 1
        
    def op_save_reg(self):
        """Save value to result register"""
        value = self.pop()
        self.log(f"SAVE_REG: Setting result register to {value}")
        self.result_register = value
        self.pc += 1
        
    def op_push_reg(self):
        """Push result register onto stack"""
        self.log(f"PUSH_REG: Pushing result register {self.result_register}")
        self.push(self.result_register)
        self.pc += 1
        
    def op_exit_op(self):
        """End program execution"""
        self.log("EXIT_OP: Ending program execution")
        self.finish_conversation()
        
    def op_say_op(self):
        """NPC says something"""
        string_id = self.pop()
        text = self.get_string(string_id)
        self.log(f"SAY_OP: Using string ID {string_id}")
        if text != "[No string block loaded]":
            print(f'NPC: "{text}"')
        else:
            self.log(f'NPC: "{text}"')
        self.pc += 1
        
    def op_opneg(self):
        """Negate top value on stack"""
        value = self.pop()
        self.log(f"OPNEG: Negating {value} to {-value}")
        self.push(-value)
        self.pc += 1
    
    def finish_conversation(self):
        """End the conversation"""
        print("\nConversation finished")
        self.finished = True
        
        # Save the conversation variables
        saved_vars = []
        for i in range(self.memory_slots - self.first_memory_slot):
            saved_vars.append(self.get_mem(self.first_memory_slot + i))
        
        if self.debug:
            print(f"Saved variables: {saved_vars}")
    
    # Simplified implementations of imported functions
    def func_babl_menu(self):
        """Show a menu of dialogue options and get player choice"""
        # Get the number of arguments (first value pushed, last popped)
        num_args = self.pop()
        self.log(f"babl_menu: {num_args} args")
        
        # Get the string array pointer
        string_array_ptr = self.pop()
        self.log(f"String array pointer: {string_array_ptr}")
        
        # Read the string IDs from memory
        options = []
        i = 0
        while True:
            string_id = self.get_mem(string_array_ptr + i)
            if string_id == 0:
                break
            
            text = self.get_string(string_id)
            options.append((i+1, string_id, text))
            i += 1
        
        # Display options to the player
        print("\nChoose an option:")
        for option_num, _, text in options:
            print(f"{option_num}. {text}")
        
        # Wait for player response
        self.waiting_response = True
        
        # Prompt for input (for our simulation)
        choice = input("Enter choice [1-{}]: ".format(len(options)))
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                self.result_register = choice_num
            else:
                print("Invalid choice, defaulting to 1")
                self.result_register = 1
        except ValueError:
            print("Invalid input, defaulting to 1")
            self.result_register = 1
        
        # Resume conversation
        self.waiting_response = False
    
    def func_babl_fmenu(self):
        """Show a filtered menu of dialogue options"""
        # Skip getting num_args for simplicity
        num_args = self.pop()
        
        # Get string array and flag array pointers
        string_array_ptr = self.pop()
        flag_array_ptr = self.pop()
        
        # Read the string IDs and flags
        options = []
        flags = []
        i = 0
        while True:
            string_id = self.get_mem(string_array_ptr + i)
            if string_id == 0:
                break
            
            flag = self.get_mem(flag_array_ptr + i)
            flags.append(flag)
            
            if flag == 1:  # Only show enabled options
                text = self.get_string(string_id)
                options.append((i+1, string_id, text))
            i += 1
        
        # Display options to the player
        print("\nChoose an option:")
        valid_indices = []
        display_index = 1
        for orig_idx, _, text in options:
            print(f"{display_index}. {text}")
            valid_indices.append(orig_idx)
            display_index += 1
        
        # Wait for player response
        self.waiting_response = True
        
        # Prompt for input
        choice = input("Enter choice [1-{}]: ".format(len(options)))
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                self.result_register = valid_indices[choice_num-1]
            else:
                print("Invalid choice, defaulting to first option")
                self.result_register = valid_indices[0] if valid_indices else 0
        except ValueError:
            print("Invalid input, defaulting to first option")
            self.result_register = valid_indices[0] if valid_indices else 0
        
        # Resume conversation
        self.waiting_response = False
    
    def func_print(self):
        """Print a string"""
        ptr_to_string_id = self.pop()
        string_id = self.get_mem(ptr_to_string_id)
        if 0 <= string_id < len(self.string_block):
            text = self.string_block[string_id]
            print(f'PRINT: "{text}"')
        else:
            print(f"PRINT: [Invalid string ID: {string_id}]")
    
    def func_babl_ask(self):
        """Ask the player for input"""
        print("\nEnter text:")
        self.waiting_response = True
        
        # In a real implementation, this would add the string to the string block
        # Here we'll simulate it returning a dummy string ID
        text = input("> ")
        print(f"Input received: {text}")
        self.result_register = 100  # Dummy string ID
        
        self.waiting_response = False
    
    def func_compare(self):
        """Compare two strings for equality"""
        ptr1 = self.pop()
        ptr2 = self.pop()
        
        string_id1 = self.get_mem(ptr1)
        string_id2 = self.get_mem(ptr2)
        
        if 0 <= string_id1 < len(self.string_block) and 0 <= string_id2 < len(self.string_block):
            str1 = self.string_block[string_id1].lower()
            str2 = self.string_block[string_id2].lower()
            
            self.result_register = 1 if str1 == str2 else 0
            print(f'COMPARE: "{str1}" vs "{str2}" -> {self.result_register}')
        else:
            print(f"COMPARE: Invalid string IDs: {string_id1}, {string_id2}")
            self.result_register = 0
    
    def func_random(self):
        """Generate a random number"""
        ptr = self.pop()
        max_val = self.get_mem(ptr)
        
        import random
        self.result_register = random.randint(1, max_val)
        #print(f"RANDOM: Generated {self.result_register} (1 to {max_val})")
    
    def func_contains(self):
        """Check if one string contains another"""
        ptr1 = self.pop()
        ptr2 = self.pop()
        
        string_id1 = self.get_mem(ptr1)
        string_id2 = self.get_mem(ptr2)
        
        if 0 <= string_id1 < len(self.string_block) and 0 <= string_id2 < len(self.string_block):
            str1 = self.string_block[string_id1].lower()
            str2 = self.string_block[string_id2].lower()
            
            self.result_register = 1 if str2 in str1 else 0
            print(f'CONTAINS: "{str2}" in "{str1}" -> {self.result_register}')
        else:
            print(f"CONTAINS: Invalid string IDs: {string_id1}, {string_id2}")
            self.result_register = 0
    
    def func_length(self):
        """Get the length of a string"""
        ptr = self.pop()
        string_id = self.get_mem(ptr)
        
        if 0 <= string_id < len(self.string_block):
            length = len(self.string_block[string_id])
            self.result_register = length
            print(f"LENGTH: String {string_id} has length {length}")
        else:
            print(f"LENGTH: Invalid string ID: {string_id}")
            self.result_register = 0
    
    def func_get_quest(self):
        """Get a quest flag value"""
        ptr = self.pop()
        quest_id = self.get_mem(ptr)
        
        # In a real implementation, this would check a persistent quest store
        print(f"GET_QUEST: Quest ID {quest_id}")
        
        # Simulate getting a quest value
        print("Enter quest status (0 = not done, 1 = done):")
        value = int(input("> ") or "0")
        self.result_register = value
    
    def func_set_quest(self):
        """Set a quest flag value"""
        ptr1 = self.pop()  # Value
        ptr2 = self.pop()  # Quest ID
        
        value = self.get_mem(ptr1)
        quest_id = self.get_mem(ptr2)
        
        print(f"SET_QUEST: Setting quest {quest_id} to {value}")
    
    def func_sex(self):
        """Return string based on player gender"""
        ptr1 = self.pop()  # Female string ID pointer
        ptr2 = self.pop()  # Male string ID pointer
        
        female_str_id = self.get_mem(ptr1)
        male_str_id = self.get_mem(ptr2)
        
        print("Choose gender (m/f):")
        gender = input("> ").lower()
        
        if gender.startswith('m'):
            self.result_register = male_str_id
            print(f"SEX: Using male string ID {male_str_id}")
        else:
            self.result_register = female_str_id
            print(f"SEX: Using female string ID {female_str_id}")
    
    def func_show_inv(self):
        """Show inventory interface"""
        ptr1 = self.pop()  # Array for inventory positions
        ptr2 = self.pop()  # Array for object IDs
        
        print("SHOW_INV: Showing inventory interface")
        print("Enter number of items to select (0-4):")
        count = min(4, max(0, int(input("> ") or "0")))
        
        # Simulate selecting items
        for i in range(count):
            print(f"Enter object ID for item {i+1}:")
            obj_id = int(input("> ") or "0")
            
            self.set_mem(ptr2 + i, obj_id)
            self.set_mem(ptr1 + i, 750 + i)  # Dummy master list position
        
        self.result_register = count
        print(f"SHOW_INV: Selected {count} items")
    
    def func_give_to_npc(self):
        """Give items to NPC"""
        ptr1 = self.pop()  # Array of item inventory positions
        ptr2 = self.pop()  # Number of items
        
        count = self.get_mem(ptr2)
        
        print(f"GIVE_TO_NPC: Giving {count} items to NPC")
        print("Accept items? (y/n):")
        accept = input("> ").lower().startswith('y')
        
        self.result_register = 1 if accept else 0
        print(f"GIVE_TO_NPC: NPC {'accepted' if accept else 'rejected'} items")
    
    def func_give_ptr_npc(self):
        """Give item pointer to NPC"""
        ptr1 = self.pop()  # Quantity
        ptr2 = self.pop()  # Position
        
        quantity = self.get_mem(ptr1)
        position = self.get_mem(ptr2)
        
        print(f"GIVE_PTR_NPC: Giving item at position {position}, quantity {quantity}")
    
    def func_take_from_npc(self):
        """Take item from NPC"""
        ptr = self.pop()
        item_id = self.get_mem(ptr)
        
        print(f"TAKE_FROM_NPC: Taking item ID {item_id} from NPC")
        print("Accept item? (y/n):")
        accept = input("> ").lower().startswith('y')
        
        self.result_register = 1 if accept else 2  # 1 = OK, 2 = No space
        print(f"TAKE_FROM_NPC: {'Accepted' if self.result_register == 1 else 'No space for'} item")
    
    def func_take_id_from_npc(self):
        """Take item by ID from NPC"""
        ptr = self.pop()
        position = self.get_mem(ptr)
        
        print(f"TAKE_ID_FROM_NPC: Taking item at position {position} from NPC")
        print("Accept item? (y/n):")
        accept = input("> ").lower().startswith('y')
        
        self.result_register = 1 if accept else 2  # 1 = OK, 2 = No space
        print(f"TAKE_ID_FROM_NPC: {'Accepted' if self.result_register == 1 else 'No space for'} item")
    
    def func_identify_inv(self):
        """Identify inventory item"""
        # Skip implementation details
        print("IDENTIFY_INV: Identifying inventory item")
        self.pop() # Skip arguments
        self.pop()
        self.pop()
        self.pop()
        
        self.result_register = 0  # Dummy result
    
    def func_do_offer(self):
        """Handle trading offer"""
        print("DO_OFFER: Processing trade offer")
        
        # Skip the arguments for simplicity
        for _ in range(5):
            self.pop()
        
        print("Accept offer? (y/n):")
        accept = input("> ").lower().startswith('y')
        
        self.result_register = 1 if accept else 0
        print(f"DO_OFFER: Offer {'accepted' if accept else 'rejected'}")
    
    def func_do_demand(self):
        """Handle demand for items"""
        ptr1 = self.pop()  # String if not willing
        ptr2 = self.pop()  # String if willing
        
        unwilling_str_id = self.get_mem(ptr1)
        willing_str_id = self.get_mem(ptr2)
        
        print("DO_DEMAND: Processing demand")
        print("Accept demand? (y/n):")
        accept = input("> ").lower().startswith('y')
        
        if accept:
            print(f"DO_DEMAND: Using willing string ID {willing_str_id}")
        else:
            print(f"DO_DEMAND: Using unwilling string ID {unwilling_str_id}")
        
        self.result_register = 1 if accept else 0
    
    def func_do_inv_create(self):
        """Create item in NPC inventory"""
        ptr = self.pop()
        item_id = self.get_mem(ptr)
        
        print(f"DO_INV_CREATE: Creating item ID {item_id} in NPC inventory")
        
        self.result_register = 1000  # Dummy inventory position
        print(f"DO_INV_CREATE: Created at position {self.result_register}")
    
    def func_do_inv_delete(self):
        """Delete item from NPC inventory"""
        ptr = self.pop()
        item_id = self.get_mem(ptr)
        
        print(f"DO_INV_DELETE: Deleting item ID {item_id} from NPC inventory")
    
    def func_check_inv_quality(self):
        """Check inventory item quality"""
        ptr = self.pop()
        position = self.get_mem(ptr)
        
        print(f"CHECK_INV_QUALITY: Checking quality of item at position {position}")
        
        self.result_register = 20  # Dummy quality value
        print(f"CHECK_INV_QUALITY: Quality is {self.result_register}")
    
    def func_set_inv_quality(self):
        """Set inventory item quality"""
        ptr1 = self.pop()  # Quality
        ptr2 = self.pop()  # Position
        
        quality = self.get_mem(ptr1)
        position = self.get_mem(ptr2)
        
        print(f"SET_INV_QUALITY: Setting quality of item at position {position} to {quality}")
    
    def func_count_inv(self):
        """Count items in inventory"""
        ptr = self.pop()
        arg = self.get_mem(ptr)
        
        print(f"COUNT_INV: Counting inventory items (arg: {arg})")
        
        self.result_register = 5  # Dummy item count
        print(f"COUNT_INV: Count is {self.result_register}")
    
    def func_setup_to_barter(self):
        """Set up bartering interface"""
        print("SETUP_TO_BARTER: Setting up barter interface")
    
    def func_end_barter(self):
        """End bartering session"""
        print("END_BARTER: Ending barter session")
    
    def func_do_judgement(self):
        """Judge current trade offer"""
        print("DO_JUDGEMENT: Judging trade offer")
    
    def func_do_decline(self):
        """Decline trade offer"""
        print("DO_DECLINE: Declining trade offer")
    
    def func_set_likes_dislikes(self):
        """Set items NPC likes/dislikes to trade"""
        ptr1 = self.pop()  # Likes array
        ptr2 = self.pop()  # Dislikes array
        
        print(f"SET_LIKES_DISLIKES: Setting likes at {ptr1}, dislikes at {ptr2}")
    
    def func_gronk_door(self):
        """Open/close door or portcullis"""
        ptr1 = self.pop()  # Close/open flag
        ptr2 = self.pop()  # Y tile
        ptr3 = self.pop()  # X tile
        
        flag = self.get_mem(ptr1)
        y = self.get_mem(ptr2)
        x = self.get_mem(ptr3)
        
        action = "Opening" if flag == 0 else "Closing"
        print(f"GRONK_DOOR: {action} door at ({x}, {y})")
        
        self.result_register = 1  # Success
    
    def func_set_race_attitude(self):
        """Set attitude for a race"""
        print("SET_RACE_ATTITUDE: Setting race attitude")
        for _ in range(3):  # Skip arguments
            self.pop()
    
    def func_place_object(self):
        """Place object in the world"""
        ptr1 = self.pop()  # X tile
        ptr2 = self.pop()  # Y tile
        ptr3 = self.pop()  # Inventory slot
        
        x = self.get_mem(ptr1)
        y = self.get_mem(ptr2)
        slot = self.get_mem(ptr3)
        
        print(f"PLACE_OBJECT: Placing object from slot {slot} at ({x}, {y})")
    
    def func_take_from_npc_inv(self):
        """Take from NPC inventory"""
        ptr = self.pop()
        arg = self.get_mem(ptr)
        
        print(f"TAKE_FROM_NPC_INV: Taking from NPC inventory (arg: {arg})")
        
        self.result_register = 500  # Dummy object list position
        print(f"TAKE_FROM_NPC_INV: Object at position {self.result_register}")
    
    def func_add_to_npc_inv(self):
        """Add to NPC inventory"""
        print("ADD_TO_NPC_INV: Adding to NPC inventory")
    
    def func_remove_talker(self):
        """Remove the NPC the player is talking to"""
        print("REMOVE_TALKER: Removing NPC")
    
    def func_set_attitude(self):
        """Set NPC attitude"""
        ptr1 = self.pop()  # Attitude
        ptr2 = self.pop()  # Target ID
        
        attitude = self.get_mem(ptr1)
        target = self.get_mem(ptr2)
        
        print(f"SET_ATTITUDE: Setting attitude to {attitude} for target {target}")
    
    def func_x_skills(self):
        """Handle skills"""
        ptr1 = self.pop()  # Type
        ptr2 = self.pop()  # Skill
        
        type_val = self.get_mem(ptr1)
        skill = self.get_mem(ptr2)
        
        if type_val == 10000:
            action = "Adding"
        elif type_val == 10001:
            action = "Getting"
        else:
            action = "Unknown operation on"
        
        print(f"X_SKILLS: {action} skill {skill}")
        
        self.result_register = 10  # Dummy skill value
        print(f"X_SKILLS: Result is {self.result_register}")
    
    def func_x_traps(self):
        """Handle traps"""
        ptr1 = self.pop()  # Type
        ptr2 = self.pop()  # Variable
        
        type_val = self.get_mem(ptr1)
        var = self.get_mem(ptr2)
        
        if type_val == 10001:
            action = "Getting variable"
        else:
            action = "Unknown operation on"
        
        print(f"X_TRAPS: {action} {var}")
        
        self.result_register = 0  # Dummy result
        print(f"X_TRAPS: Result is {self.result_register}")
    
    def func_x_obj_stuff(self):
        """Handle object properties"""
        print("X_OBJ_STUFF: Handling object properties")
        
        # Skip arguments for simplicity
        for _ in range(9):
            self.pop()
    
    def func_find_inv(self):
        """Find item in inventory"""
        ptr1 = self.pop()  # Inventory type (0:NPC, 1:player)
        ptr2 = self.pop()  # Item ID
        
        inv_type = self.get_mem(ptr1)
        item_id = self.get_mem(ptr2)
        
        inv_name = "NPC" if inv_type == 0 else "player"
        print(f"FIND_INV: Finding item ID {item_id} in {inv_name} inventory")
        
        self.result_register = 0  # Not found
        print(f"FIND_INV: Result is {self.result_register}")
    
    def func_find_barter(self):
        """Find item in barter area"""
        ptr = self.pop()
        item_id = self.get_mem(ptr)
        
        print(f"FIND_BARTER: Finding item ID {item_id} in barter area")
        
        self.result_register = 0  # Not found
        print(f"FIND_BARTER: Result is {self.result_register}")
    
    def func_find_barter_total(self):
        """Find total of item in barter area"""
        print("FIND_BARTER_TOTAL: Finding total in barter area")
        
        # Skip arguments for simplicity
        for _ in range(4):
            self.pop()
        
        self.result_register = 0  # Not found
        print(f"FIND_BARTER_TOTAL: Result is {self.result_register}")

def main():
    """Main function to run the Ultima Underworld VM"""
    parser = argparse.ArgumentParser(description='Ultima Underworld Conversation VM')
    parser.add_argument('conversation', help='Path to the conversation ASM file')
    parser.add_argument('--strings', help='Path to the string block file', default='uw-strings.txt')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    if not os.path.exists(args.conversation):
        print(f"Error: Conversation file '{args.conversation}' not found")
        return
    
    if not os.path.exists(args.strings):
        print(f"Error: String block file '{args.strings}' not found")
        return
    
    print("=== Ultima Underworld Conversation VM ===")
    
    # Create VM
    vm = UltimaUnderworldVM(debug=args.debug)
    
    # Load string blocks
    vm.load_string_blocks(args.strings)
    
    # Parse and load the assembly code
    vm.parse_asm(args.conversation)
    
    # Initialize memory
    vm.initialize_memory()
    
    # Execute the conversation
    vm.execute()
    
    print("Conversation complete")

if __name__ == "__main__":
    main()
