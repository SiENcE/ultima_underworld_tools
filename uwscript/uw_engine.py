"""
Facts about Ultima Underworld's conversation engine, shared by the UWScript
compiler, the VM (uwscript_vm.py) and the tests.

Sources: docs/conversation_spec.txt and the conversation VM of Underworld
Adventures (https://github.com/vividos/UnderworldAdventures, conv/CodeVM.cpp),
which runs the original conversations.

Engine behaviour that the compiler and the VM rely on:
- Memory is an array of 16-bit words. The words below the "memory slots"
  count from the conversation header hold the conversation's globals; the
  stack starts right after them and grows upwards. The stack pointer points
  at the top value (push = pre-increment).
- Imported game globals (player and NPC properties) are copied to the
  addresses listed in the import table when the conversation starts and
  copied back when it ends. Everything below "memory slots" is saved as the
  conversation's private globals.
- SPTOBP makes BP point at the saved frame pointer, so PUSHI_EFF n
  addresses BP + n: locals are at 1, 2, ...; with N arguments, argument i
  (0-based) is at -(1 + N - i) (BP - 1 is the return address).
- BEQ/BNE/BRA jump to (address of the operand word) + offset, that is
  instruction address + 1 + offset. JMP and CALL take absolute addresses.
  CALL pushes the address of its operand word; RET continues after it.
- CALLI passes the argument count on top of the stack with pointers to the
  arguments below it (argument 1 right below the count). The function does
  not pop them; the result is in the result register (PUSH_REG).
"""

OPCODES = {
    'NOP': 0x00, 'OPADD': 0x01, 'OPMUL': 0x02, 'OPSUB': 0x03, 'OPDIV': 0x04, 'OPMOD': 0x05,
    'OPOR': 0x06, 'OPAND': 0x07, 'OPNOT': 0x08, 'TSTGT': 0x09, 'TSTGE': 0x0A, 'TSTLT': 0x0B,
    'TSTLE': 0x0C, 'TSTEQ': 0x0D, 'TSTNE': 0x0E, 'JMP': 0x0F, 'BEQ': 0x10, 'BNE': 0x11,
    'BRA': 0x12, 'CALL': 0x13, 'CALLI': 0x14, 'RET': 0x15, 'PUSHI': 0x16, 'PUSHI_EFF': 0x17,
    'POP': 0x18, 'SWAP': 0x19, 'PUSHBP': 0x1A, 'POPBP': 0x1B, 'SPTOBP': 0x1C, 'BPTOSP': 0x1D,
    'ADDSP': 0x1E, 'FETCHM': 0x1F, 'STO': 0x20, 'OFFSET': 0x21, 'START': 0x22, 'SAVE_REG': 0x23,
    'PUSH_REG': 0x24, 'STRCMP': 0x25, 'EXIT_OP': 0x26, 'SAY_OP': 0x27, 'RESPOND_OP': 0x28,
    'OPNEG': 0x29,
}
OPCODE_NAMES = {value: name for name, value in OPCODES.items()}
# Opcodes followed by an operand word
OPCODES_WITH_OPERAND = {'JMP', 'BEQ', 'BNE', 'BRA', 'CALL', 'CALLI', 'PUSHI', 'PUSHI_EFF'}

# Imported functions of Ultima Underworld 1: id -> (name, return type)
# (conversation_spec.txt section 7.6.1). Functions marked "not used in uw1"
# there are included for decompiled code but not offered by UWScript.
IMPORTED_FUNCTIONS = {
    0x00: ('babl_menu', 'int'),
    0x01: ('babl_fmenu', 'int'),
    0x02: ('print', 'void'),
    0x03: ('babl_ask', 'int'),
    0x04: ('compare', 'int'),
    0x05: ('random', 'int'),
    0x06: ('plural', 'string'),
    0x07: ('contains', 'int'),
    0x08: ('append', 'string'),
    0x09: ('copy', 'string'),
    0x0A: ('find', 'int'),
    0x0B: ('length', 'int'),
    0x0C: ('val', 'int'),
    0x0D: ('say', 'void'),
    0x0E: ('respond', 'void'),
    0x0F: ('get_quest', 'int'),
    0x10: ('set_quest', 'void'),
    0x11: ('sex', 'string'),
    0x12: ('show_inv', 'int'),
    0x13: ('give_to_npc', 'int'),
    0x14: ('give_ptr_npc', 'int'),
    0x15: ('take_from_npc', 'int'),
    0x16: ('take_id_from_npc', 'int'),
    0x17: ('identify_inv', 'int'),
    0x18: ('do_offer', 'int'),
    0x19: ('do_demand', 'int'),
    0x1A: ('do_inv_create', 'int'),
    0x1B: ('do_inv_delete', 'int'),
    0x1C: ('check_inv_quality', 'int'),
    0x1D: ('set_inv_quality', 'int'),
    0x1E: ('count_inv', 'int'),
    0x1F: ('setup_to_barter', 'void'),
    0x20: ('end_barter', 'void'),
    0x21: ('do_judgement', 'void'),
    0x22: ('do_decline', 'void'),
    0x23: ('pause', 'void'),
    0x24: ('set_likes_dislikes', 'void'),
    0x25: ('gronk_door', 'int'),
    0x26: ('set_race_attitude', 'void'),
    0x27: ('place_object', 'void'),
    0x28: ('take_from_npc_inv', 'int'),
    0x29: ('add_to_npc_inv', 'void'),
    0x2A: ('remove_talker', 'void'),
    0x2B: ('set_attitude', 'void'),
    0x2C: ('x_skills', 'int'),
    0x2D: ('x_traps', 'int'),
    0x2E: ('x_obj_pos', 'void'),
    0x2F: ('x_obj_stuff', 'void'),
    0x30: ('find_inv', 'int'),
    0x31: ('find_barter', 'int'),
    0x32: ('find_barter_total', 'int'),
}
FUNCTION_IDS = {name: func_id for func_id, (name, _) in IMPORTED_FUNCTIONS.items()}

# Game globals: (name, type, default value in the VM). The compiler places
# them at addresses 0..30 (the import table records the addresses, the game
# finds the values by name).
GAME_GLOBALS = [
    ('play_hunger', 'int', 0),
    ('play_health', 'int', 30),
    ('play_arms', 'int', 0),
    ('play_power', 'int', 0),
    ('play_hp', 'int', 30),
    ('play_mana', 'int', 30),
    ('play_level', 'int', 3),
    ('new_player_exp', 'int', 0),
    ('play_name', 'string', 'Avatar'),
    ('play_poison', 'int', 0),
    ('play_drawn', 'int', 0),
    ('play_sex', 'int', 0),           # 0 male, 1 female
    ('npc_xhome', 'int', 32),
    ('npc_yhome', 'int', 32),
    ('npc_whoami', 'int', 0),
    ('npc_hunger', 'int', 0),
    ('npc_health', 'int', 30),
    ('npc_hp', 'int', 30),
    ('npc_arms', 'int', 0),
    ('npc_power', 'int', 0),
    ('npc_goal', 'int', 8),
    ('npc_attitude', 'int', 2),       # 0 hostile, 1 upset, 2 mellow, 3 friendly
    ('npc_gtarg', 'int', 0),
    ('npc_talkedto', 'int', 0),
    ('npc_level', 'int', 1),
    ('npc_name', 'string', 'Stranger'),
    ('dungeon_level', 'int', 1),
    ('riddlecounter', 'int', 0),
    ('game_time', 'int', 0),
    ('game_days', 'int', 1),
    ('game_mins', 'int', 0),
]
GAME_GLOBAL_ADDRESSES = {name: address for address, (name, _, _) in enumerate(GAME_GLOBALS)}
GAME_GLOBAL_TYPES = {name: vtype for name, vtype, _ in GAME_GLOBALS}

# First address of UWScript's own (private) globals, after the game globals
PRIVATE_GLOBALS_BASE = 0x20

# Return type codes in import records
RETURN_TYPE_CODES = {'void': 0x0000, 'int': 0x0129, 'string': 0x012B}


def to_word(value: int) -> int:
    """Wrap a value to a signed 16-bit word"""
    return ((value + 0x8000) & 0xFFFF) - 0x8000
