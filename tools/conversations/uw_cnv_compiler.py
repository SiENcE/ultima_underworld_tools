#!/usr/bin/env python3
"""
Ultima Underworld Conversation Compiler

This tool compiles conversation assembly files back to binary format
and can optionally update a slot in the CNV.ARK file.
"""

import os
import struct
import argparse
import re
from pathlib import Path
import io

class ArkCompressor:
    """Compressor for Ultima Underworld 1/2 .ark files."""
    
    @staticmethod
    def compress(input_data):
        """Compress data using UW2 ARK compression algorithm."""
        output = bytearray()
        i = 0
        
        while i < len(input_data):
            # Look for runs of 3 or more identical bytes
            run_length = 1
            if i + 2 < len(input_data) and input_data[i] == input_data[i+1]:
                run_value = input_data[i]
                j = i
                while j + 1 < len(input_data) and input_data[j+1] == run_value and run_length < 130:
                    run_length += 1
                    j += 1
                
                # Encode the run if at least 3 bytes long
                if run_length >= 3:
                    output.append(0x80 | (run_length - 3))  # High bit set, length - 3
                    output.append(run_value)
                    i += run_length
                    continue
            
            # If no run found, encode literal bytes
            literal_start = i
            while i < len(input_data):
                # Check if we can start a run
                if i + 2 < len(input_data) and input_data[i] == input_data[i+1] == input_data[i+2]:
                    break
                
                i += 1
                # Maximum literal length is 128 bytes
                if i - literal_start >= 128:
                    break
            
            literal_length = i - literal_start
            if literal_length > 0:
                output.append(literal_length - 1)  # High bit clear, length - 1
                output.extend(input_data[literal_start:i])
        
        return bytes(output)
    
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
                    break  # Not enough data
        
        return bytes(output)
    
    @staticmethod
    def is_compressed(data):
        """Try to detect if data is compressed."""
        # Check first 256 bytes for compression indicators
        sample = data[:256]
        high_bit_count = sum(1 for b in sample if b & 0x80)
        return high_bit_count > 64  # Threshold for compression detection


class ConversationCompiler:
    """Compiles decompiled conversation files back to binary format."""
    
    def __init__(self, asm_file, output_file=None, verbose=False):
        self.asm_file = asm_file
        self.output_file = output_file or asm_file.replace(".asm", ".bin")
        self.verbose = verbose
        
        # Conversation metadata
        self.slot_idx = None
        self.string_block = None
        self.memory_slots = 0
        self.unknown1 = 0x0828  # Default value from spec
        self.unknown2 = 0x0000
        self.unknown3 = 0x0000
        self.unknown4 = 0x0000
        
        # Code and imports
        self.labels = {}  # Maps label names to positions
        self.imports = []
        self.code = []
        
        # Parsing state
        self.current_pos = 0
        
    def log(self, message):
        """Print debugging information if verbose mode is enabled."""
        if self.verbose:
            print(f"DEBUG: {message}")
            
    def parse_asm(self):
        """Parse the decompiled assembly file."""
        try:
            with open(self.asm_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Extract metadata from comments
            for line in lines[:20]:
                line = line.strip()
                if '; Slot:' in line:
                    slot_str = line.split('Slot:')[1].strip()
                    self.slot_idx = int(slot_str, 16) if slot_str.startswith('0x') else int(slot_str, 16)
                    self.log(f"Found slot ID: 0x{self.slot_idx:04X}")
                
                elif '; String Block:' in line:
                    block_str = line.split('String Block:')[1].strip()
                    self.string_block = int(block_str)
                    self.log(f"Found string block: {self.string_block}")

                elif '; Memory Slots:' in line:
                    slots_str = line.split('Memory Slots:')[1].strip()
                    self.memory_slots = int(slots_str)
                    self.log(f"Found memory slots: {self.memory_slots}")

            # Parse import section
            import_section = False
            for line in lines:
                line = line.strip()
                if not line or not line.startswith(';'):
                    continue
                
                if '; Imported Functions/Variables:' in line:
                    import_section = True
                    continue
                
                if import_section and line.startswith('; Import '):
                    # Parse import info
                    try:
                        import_info = self._parse_import_line(line)
                        if import_info:
                            self.imports.append(import_info)
                    except Exception as e:
                        print(f"Warning: Failed to parse import line: {line}")
                        print(f"  Error: {e}")
            
            # First pass - find all labels
            self.current_pos = 0
            for line in lines:
                line = self._clean_line(line)
                if not line:
                    continue
                
                # Look for label definitions
                if ':' in line and not line.startswith(';'):
                    label = line.split(':')[0].strip()
                    self.labels[label] = self.current_pos
                    self.log(f"Found label '{label}' at position {self.current_pos}")
                    continue
                
                # Skip comments
                if line.startswith(';'):
                    continue
                
                # Update position based on instruction size
                if ' ' in line:
                    # Opcode with argument (2 words)
                    self.current_pos += 2
                else:
                    # Single opcode (1 word)
                    self.current_pos += 1
            
            # Second pass - compile instructions
            self.code = []
            self.current_pos = 0
            
            for line in lines:
                line = self._clean_line(line)
                if not line or line.startswith(';') or ':' in line:
                    continue
                
                # Compile instruction
                self._compile_instruction(line)
            
            # Log summary
            self.log(f"Compiled {len(self.code)} code words")
            self.log(f"Found {len(self.labels)} labels")
            self.log(f"Processed {len(self.imports)} imports")
            
            # Calculate memory slots if not set
            if self.memory_slots == 0:
                # Default memory slots based on import count
                self.memory_slots = 32 + len(self.imports)
            
            return True
            
        except Exception as e:
            print(f"Error parsing ASM file: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _clean_line(self, line):
        """Clean a line by removing comments and whitespace."""
        # Remove inline comments
        if ';' in line and not line.startswith(';'):
            line = line.split(';')[0]
        return line.strip()
    
    def _parse_import_line(self, line):
        """Parse an import comment line."""
        # Example: "; Import 0: Function babl_menu, ID: 0, Returns: int"
        
        # Extract import type and name
        function_match = re.search(r'; Import (\d+): Function ([^,]+), ID: ([^,]+), Returns: ([^,\n]+)', line)
        variable_match = re.search(r'; Import (\d+): Variable ([^,]+), Addr: ([^,]+)', line)
        
        if function_match:
            idx, name, id_str, ret_type = function_match.groups()
            return {
                'index': int(idx),
                'name': name.strip(),
                'is_function': True,
                'id_or_addr': int(id_str),
                'return_type': ret_type.strip()
            }
        elif variable_match:
            idx, name, addr_str = variable_match.groups()
            addr = int(addr_str, 16) if addr_str.startswith('0x') else int(addr_str)
            return {
                'index': int(idx),
                'name': name.strip(),
                'is_function': False,
                'id_or_addr': addr,
                'return_type': 'int'  # Default for variables
            }
        
        return None
    
    def _compile_instruction(self, line):
        """Compile a single instruction into bytecode."""
        if ' ' in line:
            # Opcode with argument
            parts = line.split(' ', 1)
            opcode_name = parts[0].strip().upper()
            arg_str = parts[1].strip()
            
            # Get opcode value
            opcode_val = self._get_opcode_value(opcode_name)
            
            # Parse argument value - handle labels and numeric values
            arg_val = self._parse_argument(arg_str, opcode_name)
            
            # Add to code
            self.code.append(opcode_val)
            self.code.append(arg_val)
            
            self.log(f"Compiled: {opcode_name} {arg_val} -> [{opcode_val:02X}, {arg_val:04X}]")
            self.current_pos += 2
            
        else:
            # Single opcode without argument
            opcode_name = line.upper()
            opcode_val = self._get_opcode_value(opcode_name)
            
            self.code.append(opcode_val)
            self.log(f"Compiled: {opcode_name} -> [{opcode_val:02X}]")
            self.current_pos += 1
    
    def _parse_argument(self, arg_str, opcode_name):
        """Parse instruction argument, resolving labels if needed."""
        # Check if argument is a label
        if arg_str in self.labels:
            target_pos = self.labels[arg_str]
            
            # Handle branch instructions (relative offsets)
            if opcode_name in ['BEQ', 'BNE', 'BRA']:
                # Calculate relative offset (target - current - 2)
                offset = target_pos - (self.current_pos + 2)
                self.log(f"Branch from {self.current_pos} to {target_pos}, offset={offset}")
                return offset
            elif opcode_name in ['JMP', 'CALL']:
                # For JMP and CALL, use absolute position
                self.log(f"{opcode_name} to label '{arg_str}' at position {target_pos}")
                return target_pos
        
        # Handle hex values
        if arg_str.startswith('0x'):
            try:
                return int(arg_str, 16)
            except ValueError:
                print(f"Error: Invalid hex value: {arg_str}")
                return 0
        
        # Handle decimal values
        try:
            return int(arg_str)
        except ValueError:
            print(f"Error: Cannot resolve argument '{arg_str}' - not a valid number or label")
            # Return 0 as fallback to avoid crashing
            return 0
    
    def _get_opcode_value(self, opcode_name):
        """Convert opcode name to its numeric value."""
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
            raise ValueError(f"Unknown opcode: {opcode_name}")
        
        return opcode_map[opcode_name]
    
    def build_binary(self):
        """Build the binary conversation data."""
        # Create header
        header = bytearray()
        
        # Header fields from spec
        header += struct.pack("<H", self.unknown1)          # Unknown1 (0x0828)
        header += struct.pack("<H", self.unknown2)          # Unknown2 (0x0000)
        header += struct.pack("<H", len(self.code))         # Code size in words
        header += struct.pack("<H", self.unknown3)          # Unknown3 (0x0000)
        header += struct.pack("<H", self.unknown4)          # Unknown4 (0x0000)
        header += struct.pack("<H", self.string_block)      # String block ID
        header += struct.pack("<H", self.memory_slots)      # Memory slots
        header += struct.pack("<H", len(self.imports))      # Import count
        
        # Add import records
        import_data = bytearray()
        for imp in self.imports:
            name = imp['name']
            name_bytes = name.encode('ascii')
            
            import_data += struct.pack("<H", len(name_bytes))  # Name length
            import_data += name_bytes                          # Name string
            import_data += struct.pack("<H", imp['id_or_addr'])# ID or address
            import_data += struct.pack("<H", 1)                # Unknown, always 1
            
            # Import type
            if imp['is_function']:
                import_data += struct.pack("<H", 0x0111)       # Function type
            else:
                import_data += struct.pack("<H", 0x010F)       # Variable type
            
            # Return type
            if imp['return_type'] == 'void':
                import_data += struct.pack("<H", 0x0000)
            elif imp['return_type'] == 'string':
                import_data += struct.pack("<H", 0x012B)
            else:  # Default to int
                import_data += struct.pack("<H", 0x0129)
        
        # Add code section
        code_data = bytearray()
        for word in self.code:
            code_data += struct.pack("<H", word)
        
        # Combine all sections
        binary_data = header + import_data + code_data
        
        return binary_data
    
    def write_binary(self):
        """Write compiled binary to output file."""
        try:
            binary_data = self.build_binary()
            
            with open(self.output_file, 'wb') as f:
                f.write(binary_data)
            
            print(f"Successfully wrote {len(binary_data)} bytes to {self.output_file}")
            return True
        except Exception as e:
            print(f"Error writing binary file: {e}")
            return False
    
    def update_cnv_ark(self, cnv_ark_file):
        """Update a slot in the CNV.ARK file with the compiled conversation."""
        if self.slot_idx is None:
            print("Error: No slot index specified in the ASM file")
            return False
        
        try:
            # Check if file exists
            if not os.path.exists(cnv_ark_file):
                print(f"Error: CNV.ARK file {cnv_ark_file} not found")
                return False
            
            # Read the CNV.ARK file
            with open(cnv_ark_file, 'rb') as f:
                ark_data = f.read()
            
            # Check if the file is compressed (UW2)
            is_compressed = ArkCompressor.is_compressed(ark_data)
            
            if is_compressed:
                print("CNV.ARK appears to be compressed (UW2 format)")
                # Decompress the file
                ark_data = ArkCompressor.decompress(ark_data)
            
            # Create a modifiable copy
            ark_bytes = bytearray(ark_data)
            
            # Get number of slots
            num_slots = struct.unpack("<H", ark_bytes[0:2])[0]
            
            if self.slot_idx >= num_slots:
                print(f"Error: Slot index {self.slot_idx} exceeds number of slots ({num_slots})")
                return False
            
            # Get the offset position in the header
            offset_pos = 2 + (self.slot_idx * 4)
            
            # Get our binary data
            binary_data = self.build_binary()
            
            # Determine where to put the new conversation
            # For simplicity, we'll append it to the end of the file
            new_offset = len(ark_bytes)
            
            # Update the offset in the header
            struct.pack_into("<I", ark_bytes, offset_pos, new_offset)
            
            # Append the conversation data
            ark_bytes.extend(binary_data)
            
            # Create backup of original file
            backup_file = cnv_ark_file + ".bak"
            if os.path.exists(backup_file):
                os.unlink(backup_file)
            os.rename(cnv_ark_file, backup_file)
            
            # Write the modified data
            if is_compressed:
                # Compress data for UW2
                compressed_data = ArkCompressor.compress(ark_bytes)
                with open(cnv_ark_file, 'wb') as f:
                    f.write(compressed_data)
                print(f"Wrote compressed file ({len(compressed_data)} bytes)")
            else:
                # Write uncompressed data for UW1
                with open(cnv_ark_file, 'wb') as f:
                    f.write(ark_bytes)
                print(f"Wrote uncompressed file ({len(ark_bytes)} bytes)")
            
            print(f"Successfully updated slot {self.slot_idx:04X} in {cnv_ark_file}")
            print(f"Original file backed up to {backup_file}")
            
            return True
            
        except Exception as e:
            print(f"Error updating CNV.ARK file: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(description="Compile UW conversation script to binary")
    parser.add_argument("asm_file", help="Input ASM file to compile")
    parser.add_argument("-o", "--output", help="Output binary file (default: input with .bin extension)")
    parser.add_argument("-u", "--update-cnv", help="Update a slot in the specified CNV.ARK file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    compiler = ConversationCompiler(args.asm_file, args.output, args.verbose)
    
    print(f"Compiling {args.asm_file}...")
    
    if not compiler.parse_asm():
        print("Failed to parse ASM file")
        return 1
    
    if args.update_cnv:
        # Update the CNV.ARK file
        if compiler.update_cnv_ark(args.update_cnv):
            print("CNV.ARK update successful")
        else:
            print("Failed to update CNV.ARK file")
            return 1
    else:
        # Write standalone binary file
        if compiler.write_binary():
            print("Compilation successful")
        else:
            print("Failed to write binary file")
            return 1
    
    return 0

if __name__ == "__main__":
    main()
