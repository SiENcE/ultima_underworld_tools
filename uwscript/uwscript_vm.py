#!/usr/bin/env python3
"""
Ultima Underworld conversation VM.

Runs conversation assembly in the terminal: UWScript output, conversations
decompiled from the game (tools/conversations), and fantasy console
programs (fantasy_console.py subclasses this VM).

    python uwscript_vm.py program.asm                  # strings from program_strings.txt
    python uwscript_vm.py program.uws                  # compile and run in one step
    python uwscript_vm.py conversation_0001.asm --strings strings.txt --set npc_attitude=3

The VM follows the original engine (see uw_engine.py): the memory layout
from the "; Memory Slots:" header, game globals placed where the import
table says, imported functions called by name, the engine's stack, frame
and branch rules, and signed 16-bit arithmetic.
"""

import argparse
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uw_engine import (OPCODES, OPCODE_NAMES, OPCODES_WITH_OPERAND, IMPORTED_FUNCTIONS,  # noqa: E402
                       GAME_GLOBALS, to_word)


class VMError(Exception):
    """A runtime error in the conversation program."""


# UWScript VM extension (not in the game), see func_freeze_string
FREEZE_STRING = 600


class UltimaUnderworldVM:
    """Virtual machine for Ultima Underworld conversations"""

    MEMORY_SIZE = 0x10000
    # Nesting depth for text substitutions that insert other templates
    MAX_SUBSTITUTION_DEPTH = 8
    # Used when an .asm file has no "; Memory Slots:" header
    DEFAULT_MEMORY_SLOTS = 0x60

    def __init__(self, debug=False):
        self.memory = [0] * self.MEMORY_SIZE
        self.stack_pointer = 0      # points at the top value
        self.stack_base = 0         # stack pointer of an empty stack
        self.base_pointer = 0
        self.result_register = 0
        self.pc = 0
        self.call_level = 1

        # Program
        self.code = []
        self.labels = {}
        self.string_literals = []   # strings listed in the compiler's header comments
        self.memory_slots = None    # from "; Memory Slots:"
        self.function_imports = {}  # CALLI id -> function name (import table)
        self.variable_imports = {}  # game global name -> address (import table)
        self.slot_idx = None
        self.string_block = None

        # Strings
        self.string_blocks = {}
        self.current_string_block = None
        self.string_block_id = 0

        # Game state the conversation can see
        self.game_values = {name: default for name, _, default in GAME_GLOBALS}
        self.quest_flags = {}
        self.player_items = set()        # item ids the player carries (find_inv, ...)
        self.npc_items = set()
        self.saved_globals = None        # private globals from an earlier run
        self.globals_file = None         # where to save them at the end

        # Conversation state
        self.finished = False
        self.waiting_response = False
        self.input_func = input
        self.debug = debug

        self.init_opcode_handlers()

        # Imported function handlers by name (dispatched through the import table)
        self.function_handlers = {
            'babl_menu': self.func_babl_menu,
            'babl_fmenu': self.func_babl_fmenu,
            'print': self.func_print,
            'babl_ask': self.func_babl_ask,
            'compare': self.func_compare,
            'random': self.func_random,
            'contains': self.func_contains,
            'length': self.func_length,
            'get_quest': self.func_get_quest,
            'set_quest': self.func_set_quest,
            'sex': self.func_sex,
            'show_inv': self.func_show_inv,
            'give_to_npc': self.func_give_to_npc,
            'give_ptr_npc': self.func_give_ptr_npc,
            'take_from_npc': self.func_take_from_npc,
            'take_id_from_npc': self.func_take_id_from_npc,
            'identify_inv': self.func_identify_inv,
            'do_offer': self.func_do_offer,
            'do_demand': self.func_do_demand,
            'do_inv_create': self.func_do_inv_create,
            'do_inv_delete': self.func_do_inv_delete,
            'check_inv_quality': self.func_check_inv_quality,
            'set_inv_quality': self.func_set_inv_quality,
            'count_inv': self.func_count_inv,
            'setup_to_barter': self.func_setup_to_barter,
            'end_barter': self.func_end_barter,
            'do_judgement': self.func_do_judgement,
            'do_decline': self.func_do_decline,
            'set_likes_dislikes': self.func_set_likes_dislikes,
            'gronk_door': self.func_gronk_door,
            'set_race_attitude': self.func_set_race_attitude,
            'place_object': self.func_place_object,
            'take_from_npc_inv': self.func_take_from_npc_inv,
            'add_to_npc_inv': self.func_add_to_npc_inv,
            'remove_talker': self.func_remove_talker,
            'set_attitude': self.func_set_attitude,
            'x_skills': self.func_x_skills,
            'x_traps': self.func_x_traps,
            'x_obj_pos': self.func_x_obj_pos,
            'x_obj_stuff': self.func_x_obj_stuff,
            'find_inv': self.func_find_inv,
            'find_barter': self.func_find_barter,
            'find_barter_total': self.func_find_barter_total,
        }
        # Handlers by CALLI id, used when the program has no import table
        # entry for an id (hand-written assembly, fantasy console functions)
        self.imported_functions = {}
        for func_id, (name, _) in IMPORTED_FUNCTIONS.items():
            self.imported_functions[func_id] = self.function_handlers.get(name, self._not_implemented(name))
        self.imported_functions[FREEZE_STRING] = self.func_freeze_string

        # Inventory simulation for the barter functions
        self._next_inventory_pos = 1
        self.item_qualities = {}

    def log(self, *args, **kwargs):
        """Log messages only when debug mode is enabled"""
        if self.debug:
            print(*args, **kwargs)

    def init_opcode_handlers(self):
        """Map opcodes to their handlers"""
        handlers = {
            'NOP': self.op_nop, 'OPADD': self.op_add, 'OPMUL': self.op_mul, 'OPSUB': self.op_sub,
            'OPDIV': self.op_div, 'OPMOD': self.op_mod, 'OPOR': self.op_or, 'OPAND': self.op_and,
            'OPNOT': self.op_not, 'TSTGT': self.op_tstgt, 'TSTGE': self.op_tstge, 'TSTLT': self.op_tstlt,
            'TSTLE': self.op_tstle, 'TSTEQ': self.op_tsteq, 'TSTNE': self.op_tstne, 'JMP': self.op_jmp,
            'BEQ': self.op_beq, 'BNE': self.op_bne, 'BRA': self.op_bra, 'CALL': self.op_call,
            'CALLI': self.op_calli, 'RET': self.op_ret, 'PUSHI': self.op_pushi,
            'PUSHI_EFF': self.op_pushi_eff, 'POP': self.op_pop, 'SWAP': self.op_swap,
            'PUSHBP': self.op_pushbp, 'POPBP': self.op_popbp, 'SPTOBP': self.op_sptobp,
            'BPTOSP': self.op_bptosp, 'ADDSP': self.op_addsp, 'FETCHM': self.op_fetchm,
            'STO': self.op_sto, 'OFFSET': self.op_offset, 'START': self.op_start,
            'SAVE_REG': self.op_save_reg, 'PUSH_REG': self.op_push_reg, 'EXIT_OP': self.op_exit_op,
            'SAY_OP': self.op_say_op, 'OPNEG': self.op_opneg,
        }
        self.opcode_handlers = {OPCODES[name]: handler for name, handler in handlers.items()}

    # -- strings ------------------------------------------------------------

    def load_string_blocks(self, filename):
        """Load string blocks from a strings file (the strings.pak dump format)"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                text = f.read()
        except OSError as e:
            print(f"Error loading string blocks: {e}")
            return False
        return self.load_string_blocks_text(text)

    def load_string_blocks_text(self, text):
        """Load string blocks from the text of a strings file"""
        current_block_id = None
        current_block = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("block:"):
                if current_block_id is not None:
                    self.string_blocks[current_block_id] = current_block
                # block ids are hex (like 0f0c)
                try:
                    current_block_id = int(line.split(";")[0].split(":")[1].strip(), 16)
                except ValueError:
                    print(f"Error: bad string block header: {line}")
                    return False
                current_block = ['']
                continue
            # "<index>: <text>"; keep trailing spaces
            if current_block_id is not None and ":" in raw_line:
                index_part, entry = raw_line.split(":", 1)
                if index_part.strip().isdigit():
                    idx = int(index_part.strip())
                    if entry.startswith(' '):
                        entry = entry[1:]
                    while len(current_block) <= idx:
                        current_block.append('')
                    current_block[idx] = self.unescape_string(entry)
        if current_block_id is not None:
            self.string_blocks[current_block_id] = current_block
        self.log(f"Loaded {len(self.string_blocks)} string blocks")
        return True

    @staticmethod
    def unescape_string(text):
        """Turn \\n, \\t and \\\\ in string files into the real characters"""
        return re.sub(r'\\([nt\\])', lambda m: {'n': '\n', 't': '\t', '\\': '\\'}[m.group(1)], text)

    def set_string_block(self, block_id):
        """Set the active string block"""
        if block_id in self.string_blocks:
            self.current_string_block = self.string_blocks[block_id]
            self.string_block_id = block_id
            self.log(f"Using string block {block_id} with {len(self.current_string_block)} strings")
            return True
        print(f"String block {block_id} not found")
        return False

    def allocate_string(self, text):
        """Add a string at runtime (like babl_ask) and return its id"""
        if self.current_string_block is None:
            self.current_string_block = ['']
        self.current_string_block.append(text)
        return len(self.current_string_block) - 1

    def get_string_raw(self, string_id):
        """A string without text substitutions"""
        if not self.current_string_block:
            return "[No string block loaded]"
        if 0 <= string_id < len(self.current_string_block):
            return self.current_string_block[string_id]
        return f"[Invalid string ID: {string_id}]"

    def get_string(self, string_id, depth=0):
        """A string with its text substitutions filled in"""
        if not self.current_string_block:
            return "[No string block loaded]"
        if 0 <= string_id < len(self.current_string_block):
            return self.process_text_substitutions(self.current_string_block[string_id], depth)
        return f"[Invalid string ID: {string_id}]"

    def process_text_substitutions(self, text, depth=0):
        """Fill in @XY<num>[C<index>] codes (conversation_spec.txt 7.5).

        X: G = global at address num, S = stack value at BP + num, P = value
        pointed to by the stack value at BP + num. Y: S = string id, I =
        integer. C<index> takes element <index> of an array. A substituted
        string may contain codes itself (UWScript builds strings that way);
        those are expanded up to MAX_SUBSTITUTION_DEPTH levels.
        """
        def substitute(match):
            source, kind, num, index = match.group(1), match.group(2), int(match.group(3)), match.group(4)
            if source == 'G':
                address = num
            elif source == 'S':
                address = self.base_pointer + num
            else:
                address = self.get_mem(self.base_pointer + num)
            if index is not None:
                address += int(index)
            value = self.get_mem(address)
            if kind == 'I':
                return str(value)
            if depth + 1 >= self.MAX_SUBSTITUTION_DEPTH:
                return self.get_string_raw(value)
            return self.get_string(value, depth + 1)

        return re.sub(r'@([GSP])([SI])(-?\d+)(?:C(\d+))?', substitute, text)

    def _string_text(self, string_id):
        if self.current_string_block and 0 <= string_id < len(self.current_string_block):
            return self.get_string(string_id)
        return None

    # -- loading ------------------------------------------------------------

    def parse_asm(self, filename):
        """Load an .asm file. Returns False on errors."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                text = f.read()
        except OSError as e:
            print(f"Error reading {filename}: {e}")
            return False
        return self.parse_asm_text(text)

    def parse_asm_text(self, text):
        """Load assembly source. Returns False on errors."""
        lines = text.splitlines()
        self.function_imports = {}
        self.variable_imports = {}
        self.string_literals = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith(';'):
                break  # header comments end at the first instruction
            match = re.match(r'^;\s*(\d+): "(.*)"', line)
            if match:
                self.string_literals.append(match.group(2))
                continue
            match = re.match(r'^;\s*Slot:\s*(0x[0-9A-Fa-f]+|[0-9A-Fa-f]+)\s*$', line)
            if match:
                self.slot_idx = int(match.group(1), 16)
                continue
            match = re.match(r'^;\s*String Block:\s*(\d+)\s*$', line)
            if match:
                self.string_block = int(match.group(1))
                self.set_string_block(self.string_block)
                continue
            match = re.match(r'^;\s*Memory Slots:\s*(0x[0-9A-Fa-f]+|\d+)\s*$', line)
            if match:
                self.memory_slots = int(match.group(1), 0)
                continue
            match = re.match(r'^;\s*Import \d+: Function (\w+), ID: (0x[0-9A-Fa-f]+|\d+)', line)
            if match:
                self.function_imports[int(match.group(2), 0)] = match.group(1)
                continue
            match = re.match(r'^;\s*Import \d+: Variable (\w+), Addr: (0x[0-9A-Fa-f]+|\d+)', line)
            if match:
                self.variable_imports[match.group(1)] = int(match.group(2), 0)

        # Strip comments; split labels from instructions
        program = []
        for number, line in enumerate(lines, 1):
            line = line.split(';', 1)[0].strip()
            if not line:
                continue
            if line.endswith(':'):
                program.append((number, line[:-1].strip(), None, None))
                continue
            parts = line.split(None, 1)
            program.append((number, None, parts[0].upper(), parts[1].strip() if len(parts) > 1 else None))

        # First pass: label addresses (in words)
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

        # Second pass: code
        self.code = []
        pc = 0
        for number, label, opcode_name, arg_str in program:
            if label is not None:
                continue
            try:
                if opcode_name not in OPCODES:
                    raise VMError(f"Unknown instruction '{opcode_name}'")
                if (arg_str is not None) != (opcode_name in OPCODES_WITH_OPERAND):
                    raise VMError(f"'{opcode_name}' " + ("takes no operand" if arg_str is not None
                                                         else "needs an operand"))
                self.code.append(OPCODES[opcode_name])
                if arg_str is not None:
                    self.code.append(self._resolve_argument(arg_str, opcode_name, pc))
                    pc += 2
                else:
                    pc += 1
            except VMError as e:
                print(f"Error: line {number}: {e}")
                return False

        self.log(f"Loaded {len(self.code)} code words, {len(self.labels)} labels, "
                 f"{len(self.function_imports)} imported functions, {len(self.variable_imports)} imported globals")
        return True

    def _resolve_argument(self, arg_str, opcode_name, pc):
        """An operand word: a number or a label"""
        if arg_str in self.labels:
            target = self.labels[arg_str]
            if opcode_name in ('BEQ', 'BNE', 'BRA'):
                # relative to the operand word
                return (target - (pc + 1)) & 0xFFFF
            if opcode_name in ('JMP', 'CALL'):
                return target
        try:
            return int(arg_str, 0) & 0xFFFF
        except ValueError:
            raise VMError(f"Unknown label or invalid number '{arg_str}'")

    def get_opcode(self, opcode_name):
        """Numeric value of an opcode name"""
        if opcode_name not in OPCODES:
            raise VMError(f"Unknown instruction '{opcode_name}'")
        return OPCODES[opcode_name]

    def get_opcode_name(self, opcode):
        """Name of an opcode value"""
        return OPCODE_NAMES.get(opcode, f"UNKNOWN(0x{opcode:02X})")

    def initialize_memory(self):
        """Set up memory like the game does when a conversation starts"""
        self.memory = [0] * self.MEMORY_SIZE
        slots = self.memory_slots if self.memory_slots is not None else self.DEFAULT_MEMORY_SLOTS

        # Private globals saved by an earlier conversation
        if self.saved_globals:
            for address, value in enumerate(self.saved_globals[:slots]):
                self.memory[address] = value

        # Game globals go to the addresses in the import table
        # (all of them at 0..30 for programs without an import table)
        placement = self.variable_imports or {name: address for address, (name, _, _) in enumerate(GAME_GLOBALS)}
        types = {name: vtype for name, vtype, _ in GAME_GLOBALS}
        for name, address in placement.items():
            value = self.game_values.get(name, 0)
            if types.get(name) == 'string':
                value = self.allocate_string(str(value))
            self.memory[address & 0xFFFF] = to_word(int(value))

        self.stack_pointer = self.stack_base = slots
        self.base_pointer = slots
        self.result_register = 0
        self.call_level = 1
        self.finished = False
        self.log(f"Memory: {slots} memory slots, stack from {slots + 1}")

    # -- memory and stack ---------------------------------------------------

    @staticmethod
    def word(value):
        """Wrap a value to a signed 16-bit word"""
        return to_word(value)

    @staticmethod
    def divide(a, b):
        """Integer division and remainder that truncate toward zero (as in C)"""
        if b == 0:
            return 0, 0
        quotient = abs(a) // abs(b)
        if (a < 0) != (b < 0):
            quotient = -quotient
        return quotient, a - b * quotient

    @property
    def stack(self):
        """The values on the stack (bottom first), for debugging"""
        return self.memory[self.stack_base + 1:self.stack_pointer + 1]

    def get_mem(self, address):
        """Read a word (addresses are 16-bit, so -1 is 65535)"""
        return self.memory[address & 0xFFFF]

    def set_mem(self, address, value):
        """Write a word (addresses are 16-bit, so -1 is 65535)"""
        self.memory[address & 0xFFFF] = value

    def push(self, value):
        if self.stack_pointer + 1 >= self.MEMORY_SIZE:
            raise VMError("Stack overflow (runaway recursion or a loop that never pops?)")
        self.stack_pointer += 1
        self.memory[self.stack_pointer] = value

    def pop(self):
        if self.stack_pointer <= self.stack_base:
            raise VMError("Stack underflow")
        value = self.memory[self.stack_pointer]
        self.stack_pointer -= 1
        return value

    def debug_memory(self, start, count):
        """Print memory contents"""
        for address in range(start, start + count):
            print(f"  [{address:04X}]: {self.get_mem(address)}")

    def debug_stack(self):
        """Print the stack"""
        print(f"Stack (BP={self.base_pointer}, SP={self.stack_pointer}): {self.stack}")

    # -- execution ----------------------------------------------------------

    def execute(self):
        """Run the conversation from the start"""
        self.pc = 0
        self._run()

    def _run(self):
        while not self.finished and not self.waiting_response and self.pc < len(self.code):
            opcode = self.code[self.pc]
            handler = self.opcode_handlers.get(opcode)
            if handler is None:
                raise VMError(f"Unknown opcode 0x{opcode:02X} at PC={self.pc}")
            if self.debug:
                name = self.get_opcode_name(opcode)
                arg = f" {self.code[self.pc + 1]}" if name in OPCODES_WITH_OPERAND else ""
                print(f"{self.pc:04X}: {name}{arg}   SP={self.stack_pointer} BP={self.base_pointer}")
            handler()
        if self.pc >= len(self.code) and not self.finished:
            self.log("End of code reached")
            self.finish_conversation()

    def resume_conversation(self, choice=None):
        """Continue after the player answered"""
        if choice is not None:
            self.result_register = choice
        self.waiting_response = False
        self._run()

    def finish_conversation(self):
        """End the conversation: copy game globals back, save private globals"""
        if self.finished:
            return
        print("\nConversation finished")
        self.finished = True

        placement = self.variable_imports or {name: address for address, (name, _, _) in enumerate(GAME_GLOBALS)}
        types = {name: vtype for name, vtype, _ in GAME_GLOBALS}
        for name, address in placement.items():
            value = self.get_mem(address)
            if types.get(name) == 'string':
                value = self.get_string(value)
            if value != self.game_values.get(name):
                self.log(f"Game global {name} changed to {value!r}")
            self.game_values[name] = value

        if self.globals_file:
            self.save_state(self.globals_file)

    def save_state(self, path):
        """Save the private globals, the game globals and the quest flags (JSON)"""
        slots = self.memory_slots if self.memory_slots is not None else self.DEFAULT_MEMORY_SLOTS
        state = {'private_globals': self.memory[:slots], 'game_globals': self.game_values,
                 'quest_flags': {str(k): v for k, v in self.quest_flags.items()}}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=1)
        self.log(f"Saved the conversation state to {path}")

    def load_state(self, path):
        """Load a state saved by save_state (call before initialize_memory)"""
        with open(path, encoding='utf-8') as f:
            state = json.load(f)
        self.saved_globals = state.get('private_globals')
        self.game_values.update(state.get('game_globals', {}))
        self.quest_flags.update({int(k): v for k, v in state.get('quest_flags', {}).items()})

    def _operand(self):
        return self.code[self.pc + 1]

    def _binary(self, operation):
        b = self.pop()
        a = self.pop()
        self.push(operation(a, b))
        self.pc += 1

    def op_nop(self):
        self.pc += 1

    def op_add(self):
        self._binary(lambda a, b: to_word(a + b))

    def op_mul(self):
        self._binary(lambda a, b: to_word(a * b))

    def op_sub(self):
        self._binary(lambda a, b: to_word(a - b))

    def op_div(self):
        self._binary(lambda a, b: to_word(self.divide(a, b)[0]))

    def op_mod(self):
        self._binary(lambda a, b: to_word(self.divide(a, b)[1]))

    def op_or(self):
        self._binary(lambda a, b: 1 if (a or b) else 0)

    def op_and(self):
        self._binary(lambda a, b: 1 if (a and b) else 0)

    def op_not(self):
        self.push(1 if self.pop() == 0 else 0)
        self.pc += 1

    def op_tstgt(self):
        self._binary(lambda a, b: 1 if a > b else 0)

    def op_tstge(self):
        self._binary(lambda a, b: 1 if a >= b else 0)

    def op_tstlt(self):
        self._binary(lambda a, b: 1 if a < b else 0)

    def op_tstle(self):
        self._binary(lambda a, b: 1 if a <= b else 0)

    def op_tsteq(self):
        self._binary(lambda a, b: 1 if a == b else 0)

    def op_tstne(self):
        self._binary(lambda a, b: 1 if a != b else 0)

    def op_jmp(self):
        self.pc = self._operand()

    def _branch(self, taken):
        # Relative to the operand word
        self.pc = self.pc + 1 + to_word(self._operand()) if taken else self.pc + 2

    def op_beq(self):
        self._branch(self.pop() == 0)

    def op_bne(self):
        self._branch(self.pop() != 0)

    def op_bra(self):
        self._branch(True)

    def op_call(self):
        self.push(self.pc + 1)  # the address of the operand word
        self.pc = self._operand()
        self.call_level += 1

    def op_ret(self):
        self.call_level -= 1
        if self.call_level <= 0:
            self.finish_conversation()
            return
        self.pc = self.pop() + 1

    def op_calli(self):
        """Call an imported function.

        The function finds the argument count on top of the stack and the
        argument pointers below it, and leaves them for the caller to pop.
        Handlers may pop them to read them; the stack is restored after.
        """
        func_id = self._operand()
        name = self.function_imports.get(func_id)
        handler = self.function_handlers.get(name) if name else None
        if handler is None:
            handler = self.imported_functions.get(func_id)
        if handler is None:
            raise VMError(f"Unknown imported function {name or func_id}")
        saved_sp = self.stack_pointer
        handler()
        self.stack_pointer = saved_sp
        self.pc += 2

    def op_pushi(self):
        self.push(to_word(self._operand()))
        self.pc += 2

    def op_pushi_eff(self):
        self.push(self.base_pointer + to_word(self._operand()))
        self.pc += 2

    def op_pop(self):
        self.pop()
        self.pc += 1

    def op_swap(self):
        b = self.pop()
        a = self.pop()
        self.push(b)
        self.push(a)
        self.pc += 1

    def op_pushbp(self):
        self.push(self.base_pointer)
        self.pc += 1

    def op_popbp(self):
        self.base_pointer = self.pop()
        self.pc += 1

    def op_sptobp(self):
        self.base_pointer = self.stack_pointer
        self.pc += 1

    def op_bptosp(self):
        self.stack_pointer = self.base_pointer
        self.pc += 1

    def op_addsp(self):
        for _ in range(max(0, self.pop())):
            self.push(0)
        self.pc += 1

    def op_fetchm(self):
        self.push(self.get_mem(self.pop()))
        self.pc += 1

    def op_sto(self):
        value = self.pop()
        self.set_mem(self.pop(), value)
        self.pc += 1

    def op_offset(self):
        """Array offset: address + index - 1"""
        index = self.pop()
        base = self.pop()
        self.push(base + index - 1)
        self.pc += 1

    def op_start(self):
        self.pc += 1

    def op_save_reg(self):
        self.result_register = self.pop()
        self.pc += 1

    def op_push_reg(self):
        self.push(self.result_register)
        self.pc += 1

    def op_exit_op(self):
        self.finish_conversation()

    def op_say_op(self):
        print(f'NPC: "{self.get_string(self.pop())}"')
        self.pc += 1

    def op_opneg(self):
        self.push(to_word(-self.pop()))
        self.pc += 1

    # -- imported function helpers ----------------------------------------------

    def pop_args(self):
        """Pop the argument count and the argument pointers: [arg1, arg2, ...]"""
        count = self.pop()
        return [self.pop() for _ in range(max(0, count))]

    def arg_values(self):
        """The values the argument pointers point to"""
        return [self.get_mem(ptr) for ptr in self.pop_args()]

    def read_array(self, address, end=0, limit=256):
        """Read words from address until `end` (not included)"""
        values = []
        while len(values) < limit and self.get_mem(address + len(values)) != end:
            values.append(self.get_mem(address + len(values)))
        return values

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

    @staticmethod
    def _not_implemented(name):
        def handler():
            raise VMError(f"Imported function '{name}' is not used in Ultima Underworld 1 and not implemented")
        return handler

    # -- dialogue -----------------------------------------------------------

    def func_babl_menu(self):
        """Show a menu; arg1 is a 0-terminated list of string ids. Result: 1-based choice"""
        options = [self.get_string(string_id) for string_id in self.read_array(self.pop_args()[0])]
        choice = self.choose_option(options)
        self.result_register = 0 if choice is None else choice + 1

    def func_babl_fmenu(self):
        """Menu with flags: arg1 string ids (0-terminated), arg2 flags (non-zero = shown)"""
        strings_ptr, flags_ptr = self.pop_args()[:2]
        options, positions = [], []
        for i, string_id in enumerate(self.read_array(strings_ptr)):
            if self.get_mem(flags_ptr + i) != 0:
                options.append(self.get_string(string_id))
                positions.append(i + 1)
        choice = self.choose_option(options)
        # The result is the position in the full list, not among the shown options
        self.result_register = 0 if choice is None else positions[choice]

    def func_print(self):
        """Print a text that no one speaks (scene description)"""
        print(f'PRINT: "{self.get_string(self.arg_values()[0])}"')

    def func_babl_ask(self):
        """Let the player type a text; the result is the id of a new string"""
        print("\nEnter text:")
        text = self.read_input("> ")
        self.result_register = 0 if text is None else self.allocate_string(text)

    def func_compare(self):
        """1 if two strings are equal, ignoring case"""
        id1, id2 = self.arg_values()[:2]
        str1, str2 = self._string_text(id1), self._string_text(id2)
        if str1 is None or str2 is None:
            print(f"COMPARE: Invalid string IDs: {id1}, {id2}")
            self.result_register = 0
            return
        self.result_register = 1 if str1.strip().lower() == str2.strip().lower() else 0

    def func_random(self):
        """Random number in the range [1..arg1]"""
        max_val = self.arg_values()[0]
        self.result_register = random.randint(1, max_val) if max_val >= 1 else 1

    def func_contains(self):
        """1 if the first string contains the second one, ignoring case"""
        id1, id2 = self.arg_values()[:2]
        str1, str2 = self._string_text(id1), self._string_text(id2)
        if str1 is None or str2 is None:
            print(f"CONTAINS: Invalid string IDs: {id1}, {id2}")
            self.result_register = 0
            return
        self.result_register = 1 if str2.lower() in str1.lower() else 0

    def func_length(self):
        """Length of a string"""
        text = self._string_text(self.arg_values()[0])
        self.result_register = 0 if text is None else len(text)

    def func_sex(self):
        """arg1 for a female avatar, arg2 for a male one (play_sex: 0 male)"""
        female, male = self.arg_values()[:2]
        self.result_register = male if int(self.game_values.get('play_sex', 0)) == 0 else female

    # -- quests and world ---------------------------------------------------

    def func_get_quest(self):
        """Value of a quest flag (0 unless set, or preset with --quest)"""
        self.result_register = self.quest_flags.get(self.arg_values()[0], 0)

    def func_set_quest(self):
        """Set a quest flag: arg1 is the new value, arg2 the quest number"""
        value, quest_id = self.arg_values()[:2]
        self.quest_flags[quest_id] = value
        print(f"SET_QUEST: Setting quest {quest_id} to {value}")

    def func_gronk_door(self):
        """Open (flag 0) or close a door: gronk_door(x, y, flag)"""
        x, y, flag = self.arg_values()[:3]
        print(f"GRONK_DOOR: {'Opening' if flag == 0 else 'Closing'} door at ({x}, {y})")
        self.result_register = 1

    def func_set_race_attitude(self):
        print(f"SET_RACE_ATTITUDE: {self.arg_values()}")

    def func_place_object(self):
        x, y, slot = (self.arg_values() + [0, 0, 0])[:3]
        print(f"PLACE_OBJECT: inventory slot {slot} at ({x}, {y})")

    def func_remove_talker(self):
        self.pop_args()
        print("REMOVE_TALKER: The NPC leaves")

    def func_set_attitude(self):
        args = self.arg_values()
        print(f"SET_ATTITUDE: {args}")

    def func_x_skills(self):
        print(f"X_SKILLS: {self.arg_values()}")
        self.result_register = 0

    def func_x_traps(self):
        print(f"X_TRAPS: {self.arg_values()}")
        self.result_register = 0

    def func_x_obj_pos(self):
        print(f"X_OBJ_POS: {self.arg_values()}")

    def func_x_obj_stuff(self):
        print(f"X_OBJ_STUFF: {self.arg_values()}")

    # -- inventory and bartering (simulated) -------------------------------------

    def func_show_inv(self):
        """Copy the player's barter area to arg1 (positions) and arg2 (object ids)"""
        positions_ptr, ids_ptr = self.pop_args()[:2]
        items = sorted(self.player_items)[:4]
        for i, item in enumerate(items):
            self.set_mem(positions_ptr + i, i + 1)
            self.set_mem(ids_ptr + i, item)
        self.result_register = len(items)

    def func_give_to_npc(self):
        """Give arg2 items (inventory positions in the array arg1) to the NPC"""
        list_ptr, count = self.pop_args()[:2]
        count = self.get_mem(count)
        print(f"GIVE_TO_NPC: {count} item(s)")
        self.result_register = 1 if count > 0 else 0

    def func_give_ptr_npc(self):
        quantity, position = self.arg_values()[:2]
        print(f"GIVE_PTR_NPC: item at {position} (quantity {quantity})")
        self.result_register = 1

    def func_take_from_npc(self):
        """Give the player an item (id, or a category if > 1000). 1: ok, 2: no room"""
        item = self.arg_values()[0]
        self.player_items.add(item)
        print(f"TAKE_FROM_NPC: The player receives item {item}")
        self.result_register = 1

    def func_take_id_from_npc(self):
        print(f"TAKE_ID_FROM_NPC: item at {self.arg_values()[0]}")
        self.result_register = 1

    def func_identify_inv(self):
        self.arg_values()
        self.result_register = 0

    def func_do_offer(self):
        """Is the deal in the barter areas acceptable? (the VM always accepts)"""
        print(f"DO_OFFER: {self.arg_values()} -> accepted")
        self.result_register = 1

    def func_do_demand(self):
        """Does the NPC give in to a demand? (the VM says yes)"""
        refuse_text, agree_text = self.arg_values()[:2]
        print(f'DO_DEMAND: "{self.get_string(agree_text)}"')
        self.result_register = 1

    def func_do_inv_create(self):
        """Create an item in the NPC's inventory; returns its inventory position"""
        item = self.arg_values()[0]
        self.npc_items.add(item)
        position = self._next_inventory_pos
        self._next_inventory_pos += 1
        print(f"DO_INV_CREATE: item {item} at position {position}")
        self.result_register = position

    def func_do_inv_delete(self):
        item = self.arg_values()[0]
        self.npc_items.discard(item)
        print(f"DO_INV_DELETE: item {item}")
        self.result_register = 1

    def func_check_inv_quality(self):
        self.result_register = self.item_qualities.get(self.arg_values()[0], 0)

    def func_set_inv_quality(self):
        quality, position = self.arg_values()[:2]
        self.item_qualities[position] = quality
        self.result_register = 1

    def func_count_inv(self):
        self.arg_values()
        self.result_register = len(self.player_items)

    def func_setup_to_barter(self):
        self.pop_args()
        print("SETUP_TO_BARTER")

    def func_end_barter(self):
        self.pop_args()
        print("END_BARTER")

    def func_do_judgement(self):
        self.pop_args()
        print("DO_JUDGEMENT: That seems a fair trade.")

    def func_do_decline(self):
        self.pop_args()
        print("DO_DECLINE")

    def func_set_likes_dislikes(self):
        """arg1/arg2: lists of item types the NPC likes/dislikes, ending with -1"""
        likes_ptr, dislikes_ptr = self.pop_args()[:2]
        print(f"SET_LIKES_DISLIKES: likes {self.read_array(likes_ptr, -1)}, "
              f"dislikes {self.read_array(dislikes_ptr, -1)}")

    def func_take_from_npc_inv(self):
        self.arg_values()
        self.result_register = 1

    def func_add_to_npc_inv(self):
        print(f"ADD_TO_NPC_INV: {self.arg_values()}")

    def func_find_inv(self):
        """Find an item: arg1 0 = NPC inventory, 1 = player; result 0 if not found"""
        where, item = self.arg_values()[:2]
        items = self.player_items if where == 1 else self.npc_items
        self.result_register = (sorted(items).index(item) + 1) if item in items else 0

    def func_find_barter(self):
        item = self.arg_values()[0]
        self.result_register = 1 if item in self.player_items else 0

    def func_find_barter_total(self):
        self.pop_args()
        self.result_register = 0

    def func_freeze_string(self):
        """UWScript VM extension: expand a string template now into a new string"""
        self.result_register = self.allocate_string(self._string_text(self.arg_values()[0]) or "")


def load_program(vm, program, strings=None, block=1, target='uw'):
    """Load a .asm file (or compile a .uws file) and its strings into the VM.

    Returns an error message or None.
    """
    stem, ext = os.path.splitext(program)
    if ext.lower() == '.uws':
        from uwscript_compiler import compile_uwscript, UWScriptError
        try:
            with open(program, 'r', encoding='utf-8') as f:
                result = compile_uwscript(f.read(), block, source_name=os.path.basename(program),
                                          target=target)
        except UWScriptError as e:
            return f"{program}: error: {e}"
        if strings:
            vm.load_string_blocks(strings)
        else:
            vm.load_string_blocks_text(result['strings'])
        if not vm.parse_asm_text(result['assembly']):
            return "Could not load the compiled assembly"
        return None

    if not strings:
        # <program>_strings.txt (UWScript), else the full dump from uw-strings-extractor.py
        candidates = [f"{stem}_strings.txt", os.path.join(os.path.dirname(program), "uw-strings.txt"),
                      "uw-strings.txt"]
        strings = next((path for path in candidates if os.path.exists(path)), candidates[0])
    if not os.path.exists(strings):
        return f"String block file '{strings}' not found (use --strings)"
    if not vm.load_string_blocks(strings):
        return f"Could not load '{strings}'"
    if not vm.parse_asm(program):
        return f"Could not load '{program}'"
    return None


def _parse_assignment(text, option):
    if '=' not in text:
        raise ValueError(f"{option} expects NAME=VALUE, got '{text}'")
    name, value = text.split('=', 1)
    return name.strip(), value.strip()


def main(argv=None):
    """Run a conversation in the terminal"""
    parser = argparse.ArgumentParser(
        description='Run an Ultima Underworld conversation (.asm, or UWScript .uws).')
    parser.add_argument('program', help='conversation assembly (.asm) or UWScript source (.uws)')
    parser.add_argument('--strings', help='string block file (default: <program>_strings.txt)')
    parser.add_argument('--quest', action='append', default=[], metavar='ID=VALUE',
                        help='preset a quest flag (repeatable)')
    parser.add_argument('--set', action='append', default=[], metavar='NAME=VALUE',
                        help='set a game global, e.g. npc_attitude=3 or play_name=Shanra (repeatable)')
    parser.add_argument('--item', action='append', default=[], type=int, metavar='ID',
                        help='an item id the player carries (repeatable)')
    parser.add_argument('--globals', metavar='FILE',
                        help='load the conversation state (private globals, game globals, quest flags) '
                             'from FILE if it exists, and save it there at the end, to replay later talks')
    parser.add_argument('--debug', action='store_true', help='trace every instruction')
    args = parser.parse_args(argv)

    if not os.path.exists(args.program):
        print(f"Error: '{args.program}' not found")
        return 1

    vm = UltimaUnderworldVM(debug=args.debug)
    if args.globals:
        vm.globals_file = args.globals
        if os.path.exists(args.globals):
            vm.load_state(args.globals)
    try:
        for preset in args.quest:
            quest_id, value = _parse_assignment(preset, '--quest')
            vm.quest_flags[int(quest_id, 0)] = int(value, 0)
        for preset in args.set:
            name, value = _parse_assignment(preset, '--set')
            if name not in vm.game_values:
                raise ValueError(f"Unknown game global '{name}' "
                                 f"(known: {', '.join(n for n, _, _ in GAME_GLOBALS)})")
            vm.game_values[name] = value if isinstance(vm.game_values[name], str) else int(value, 0)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    vm.player_items.update(args.item)

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
