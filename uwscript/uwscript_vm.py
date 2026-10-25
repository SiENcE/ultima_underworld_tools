#!/usr/bin/env python3
"""
UWScript VM: runs Ultima Underworld conversation assembly in the terminal.

    python uwscript_vm.py program.asm                  # strings from program_strings.txt
    python uwscript_vm.py program.uws                  # compile and run in one step
    python uwscript_vm.py program.asm --strings other_strings.txt --quest 5=1

It follows the calling convention of the original engine for imported
functions (CALLI): arguments stay on the stack for the caller to pop and the
result is read with PUSH_REG. The fantasy console (../fantasy_console) is
built on this VM.
"""

import argparse
import os
import random
import re
import sys


class VMError(Exception):
    """A runtime error in the conversation program."""


class UltimaUnderworldVM:
    """Virtual Machine for Ultima Underworld Conversations"""

    # Nesting depth for text substitutions that insert other templates
    MAX_SUBSTITUTION_DEPTH = 8

    def __init__(self, debug=False):
        # Memory model
        self.memory = [0] * 65536  # Full 16-bit address space (64K)
        self.stack_base = 0        # Initial stack pointer (see the stack property)
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

        # Quest flags (get_quest/set_quest) and scripted answers for menus/ask
        self.quest_flags = {}
        self.input_func = input
        
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
                text = f.read()
        except OSError as e:
            print(f"Error loading string blocks: {e}")
            return False
        return self.load_string_blocks_text(text)

    def load_string_blocks_text(self, text):
        """Load string blocks from the text of a strings file"""
        try:
            lines = text.splitlines(keepends=True)
            
            current_block_id = None
            current_block = []
            
            for raw_line in lines:
                line = raw_line.strip()

                # Check for block header
                if line.startswith("block:"):
                    # Save previous block if exists
                    if current_block_id is not None and current_block:
                        self.string_blocks[current_block_id] = current_block

                    # Parse new block header; block ids are hex (like 0f0c)
                    parts = line.split(";")[0].strip()
                    current_block_id = int(parts.split(":")[1].strip(), 16)

                    current_block = ['']  # Initialize with empty string at index 0

                    self.log(f"Found string block: {current_block_id}")
                    continue

                # Process string entry ("<index>: <text>"); keep trailing spaces
                if current_block_id is not None and ":" in line:
                    index_part, text = raw_line.rstrip('\r\n').split(":", 1)
                    if index_part.strip().isdigit():
                        idx = int(index_part.strip())
                        if text.startswith(' '):
                            text = text[1:]

                        # Extend the block if needed
                        while len(current_block) <= idx:
                            current_block.append('')

                        current_block[idx] = self.unescape_string(text)

            # Save the last block
            if current_block_id is not None and current_block:
                self.string_blocks[current_block_id] = current_block

            self.log(f"Loaded {len(self.string_blocks)} string blocks")
            return True

        except Exception as e:
            print(f"Error loading string blocks: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return False

    @staticmethod
    def unescape_string(text):
        """Turn \\n, \\t and \\\\ in string files into the real characters"""
        return re.sub(r'\\([nt\\])', lambda m: {'n': '\n', 't': '\t', '\\': '\\'}[m.group(1)], text)

    def set_string_block(self, block_id):
        """Set the active string block"""
        if block_id in self.string_blocks:
            self.current_string_block = self.string_blocks[block_id]
            self.string_block_id = block_id
            self.log(f"Using string block: {block_id} with {len(self.current_string_block)} strings")
            return True
        else:
            print(f"String block {block_id} not found")
            return False

    def process_text_substitutions(self, text, depth=0):
        """
        Process UW text substitutions in a string.
        
        Format: @XY<num>
        X: G=global, S=stack, P=pointer
        Y: S=string, I=integer

        A substituted string may itself contain substitutions (UWScript
        builds strings that way); those are expanded up to
        MAX_SUBSTITUTION_DEPTH levels.
        """
        def get_text(string_id):
            if depth + 1 >= self.MAX_SUBSTITUTION_DEPTH:
                return self.get_string_raw(string_id)
            return self.get_string(string_id, depth + 1)

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
                        return get_text(value)
                        
                elif source == 'G':  # Game global
                    # Game globals are at the start of memory
                    value = self.get_mem(num)
                    
                    if type_char == 'I':
                        return str(value)
                    elif type_char == 'S':
                        return get_text(value)
                        
                elif source == 'P':  # Pointer variable
                    # Pointer variables point to memory addresses
                    ptr_addr = self.base_pointer + num
                    ptr_value = self.get_mem(ptr_addr)
                    value = self.get_mem(ptr_value)
                    
                    if type_char == 'I':
                        return str(value)
                    elif type_char == 'S':
                        return get_text(value)
                        
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

    def get_string(self, string_id, depth=0):
        """Get a string from the current string block with text substitution processing"""
        if not self.current_string_block:
            return f"[No string block loaded]"
        
        if 0 <= string_id < len(self.current_string_block):
            raw_string = self.current_string_block[string_id]
            # Process text substitutions
            return self.process_text_substitutions(raw_string, depth)
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
        try:
            if arg_str.lower().startswith(('0x', '-0x')):
                return int(arg_str, 16)
            return int(arg_str)
        except ValueError:
            raise VMError(f"Unknown label or invalid number '{arg_str}'")
    
    def parse_asm(self, filename):
        """Parse an ASM file into executable code"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                text = f.read()
        except OSError as e:
            print(f"Error reading {filename}: {e}")
            return False
        return self.parse_asm_text(text)

    def parse_asm_text(self, text):
        """Parse assembly source into executable code. Returns False on errors."""
        lines = text.splitlines()

        # Extract string literals from the compiler's header comments ('; 3: "text"')
        self.string_literals = []
        for line in lines:
            match = re.match(r'^;\s*\d+: "(.*)"', line.strip())
            if match:
                self.string_literals.append(match.group(1))

        # Extract metadata from the header comments
        for line in lines[:20]:
            line = line.strip()
            if "; Slot:" in line:
                slot_str = line.split('Slot:')[1].strip()
                self.slot_idx = int(slot_str, 16)
                self.log(f"Found slot ID: 0x{self.slot_idx:04X}")
            elif "; String Block:" in line:
                self.string_block = int(line.split('String Block:')[1].strip())
                self.log(f"Found string block: {self.string_block}")
                self.set_string_block(self.string_block)

        # Strip comments and blank lines; split labels from instructions
        program = []  # (line number, label or None, opcode name, argument string or None)
        for number, line in enumerate(lines, 1):
            line = line.split(';', 1)[0].strip()
            if not line:
                continue
            if line.endswith(':'):
                program.append((number, line[:-1].strip(), None, None))
                continue
            parts = line.split(None, 1)
            program.append((number, None, parts[0].upper(), parts[1].strip() if len(parts) > 1 else None))

        # First pass: label positions
        self.labels = {}
        pc = 0
        for number, label, opcode_name, arg_str in program:
            if label is not None:
                if label in self.labels:
                    print(f"Error: line {number}: label '{label}' is defined twice")
                    return False
                self.labels[label] = pc
            else:
                pc += 2 if arg_str is not None else 1
        self.log(f"Identified {len(self.labels)} labels: {self.labels}")

        # Second pass: emit code
        self.code = []
        pc = 0
        for number, label, opcode_name, arg_str in program:
            if label is not None:
                continue
            try:
                opcode_val = self.get_opcode(opcode_name)
                self.code.append(opcode_val)
                if arg_str is None:
                    self.log(f"Instruction at {pc}: {opcode_name}")
                    pc += 1
                else:
                    arg_val = self._resolve_argument(arg_str, opcode_name, pc)
                    self.code.append(arg_val)
                    self.log(f"Instruction at {pc}: {opcode_name} {arg_val}")
                    pc += 2
            except VMError as e:
                print(f"Error: line {number}: {e}")
                return False

        self.log(f"Parsed {len(self.code)} instruction values, {len(self.labels)} labels")
        return True
    
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
        if opcode_name not in opcode_map:
            raise VMError(f"Unknown instruction '{opcode_name}'")
        return opcode_map[opcode_name]
    
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
        """Enhanced memory initialization for large games"""
        # Game globals (keep original)
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
        game_globals[14] = 0x010C   # npc_whoami
        game_globals[15] = 0        # npc_hunger
        game_globals[16] = 30       # npc_health
        game_globals[17] = 30       # npc_hp
        game_globals[18] = 0        # npc_arms
        game_globals[19] = 0        # npc_power
        game_globals[20] = 8        # npc_goal
        game_globals[21] = 3        # npc_attitude
        game_globals[22] = 0        # npc_gtarg
        game_globals[23] = 0        # npc_talkedto
        game_globals[24] = 0        # npc_level
        game_globals[25] = 0        # npc_name
        game_globals[26] = 1        # dungeon_level
        game_globals[27] = 0        # riddlecounter
        game_globals[28] = 1        # game_time
        game_globals[29] = 1        # game_days
        game_globals[30] = 1        # game_mins
        game_globals[31] = 0        # first_encounter flag
        
        # Set the game globals in memory
        self.imported_globals_count = len(game_globals)
        for i, value in enumerate(game_globals):
            self.memory[i] = value
        
        # CRITICAL FIX: Much larger separation for Mario game arrays
        self.first_memory_slot = self.imported_globals_count  # 32
        self.memory_slots = self.imported_globals_count + 64  # 96
        self.base_pointer = self.memory_slots  # 96
        
        # FIXED: Move stack much further away for large arrays (Mario level = 384 elements)
        self.stack_pointer = self.memory_slots + 4096  # Start at 96 + 4096 = 4192
        self.stack_base = self.stack_pointer
        
        self.log(f"Memory: game globals=0-31, base_ptr={self.base_pointer}, stack_ptr={self.stack_pointer}")

    
    @property
    def stack(self):
        """The values currently on the stack (bottom first), for debugging"""
        return self.memory[self.stack_base:self.stack_pointer]

    def get_mem(self, address):
        """Get a value from memory"""
        if not 0 <= address < len(self.memory):
            raise VMError(f"Memory read outside of the address space: {address}")
        return self.memory[address]
    
    def set_mem(self, address, value):
        """Set a value in memory"""
        if not 0 <= address < len(self.memory):
            raise VMError(f"Memory write outside of the address space: {address}")
        self.memory[address] = value
    
    def push(self, value):
        """Push a value onto the stack"""
        if self.stack_pointer >= len(self.memory):
            raise VMError("Stack overflow (runaway recursion or a loop that never pops?)")
        self.set_mem(self.stack_pointer, value)
        self.stack_pointer += 1
    
    def pop(self):
        """Pop a value from the stack"""
        if self.stack_pointer <= 0:
            raise VMError("Stack underflow")
        self.stack_pointer -= 1
        value = self.get_mem(self.stack_pointer)
        #self.set_mem(self.stack_pointer, 0)  # Clear the value
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
        """Execute the conversation code from the start"""
        self.pc = 0
        self._run()

    def _run(self):
        # Execute until finished or waiting for response
        while not self.finished and not self.waiting_response and self.pc < len(self.code):
            opcode = self.code[self.pc]
            handler = self.opcode_handlers.get(opcode)
            
            if handler is None:
                raise VMError(f"Unknown opcode 0x{opcode:02X} at PC={self.pc}")
            handler()
            
            # Safety check to avoid infinite loops
            if self.pc >= len(self.code):
                self.log("End of code reached")
                self.finished = True
    
    def resume_conversation(self, choice=None):
        """Resume conversation after player response"""
        if choice is not None:
            self.result_register = choice
        
        self.waiting_response = False
        self._run()
    
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
            self.pc = self.pc + 2 + offset  # Fixed: offset is relative to instruction after branch
        else:
            self.log(f"BEQ: Not branching (value is {value})")
            self.pc += 2
            
    def op_bne(self):
        """Branch if not equal (non-zero)"""
        offset = self.code[self.pc + 1]
        value = self.pop()
        if value != 0:
            self.log(f"BNE: Branching from {self.pc} by {offset} (value is {value})")
            self.pc = self.pc + 2 + offset  # Fixed: offset is relative to instruction after branch
        else:
            self.log(f"BNE: Not branching (value is 0)")
            self.pc += 2
            
    def op_bra(self):
        """Branch always"""
        offset = self.code[self.pc + 1]
        self.log(f"BRA: Branching from {self.pc} by {offset}")
        self.pc = self.pc + 2 + offset  # Fixed: offset is relative to instruction after branch
        
    def op_call(self):
        """Call subroutine"""
        target = self.code[self.pc + 1]
        self.log(f"CALL: From {self.pc} to {target}, pushing return addr {self.pc + 2}")
        self.push(self.pc + 2)  # Push return address
        self.pc = target
        self.call_level += 1
        
    def op_calli(self):
        """Call imported function.

        Like the original engine, CALLI leaves the arguments on the stack:
        the caller pops them and reads the result with PUSH_REG. The handlers
        may pop their arguments to read them; the stack pointer is restored
        afterwards.
        """
        func_id = self.code[self.pc + 1]
        handler = self.imported_functions.get(func_id)
        if handler is None:
            raise VMError(f"Unknown imported function ID {func_id}")

        saved_sp = self.stack_pointer
        handler()
        self.stack_pointer = saved_sp

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
        if self.finished:
            return
        print("\nConversation finished")
        self.finished = True
        
        # Save the conversation variables
        saved_vars = []
        for i in range(self.memory_slots - self.first_memory_slot):
            saved_vars.append(self.get_mem(self.first_memory_slot + i))
        
        if self.debug:
            print(f"Saved variables: {saved_vars}")
    
    # Simplified implementations of imported functions
    def pop_args(self):
        """Pop the argument count and the argument pointers of an imported function.

        Returns the pointers as [arg1, arg2, ...]: the engine pushes the last
        argument first, so arg1 sits right below the argument count.
        """
        count = self.pop()
        return [self.pop() for _ in range(count)]

    def arg_values(self):
        """The values the argument pointers point to"""
        return [self.get_mem(ptr) for ptr in self.pop_args()]

    def read_input(self, prompt):
        """Read a line from the player; ends the conversation when input runs out"""
        try:
            return self.input_func(prompt)
        except EOFError:
            print("\n(no more input)")
            self.finish_conversation()
            return None

    def choose_option(self, options):
        """Show numbered options and return the chosen index (0-based)"""
        print("\nChoose an option:")
        for number, text in enumerate(options, 1):
            print(f"{number}. {text}")
        if not options:
            return None
        while True:
            answer = self.read_input(f"Enter choice [1-{len(options)}]: ")
            if answer is None:
                return None
            try:
                choice = int(answer)
            except ValueError:
                choice = 0
            if 1 <= choice <= len(options):
                return choice - 1
            print("Invalid choice, defaulting to 1")
            return 0

    def func_babl_menu(self):
        """Show a menu of dialogue options and get player choice"""
        string_array_ptr = self.pop_args()[0]
        
        # Read the string IDs from memory (the list ends with string id 0)
        options = []
        i = 0
        while self.get_mem(string_array_ptr + i) != 0:
            options.append(self.get_string(self.get_mem(string_array_ptr + i)))
            i += 1

        choice = self.choose_option(options)
        self.result_register = 0 if choice is None else choice + 1
    
    def func_babl_fmenu(self):
        """Show a filtered menu of dialogue options"""
        string_array_ptr, flag_array_ptr = self.pop_args()[:2]
        
        # Read the string IDs and flags; only options with a non-zero flag are shown
        options = []
        indices = []
        i = 0
        while self.get_mem(string_array_ptr + i) != 0:
            if self.get_mem(flag_array_ptr + i) != 0:
                options.append(self.get_string(self.get_mem(string_array_ptr + i)))
                indices.append(i + 1)
            i += 1

        choice = self.choose_option(options)
        # The result is the position in the full list, not among the shown options
        self.result_register = 0 if choice is None else indices[choice]
    
    def func_print(self):
        """Print a string that no one speaks (scene description)"""
        string_id = self.arg_values()[0]
        print(f'PRINT: "{self.get_string(string_id)}"')
    
    def func_babl_ask(self):
        """Ask the player for input and store it in the string block"""
        print("\nEnter text:")
        text = self.read_input("> ")
        if text is None:
            self.result_register = 0
            return
        
        if self.current_string_block is None:
            self.current_string_block = ['']
        # The typed text becomes a new string; its id is the result
        self.current_string_block.append(text)
        self.result_register = len(self.current_string_block) - 1
        self.log(f"BABL_ASK: Stored '{text}' as string ID {self.result_register}")

    def _string_text(self, string_id):
        if self.current_string_block and 0 <= string_id < len(self.current_string_block):
            return self.get_string(string_id)
        return None
    
    def func_compare(self):
        """Compare two strings for equality, case independent"""
        id1, id2 = self.arg_values()[:2]
        str1, str2 = self._string_text(id1), self._string_text(id2)
        if str1 is None or str2 is None:
            print(f"COMPARE: Invalid string IDs: {id1}, {id2}")
            self.result_register = 0
            return
        self.result_register = 1 if str1.strip().lower() == str2.strip().lower() else 0
        self.log(f'COMPARE: "{str1}" vs "{str2}" -> {self.result_register}')
    
    def func_random(self):
        """Generate a random number in the range [1..arg1]"""
        max_val = self.arg_values()[0]
        self.result_register = random.randint(1, max_val) if max_val >= 1 else 1
    
    def func_contains(self):
        """Check if the first string contains the second one, case independent"""
        id1, id2 = self.arg_values()[:2]
        str1, str2 = self._string_text(id1), self._string_text(id2)
        if str1 is None or str2 is None:
            print(f"CONTAINS: Invalid string IDs: {id1}, {id2}")
            self.result_register = 0
            return
        self.result_register = 1 if str2.lower() in str1.lower() else 0
        self.log(f'CONTAINS: "{str2}" in "{str1}" -> {self.result_register}')
    
    def func_length(self):
        """Get the length of a string"""
        string_id = self.arg_values()[0]
        text = self._string_text(string_id)
        if text is None:
            print(f"LENGTH: Invalid string ID: {string_id}")
            self.result_register = 0
            return
        self.result_register = len(text)
    
    def func_get_quest(self):
        """Get a quest flag value (0 unless set or preset with --quest)"""
        quest_id = self.arg_values()[0]
        self.result_register = self.quest_flags.get(quest_id, 0)
        self.log(f"GET_QUEST: Quest {quest_id} = {self.result_register}")
    
    def func_set_quest(self):
        """Set a quest flag value: arg1 is the new value, arg2 the quest number"""
        value, quest_id = self.arg_values()[:2]
        self.quest_flags[quest_id] = value
        print(f"SET_QUEST: Setting quest {quest_id} to {value}")

    def func_sex(self):
        """Return string based on player gender"""
        ptr1 = self.pop()  # Female string ID pointer
        ptr2 = self.pop()  # Male string ID pointer
        
        female_str_id = self.get_mem(ptr1)
        male_str_id = self.get_mem(ptr2)
        
        print("Choose gender (m/f):")
        gender = (self.read_input("> ") or "").lower()
        
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
        count = min(4, max(0, int((self.read_input("> ") or "") or "0")))
        
        # Simulate selecting items
        for i in range(count):
            print(f"Enter object ID for item {i+1}:")
            obj_id = int((self.read_input("> ") or "") or "0")
            
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
        accept = (self.read_input("> ") or "").lower().startswith('y')
        
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
        accept = (self.read_input("> ") or "").lower().startswith('y')
        
        self.result_register = 1 if accept else 2  # 1 = OK, 2 = No space
        print(f"TAKE_FROM_NPC: {'Accepted' if self.result_register == 1 else 'No space for'} item")
    
    def func_take_id_from_npc(self):
        """Take item by ID from NPC"""
        ptr = self.pop()
        position = self.get_mem(ptr)
        
        print(f"TAKE_ID_FROM_NPC: Taking item at position {position} from NPC")
        print("Accept item? (y/n):")
        accept = (self.read_input("> ") or "").lower().startswith('y')
        
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
        accept = (self.read_input("> ") or "").lower().startswith('y')
        
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
        accept = (self.read_input("> ") or "").lower().startswith('y')
        
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
        """Open/close door or portcullis: gronk_door(x, y, flag)"""
        x, y, flag = self.arg_values()[:3]
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

def load_program(vm, program, strings=None, block=1):
    """Load a .asm file (or compile a .uws file) and its strings into the VM.

    Returns an error message or None.
    """
    stem, ext = os.path.splitext(program)
    if ext.lower() == '.uws':
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from uwscript_compiler import compile_uwscript, UWScriptError
        try:
            with open(program, 'r', encoding='utf-8') as f:
                result = compile_uwscript(f.read(), block, source_name=os.path.basename(program))
        except UWScriptError as e:
            return f"{program}: error: {e}"
        if strings:
            vm.load_string_blocks(strings)
        else:
            vm.load_string_blocks_text(result['strings'])
        if not vm.parse_asm_text(result['assembly']):
            return "Could not load the compiled assembly"
        return None

    strings = strings or f"{stem}_strings.txt"
    if not os.path.exists(strings):
        return f"String block file '{strings}' not found (use --strings)"
    if not vm.load_string_blocks(strings):
        return f"Could not load '{strings}'"
    if not vm.parse_asm(program):
        return f"Could not load '{program}'"
    return None


def main(argv=None):
    """Run a conversation in the terminal"""
    parser = argparse.ArgumentParser(description='Run an Ultima Underworld conversation (.asm or .uws).')
    parser.add_argument('program', help='conversation assembly (.asm) or UWScript source (.uws)')
    parser.add_argument('--strings', help='string block file (default: <program>_strings.txt)')
    parser.add_argument('--quest', action='append', default=[], metavar='ID=VALUE',
                        help='preset a quest flag for get_quest (repeatable)')
    parser.add_argument('--debug', action='store_true', help='trace every instruction')
    args = parser.parse_args(argv)
    
    if not os.path.exists(args.program):
        print(f"Error: '{args.program}' not found")
        return 1

    vm = UltimaUnderworldVM(debug=args.debug)
    for preset in args.quest:
        try:
            quest_id, value = (int(part) for part in preset.split('=', 1))
        except ValueError:
            print(f"Error: --quest expects ID=VALUE, got '{preset}'")
            return 1
        vm.quest_flags[quest_id] = value

    error = load_program(vm, args.program, args.strings)
    if error:
        print(f"Error: {error}")
        return 1

    vm.initialize_memory()
    try:
        vm.execute()
    except VMError as e:
        print(f"\nVM error at PC={vm.pc}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
