#!/usr/bin/env python3
"""
Ultima Underworld Conversation Extractor and Decompiler

This tool extracts individual conversation slots from the CNV.ARK file
and decompiles the code section to human-readable assembler.
"""

import os
import struct
import argparse
from pathlib import Path
import io

class ArkDecompressor:
    """Decompress Ultima Underworld 2 .ark files."""
    
    @staticmethod
    def decompress(input_data):
        """Decompress UW2 ARK data."""
        if not input_data:
            return b''
            
        output = bytearray()
        i = 0
        
        while i < len(input_data):
            control_byte = input_data[i]
            i += 1
            
            if control_byte & 0x80:  # High bit set - run of bytes
                count = (control_byte & 0x7F) + 3
                if i < len(input_data):
                    value = input_data[i]
                    i += 1
                    output.extend([value] * count)
            else:  # Literal bytes
                count = (control_byte & 0x7F) + 1
                if i + count <= len(input_data):
                    output.extend(input_data[i:i+count])
                    i += count
                else:
                    # Not enough data left
                    break
                    
        return bytes(output)
    
    @staticmethod
    def is_compressed(data):
        """Try to detect if data is compressed."""
        # Simple heuristic: compressed files typically have high entropy
        # and many values with high bit set.
        high_bit_count = sum(1 for b in data[:256] if b & 0x80)
        return high_bit_count > 64  # Threshold can be adjusted
    
    @staticmethod
    def decompress_file(input_file):
        """Decompress a UW2 ARK file and return the decompressed data."""
        with open(input_file, 'rb') as f:
            data = f.read()
            
        if ArkDecompressor.is_compressed(data):
            print(f"File appears to be compressed, decompressing...")
            return ArkDecompressor.decompress(data)
        else:
            print(f"File does not appear to be compressed.")
            return data

class ConversationDecompiler:
    """Decompile Ultima Underworld conversation bytecode to assembly."""
    
    def __init__(self):
        # Opcode definitions - derived from the VM implementation
        self.opcodes = {
            0x00: {"name": "NOP", "operands": 0, "description": "No operation"},
            0x01: {"name": "OPADD", "operands": 0, "description": "Add top two values"},
            0x02: {"name": "OPMUL", "operands": 0, "description": "Multiply top two values"},
            0x03: {"name": "OPSUB", "operands": 0, "description": "Subtract s[0] from s[1]"},
            0x04: {"name": "OPDIV", "operands": 0, "description": "Divide s[1] by s[0]"},
            0x05: {"name": "OPMOD", "operands": 0, "description": "s[1] modulo s[0]"},
            0x06: {"name": "OPOR", "operands": 0, "description": "Logical OR of two values"},
            0x07: {"name": "OPAND", "operands": 0, "description": "Logical AND of two values"},
            0x08: {"name": "OPNOT", "operands": 0, "description": "Logical NOT of top value"},
            0x09: {"name": "TSTGT", "operands": 0, "description": "Test if s[1] > s[0]"},
            0x0A: {"name": "TSTGE", "operands": 0, "description": "Test if s[1] >= s[0]"},
            0x0B: {"name": "TSTLT", "operands": 0, "description": "Test if s[1] < s[0]"},
            0x0C: {"name": "TSTLE", "operands": 0, "description": "Test if s[1] <= s[0]"},
            0x0D: {"name": "TSTEQ", "operands": 0, "description": "Test if s[1] == s[0]"},
            0x0E: {"name": "TSTNE", "operands": 0, "description": "Test if s[1] != s[0]"},
            0x0F: {"name": "JMP", "operands": 1, "description": "Jump to address"},
            0x10: {"name": "BEQ", "operands": 1, "description": "Branch if equal/zero"},
            0x11: {"name": "BNE", "operands": 1, "description": "Branch if not equal/non-zero"},
            0x12: {"name": "BRA", "operands": 1, "description": "Branch always"},
            0x13: {"name": "CALL", "operands": 1, "description": "Call subroutine"},
            0x14: {"name": "CALLI", "operands": 1, "description": "Call imported function"},
            0x15: {"name": "RET", "operands": 0, "description": "Return from subroutine"},
            0x16: {"name": "PUSHI", "operands": 1, "description": "Push immediate value"},
            0x17: {"name": "PUSHI_EFF", "operands": 1, "description": "Push effective address (BP+offset)"},
            0x18: {"name": "POP", "operands": 0, "description": "Pop and discard value"},
            0x19: {"name": "SWAP", "operands": 0, "description": "Swap top two values"},
            0x1A: {"name": "PUSHBP", "operands": 0, "description": "Push frame pointer"},
            0x1B: {"name": "POPBP", "operands": 0, "description": "Pop to frame pointer"},
            0x1C: {"name": "SPTOBP", "operands": 0, "description": "Set frame pointer to stack pointer"},
            0x1D: {"name": "BPTOSP", "operands": 0, "description": "Set stack pointer to frame pointer"},
            0x1E: {"name": "ADDSP", "operands": 0, "description": "Reserve stack space"},
            0x1F: {"name": "FETCHM", "operands": 0, "description": "Fetch from memory"},
            0x20: {"name": "STO", "operands": 0, "description": "Store to memory"},
            0x21: {"name": "OFFSET", "operands": 0, "description": "Calculate array offset"},
            0x22: {"name": "START", "operands": 0, "description": "Program start marker"},
            0x23: {"name": "SAVE_REG", "operands": 0, "description": "Save to result register"},
            0x24: {"name": "PUSH_REG", "operands": 0, "description": "Push result register"},
            0x25: {"name": "STRCMP", "operands": 0, "description": "String comparison"},
            0x26: {"name": "EXIT_OP", "operands": 0, "description": "End program"},
            0x27: {"name": "SAY_OP", "operands": 0, "description": "NPC dialogue"},
            0x28: {"name": "RESPOND_OP", "operands": 0, "description": "Player response"},
            0x29: {"name": "OPNEG", "operands": 0, "description": "Negate value"}
        }
        
        # Instruction format for known opcodes
        self.instruction_patterns = {
            # Jump/branch instructions with address operand
            0x0F: lambda op: f"{self.opcodes[op]['name']} 0x{{:04X}}", # JMP
            0x10: lambda op: f"{self.opcodes[op]['name']} 0x{{:04X}}", # BEQ
            0x11: lambda op: f"{self.opcodes[op]['name']} 0x{{:04X}}", # BNE
            0x12: lambda op: f"{self.opcodes[op]['name']} 0x{{:04X}}", # BRA
            0x13: lambda op: f"{self.opcodes[op]['name']} 0x{{:04X}}", # CALL
            
            # Function and value instructions
            0x14: lambda op: f"{self.opcodes[op]['name']} {{:d}}",     # CALLI
            0x16: lambda op: f"{self.opcodes[op]['name']} 0x{{:04X}}",  # PUSHI
            0x17: lambda op: f"{self.opcodes[op]['name']} {{:d}}",     # PUSHI_EFF
        }
        
        # Track labels for jumps and calls
        self.labels = {}
        
    def decompile(self, code_data):
        """
        Decompile bytecode to assembly instructions.
        
        Args:
            code_data (bytes): The binary code section
            
        Returns:
            list: Decompiled assembly instructions
        """
        # First pass - find potential jump targets and create labels
        self._find_jump_targets(code_data)
        
        # Second pass - decompile instructions
        instructions = []
        pos = 0
        
        while pos < len(code_data):
            label = self.labels.get(pos, "")
            if label:
                instructions.append(f"{label}:")
            
            # Each instruction is at least 2 bytes
            if pos + 2 > len(code_data):
                instructions.append(f"; ERROR: Truncated instruction at offset {pos}")
                break
                
            # Read opcode (first byte)
            opcode = code_data[pos]
            
            # Get information about this opcode
            op_info = self.opcodes.get(opcode, {"name": f"UNKNOWN_{opcode:02X}", "operands": 0})
            
            # Format the instruction based on the opcode
            if opcode in self.instruction_patterns:
                if op_info["operands"] > 0 and pos + 2 + (op_info["operands"] * 2) <= len(code_data):
                    # Read operand (next 2 bytes after opcode)
                    operand = struct.unpack("<H", code_data[pos+2:pos+4])[0]
                    
                    # Format the instruction
                    pattern = self.instruction_patterns[opcode]
                    instr = pattern(opcode).format(operand)
                    
                    # For jumps and calls, add label reference if we have one
                    if opcode in [0x0F, 0x10, 0x11, 0x12, 0x13] and operand * 2 in self.labels:
                        instr += f"  ; -> {self.labels[operand * 2]}"
                    
                    instructions.append(instr)
                    pos += 4  # Skip opcode and operand
                else:
                    # Missing operand
                    instructions.append(f"{op_info['name']}  ; ERROR: Missing operand")
                    pos += 2  # Skip opcode
            else:
                # Opcode without operands or unknown opcode
                instructions.append(op_info["name"])
                pos += 2  # Skip opcode
                
        return instructions
    
    def _find_jump_targets(self, code_data):
        """Find jump targets and create labels."""
        self.labels = {}
        pos = 0
        label_counter = 0
        
        while pos < len(code_data):
            if pos + 2 > len(code_data):
                break
                
            opcode = code_data[pos]
            op_info = self.opcodes.get(opcode, {"operands": 0})
            
            # Check if this is a jump or call instruction
            if opcode in [0x0F, 0x10, 0x11, 0x12, 0x13]:  # JMP, BEQ, BNE, BRA, CALL
                if pos + 4 <= len(code_data):
                    # Get the target address
                    target = struct.unpack("<H", code_data[pos+2:pos+4])[0]
                    target_pos = target * 2  # Convert instruction index to byte offset
                    
                    # Create a label if we don't have one already
                    if target_pos not in self.labels:
                        self.labels[target_pos] = f"label_{label_counter}"
                        label_counter += 1
            
            # Move to next instruction
            pos += 2 + (op_info["operands"] * 2)

class ConversationExtractor:
    def __init__(self, filename, output_dir="conversations", verbose=False):
        self.filename = filename
        self.output_dir = output_dir
        self.verbose = verbose
        self.conversations = []
        self.string_block_offset = 0x0007  # String block for NPC names
        self.data = None
        self.decompiler = ConversationDecompiler()
        
    def log(self, message):
        """Print verbose information if enabled."""
        if self.verbose:
            print(message)
    
    def extract_all(self):
        """Extract all conversation slots from the file."""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Read and decompress file if needed
            self.data = ArkDecompressor.decompress_file(self.filename)
            
            # Use data as a file-like object
            import io
            with io.BytesIO(self.data) as f:
                # Read number of conversation slots
                num_slots = struct.unpack("<H", f.read(2))[0]
                self.log(f"File contains {num_slots} conversation slots")
                
                # Read all offsets
                offsets = []
                for i in range(num_slots):
                    offset = struct.unpack("<I", f.read(4))[0]
                    offsets.append(offset)
                    
                # Process each valid conversation slot
                for slot_idx, offset in enumerate(offsets):
                    if offset == 0:
                        self.log(f"Slot {slot_idx}: Empty")
                        continue
                    
                    self.log(f"Slot {slot_idx}: Offset 0x{offset:08X}")
                    self.extract_conversation(f, slot_idx, offset)
                
                self.log(f"Extracted {len(self.conversations)} conversations")
                return True
                
        except Exception as e:
            print(f"Error extracting conversations: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_conversation(self, f, slot_idx, offset):
        """Extract a single conversation from the given offset."""
        # Seek to the conversation header
        f.seek(offset)
        
        # Read conversation header
        header = {}
        header["unknown1"] = struct.unpack("<H", f.read(2))[0]        # 0x0828
        header["unknown2"] = struct.unpack("<H", f.read(2))[0]        # 0x0000
        header["code_size"] = struct.unpack("<H", f.read(2))[0]       # Code size in instructions
        header["unknown3"] = struct.unpack("<H", f.read(2))[0]        # 0x0000
        header["unknown4"] = struct.unpack("<H", f.read(2))[0]        # 0x0000
        header["string_block"] = struct.unpack("<H", f.read(2))[0]    # Game strings block
        header["memory_slots"] = struct.unpack("<H", f.read(2))[0]    # Number of memory slots
        header["num_imports"] = struct.unpack("<H", f.read(2))[0]     # Number of imported functions
        
        self.log(f"  Header: {header}")
        
        # Calculate the NPC name string reference
        npc_string_index = (slot_idx - 0x0e00 + 16) if slot_idx >= 0x0e00 else None
        
        # Read imports
        imports = []
        for i in range(header["num_imports"]):
            import_record = self._read_import_record(f)
            imports.append(import_record)
            self.log(f"  Import {i}: {import_record['name']}")
        
        # Read code section
        code_start_pos = f.tell()
        code_data = f.read(header["code_size"] * 2)  # Each instruction is 2 bytes
        
        # Decompile the code section
        decompiled_code = self.decompiler.decompile(code_data)
        
        # Store the conversation data
        conversation = {
            "slot_idx": slot_idx,
            "offset": offset,
            "header": header,
            "imports": imports,
            "code_start": code_start_pos,
            "code_data": code_data,
            "npc_string_index": npc_string_index,
            "decompiled_code": decompiled_code
        }
        
        self.conversations.append(conversation)
        
        # Write conversation to file
        self._write_conversation_file(slot_idx, conversation)
    
    def _read_import_record(self, f):
        """Read a single import record."""
        name_length = struct.unpack("<H", f.read(2))[0]
        name = f.read(name_length).decode('ascii', errors='replace')
        id_or_addr = struct.unpack("<H", f.read(2))[0]
        unknown = struct.unpack("<H", f.read(2))[0]
        import_type = struct.unpack("<H", f.read(2))[0]
        return_type = struct.unpack("<H", f.read(2))[0]
        
        return {
            "name_length": name_length,
            "name": name,
            "id_or_addr": id_or_addr,
            "unknown": unknown,
            "import_type": import_type,
            "return_type": return_type,
            "is_variable": import_type == 0x010F,
            "is_function": import_type == 0x0111,
            "return_type_name": self._get_return_type_name(return_type)
        }
    
    def _get_return_type_name(self, return_type):
        """Convert return type code to human-readable name."""
        return_types = {
            0x0000: "void",
            0x0129: "int",
            0x012B: "string"
        }
        return return_types.get(return_type, f"unknown_type_{return_type:04X}")
    
    def _write_conversation_file(self, slot_idx, conversation):
        """Write conversation data to file in a structured format."""
        # Binary file output
        filename = os.path.join(self.output_dir, f"conversation_{slot_idx:04X}.bin")
        with open(filename, "wb") as f:
            # Write the original data from the file
            f.write(struct.pack("<H", conversation["header"]["unknown1"]))
            f.write(struct.pack("<H", conversation["header"]["unknown2"]))
            f.write(struct.pack("<H", conversation["header"]["code_size"]))
            f.write(struct.pack("<H", conversation["header"]["unknown3"]))
            f.write(struct.pack("<H", conversation["header"]["unknown4"]))
            f.write(struct.pack("<H", conversation["header"]["string_block"]))
            f.write(struct.pack("<H", conversation["header"]["memory_slots"]))
            f.write(struct.pack("<H", conversation["header"]["num_imports"]))
            
            # Write imports
            for imp in conversation["imports"]:
                f.write(struct.pack("<H", imp["name_length"]))
                f.write(imp["name"].encode('ascii', errors='replace'))
                f.write(struct.pack("<H", imp["id_or_addr"]))
                f.write(struct.pack("<H", imp["unknown"]))
                f.write(struct.pack("<H", imp["import_type"]))
                f.write(struct.pack("<H", imp["return_type"]))
            
            # Write code data
            f.write(conversation["code_data"])
        
        # Metadata file with info and decompiled code
        meta_filename = os.path.join(self.output_dir, f"conversation_{slot_idx:04X}.txt")
        with open(meta_filename, "w", encoding="utf-8") as f:
            f.write(f"Conversation Slot: {slot_idx:04X}\n")
            f.write(f"Offset in CNV.ARK: 0x{conversation['offset']:08X}\n")
            if conversation["npc_string_index"] is not None:
                f.write(f"NPC Name String: Block {self.string_block_offset}, Index {conversation['npc_string_index']}\n")
            
            f.write("\nHeader Information:\n")
            for key, value in conversation["header"].items():
                if isinstance(value, int):
                    f.write(f"  {key}: {value} (0x{value:04X})\n")
                else:
                    f.write(f"  {key}: {value}\n")
            
            f.write("\nImported Functions/Variables:\n")
            for i, imp in enumerate(conversation["imports"]):
                f.write(f"  [{i}] {imp['name']} - ")
                if imp["is_function"]:
                    f.write(f"Function, ID: {imp['id_or_addr']}, Returns: {imp['return_type_name']}\n")
                elif imp["is_variable"]:
                    f.write(f"Variable, Addr: 0x{imp['id_or_addr']:04X}\n")
                else:
                    f.write(f"Unknown Type: 0x{imp['import_type']:04X}\n")
            
            f.write(f"\nCode Section: {len(conversation['code_data'])} bytes\n")
            f.write(f"Code Start Offset: 0x{conversation['code_start']:08X}\n")
            
            # Add a hexdump of the code section for debugging
            f.write("\nCode Hexdump:\n")
            for i in range(0, len(conversation["code_data"]), 16):
                line_data = conversation["code_data"][i:i+16]
                hex_values = ' '.join(f'{b:02X}' for b in line_data)
                ascii_repr = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in line_data)
                f.write(f"{i:04X}: {hex_values:<48} |{ascii_repr}|\n")
            
            # Add decompiled assembly code
            f.write("\nDecompiled Assembly Code:\n")
            for i, instr in enumerate(conversation["decompiled_code"]):
                f.write(f"{i*2:04X}: {instr}\n")
        
        # Also write assembly file
        asm_filename = os.path.join(self.output_dir, f"conversation_{slot_idx:04X}.asm")
        with open(asm_filename, "w", encoding="utf-8") as f:
            f.write("; Decompiled conversation script\n")
            f.write(f"; Slot: {slot_idx:04X}\n")
            f.write(f"; String Block: {conversation['header']['string_block']}\n\n")
            
            # Write imports as comments
            f.write("; Imported Functions/Variables:\n")
            for i, imp in enumerate(conversation["imports"]):
                if imp["is_function"]:
                    f.write(f"; Import {i}: Function {imp['name']}, ID: {imp['id_or_addr']}, Returns: {imp['return_type_name']}\n")
                elif imp["is_variable"]:
                    f.write(f"; Import {i}: Variable {imp['name']}, Addr: 0x{imp['id_or_addr']:04X}\n")
            
            f.write("\n")
            
            # Write decompiled code
            for instr in conversation["decompiled_code"]:
                f.write(f"{instr}\n")

def decompile_binary_file(binary_file, output_file=None, verbose=False):
    """Decompile a single binary conversation file."""
    try:
        # If output file not specified, create one based on input name
        if output_file is None:
            output_file = os.path.splitext(binary_file)[0] + ".asm"
        
        # Create a decompiler instance
        decompiler = ConversationDecompiler()
        
        print(f"Reading binary file: {binary_file}")
        with open(binary_file, 'rb') as f:
            # Read header
            header = {}
            header["unknown1"] = struct.unpack("<H", f.read(2))[0]
            header["unknown2"] = struct.unpack("<H", f.read(2))[0]
            header["code_size"] = struct.unpack("<H", f.read(2))[0]
            header["unknown3"] = struct.unpack("<H", f.read(2))[0]
            header["unknown4"] = struct.unpack("<H", f.read(2))[0]
            header["string_block"] = struct.unpack("<H", f.read(2))[0]
            header["memory_slots"] = struct.unpack("<H", f.read(2))[0]
            header["num_imports"] = struct.unpack("<H", f.read(2))[0]
            
            if verbose:
                print(f"Header: {header}")
            
            # Read imports
            imports = []
            for i in range(header["num_imports"]):
                # Read import record
                name_length = struct.unpack("<H", f.read(2))[0]
                name = f.read(name_length).decode('ascii', errors='replace')
                id_or_addr = struct.unpack("<H", f.read(2))[0]
                unknown = struct.unpack("<H", f.read(2))[0]
                import_type = struct.unpack("<H", f.read(2))[0]
                return_type = struct.unpack("<H", f.read(2))[0]
                
                import_record = {
                    "name": name,
                    "id_or_addr": id_or_addr,
                    "import_type": import_type, 
                    "return_type": return_type,
                    "is_variable": import_type == 0x010F,
                    "is_function": import_type == 0x0111
                }
                
                imports.append(import_record)
                
                if verbose:
                    print(f"Import {i}: {name}")
            
            # Read code section
            code_start_pos = f.tell()
            code_data = f.read(header["code_size"] * 2)  # Each instruction is 2 bytes
            
            if verbose:
                print(f"Code section: {len(code_data)} bytes")
            
            # Decompile the code section
            decompiled_code = decompiler.decompile(code_data)
            
            # Write the decompiled assembly
            with open(output_file, 'w', encoding='utf-8') as out_file:
                out_file.write("; Decompiled conversation script\n")
                out_file.write(f"; Binary File: {os.path.basename(binary_file)}\n")
                out_file.write(f"; String Block: {header['string_block']}\n\n")
                
                # Write imports as comments
                out_file.write("; Imported Functions/Variables:\n")
                for i, imp in enumerate(imports):
                    if imp["is_function"]:
                        out_file.write(f"; Import {i}: Function {imp['name']}, ID: {imp['id_or_addr']}\n")
                    elif imp["is_variable"]:
                        out_file.write(f"; Import {i}: Variable {imp['name']}, Addr: 0x{imp['id_or_addr']:04X}\n")
                
                out_file.write("\n")
                
                # Write decompiled code
                for instr in decompiled_code:
                    out_file.write(f"{instr}\n")
            
            print(f"Decompiled code written to {output_file}")
            return True
            
    except Exception as e:
        print(f"Error decompiling binary file: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Extract and decompile conversations from Ultima Underworld CNV.ARK")
    parser.add_argument('input_file', help='Path to CNV.ARK file or binary conversation file')
    parser.add_argument('-o', '--output-dir', default='conversations', 
                        help='Output directory for extracted conversations')
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='Enable verbose output')
    parser.add_argument('--decompile-binary', action='store_true',
                        help='Decompile a single binary conversation file')
    parser.add_argument('--output-file', 
                        help='Output file for decompiled code (only used with --decompile-binary)')
    args = parser.parse_args()
    
    if args.decompile_binary:
        print(f"Decompiling binary file {args.input_file}...")
        if decompile_binary_file(args.input_file, args.output_file, args.verbose):
            print("Decompilation complete.")
        else:
            print("Decompilation failed.")
            return 1
    else:
        print(f"Extracting and decompiling conversations from {args.input_file}...")
        extractor = ConversationExtractor(args.input_file, args.output_dir, args.verbose)
        
        if extractor.extract_all():
            print(f"Extraction complete. Files saved to {args.output_dir}/")
        else:
            print("Extraction failed.")
            return 1
    
    return 0

if __name__ == "__main__":
    main()
