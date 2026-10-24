import struct
import os
import json
import binascii

class UaHuffNode:
    """Node format used in STRINGS.PAK."""
    def __init__(self, symbol, parent, left, right):
        self.symbol = symbol
        self.parent = parent
        self.left = left
        self.right = right
    
    @classmethod
    def from_dict(cls, data):
        """Create a node from dictionary data."""
        return cls(
            data["symbol"],
            data["parent"],
            data["left"],
            data["right"]
        )

class UaBlockInfo:
    """Block info structure used in STRINGS.PAK."""
    def __init__(self, block_id, offset):
        self.block_id = block_id
        self.offset = offset
    
    @classmethod
    def from_dict(cls, data):
        """Create a block info from dictionary data."""
        return cls(
            data["block_id"],
            data["offset"]
        )

class StringsPacker:
    def __init__(self):
        self.blocks = {}  # Dictionary mapping block_id to list of strings
        self.huffman_nodes = []
        self.block_infos = []
        self.huffman_codes = {}  # Character to code mapping
        self.debug = False  # Debug mode
    
    def log(self, message):
        """Print debug information if debug mode is enabled."""
        if self.debug:
            print(f"DEBUG: {message}")
    
    def load_metadata(self, filename):
        """Load Huffman tree and block info from metadata file."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
                # Load Huffman nodes
                self.huffman_nodes = [
                    UaHuffNode.from_dict(node_data) 
                    for node_data in metadata.get("huffman_nodes", [])
                ]
                
                # Load block infos (we use these only for reference)
                self.block_infos = [
                    UaBlockInfo.from_dict(block_data) 
                    for block_data in metadata.get("block_infos", [])
                ]
                
                # Load pre-generated Huffman codes if available
                if "huffman_codes" in metadata:
                    self.huffman_codes = metadata["huffman_codes"]
                else:
                    # Otherwise generate them
                    self._generate_huffman_codes()
                
                return True
        except Exception as e:
            print(f"Error loading metadata from {filename}: {e}")
            return False
    
    def _generate_huffman_codes(self):
        """Generate Huffman codes from the loaded Huffman tree."""
        if not self.huffman_nodes:
            print("No Huffman nodes loaded")
            return
        
        # Find the root node (usually the second-to-last node)
        root_idx = len(self.huffman_nodes) - 1
        
        # Generate codes recursively
        def generate_codes(node_idx, code=""):
            node = self.huffman_nodes[node_idx]
            
            # Leaf node
            if node.left == 255 and node.right == 255:
                char = chr(node.symbol)
                self.huffman_codes[char] = code
                return
            
            # Traverse left (0)
            if node.left != 255:
                generate_codes(node.left, code + "0")
            
            # Traverse right (1)
            if node.right != 255:
                generate_codes(node.right, code + "1")
        
        # Start generating codes from the root
        generate_codes(root_idx)
    
    def parse_text_file(self, filename):
        """Parse the extracted text file into blocks and strings."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                current_block = None
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if this is a block header
                    if line.startswith("block: "):
                        parts = line.split(';')
                        if len(parts) >= 1:
                            block_id_str = parts[0].replace("block: ", "").strip()
                            try:
                                current_block = int(block_id_str, 16)
                                self.blocks[current_block] = []
                            except ValueError:
                                print(f"Invalid block ID: {block_id_str}")
                    
                    # Check if this is a string entry
                    elif current_block is not None and ":" in line:
                        try:
                            index_str, text = line.split(":", 1)
                            index = int(index_str.strip())
                            text = text.strip()
                            # Replace escaped newlines with actual newlines
                            text = text.replace("\\n", "\n")
                            
                            # Ensure block has enough elements
                            while len(self.blocks[current_block]) <= index:
                                self.blocks[current_block].append("")
                            
                            # Set the string at the correct index
                            self.blocks[current_block][index] = text
                        except ValueError:
                            print(f"Invalid string entry: {line}")
            
            # Sort blocks by ID
            self.blocks = dict(sorted(self.blocks.items()))
            return True
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
            return False
    
    def encode_string(self, s):
        """Encode a string using the Huffman codes."""
        if not self.huffman_codes:
            raise ValueError("Huffman codes not generated")
        
        # Add string terminator if not present
        if not s.endswith('|'):
            s += '|'
        
        # Collect all bits
        bit_string = ""
        for char in s:
            if char in self.huffman_codes:
                bit_string += self.huffman_codes[char]
            else:
                print(f"Warning: Character '{char}' (code {ord(char)}) not in Huffman codes")
                # Use a default code for unsupported characters
                # (prefer to use the code for space or other common character)
                if ' ' in self.huffman_codes:
                    bit_string += self.huffman_codes[' ']
        
        # Convert bit string to bytes
        # Important: UW expects the bits to be packed in MSB to LSB order
        bytes_data = bytearray()
        current_byte = 0
        bit_count = 0
        
        for bit in bit_string:
            # Shift left and add new bit
            current_byte = (current_byte << 1) | int(bit)
            bit_count += 1
            
            # When we have 8 bits, add byte to output
            if bit_count == 8:
                bytes_data.append(current_byte)
                current_byte = 0
                bit_count = 0
        
        # If we have remaining bits, pad with 0s and add final byte
        if bit_count > 0:
            current_byte = current_byte << (8 - bit_count)
            bytes_data.append(current_byte)
        
        return bytes_data
    
    def write_pak_file(self, filename):
        """Write the data to STRINGS.PAK format."""
        if not self.blocks or not self.huffman_nodes:
            print("No data to write or Huffman tree not loaded")
            return False
        
        try:
            # Create temporary file to build the PAK
            with open(filename, 'wb') as f:
                # Write number of Huffman nodes
                num_nodes = len(self.huffman_nodes)
                self.log(f"Writing {num_nodes} Huffman nodes")
                f.write(struct.pack("<H", num_nodes))
                
                # Write all Huffman nodes
                for node in self.huffman_nodes:
                    f.write(struct.pack("<BBBB", 
                        node.symbol, node.parent, node.left, node.right))
                
                # Get sorted block IDs
                block_ids = sorted(self.blocks.keys())
                
                # Write number of blocks
                f.write(struct.pack("<H", len(block_ids)))
                
                # Calculate header size
                header_size = 2 + (len(self.huffman_nodes) * 4) + 2 + (len(block_ids) * 6)
                
                # Placeholder for block info (we'll update later)
                block_info_pos = f.tell()
                for block_id in block_ids:
                    f.write(struct.pack("<HI", block_id, 0))  # Placeholder offset
                
                # Keep track of actual block data and offsets for final patching
                block_offsets = {}
                
                # Write each block's data
                current_offset = header_size
                for block_id in block_ids:
                    block_strings = self.blocks[block_id]
                    block_offsets[block_id] = current_offset
                    
                    # Move to the block position
                    f.seek(current_offset)
                    
                    # Write number of strings in this block
                    num_strings = len(block_strings)
                    f.write(struct.pack("<H", num_strings))
                    
                    # Calculate offset table size
                    offset_table_size = 2 + (num_strings * 2)
                    
                    # Placeholder for string offsets
                    string_offset_pos = f.tell()
                    for _ in range(num_strings):
                        f.write(struct.pack("<H", 0))  # Placeholder offset
                    
                    # Encode and write strings, keeping track of offsets
                    string_offsets = []
                    current_string_offset = 0
                    
                    for s in block_strings:
                        # Save offset relative to string data start
                        string_offsets.append(current_string_offset)
                        
                        # Encode and write the string
                        encoded = self.encode_string(s)
                        f.write(encoded)
                        
                        # Update offset for next string
                        current_string_offset += len(encoded)
                    
                    # Go back and fill in string offsets
                    f.seek(string_offset_pos)
                    for offset in string_offsets:
                        f.write(struct.pack("<H", offset))
                    
                    # Update current offset for next block
                    current_offset += offset_table_size + sum(len(self.encode_string(s)) for s in block_strings)
                    
                    # Seek to end for next block
                    f.seek(0, 2)  # Seek to end of file
                
                # Go back and update block offsets in header
                f.seek(block_info_pos)
                for block_id in block_ids:
                    f.write(struct.pack("<HI", block_id, block_offsets[block_id]))
                
                return True
        except Exception as e:
            print(f"Error writing {filename}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def compare_with_original(self, original_pak, our_pak):
        """Compare our packed file with the original."""
        try:
            with open(original_pak, 'rb') as f1, open(our_pak, 'rb') as f2:
                original_data = f1.read()
                our_data = f2.read()
                
                print(f"Original file size: {len(original_data)} bytes")
                print(f"Our file size: {len(our_data)} bytes")
                
                min_len = min(len(original_data), len(our_data))
                
                # Find first difference
                for i in range(min_len):
                    if original_data[i] != our_data[i]:
                        print(f"First difference at byte {i} (0x{i:X}):")
                        # Show a few bytes around the difference
                        context = 16
                        start = max(0, i - context)
                        end = min(min_len, i + context + 1)
                        
                        print("Original:", binascii.hexlify(original_data[start:end]))
                        print("Ours:    ", binascii.hexlify(our_data[start:end]))
                        print(f"At offset {i}:")
                        print(f"Original: 0x{original_data[i]:02X}")
                        print(f"Ours:     0x{our_data[i]:02X}")
                        break
                else:
                    print("Files are identical up to the minimum length")
                    
                    if len(original_data) > len(our_data):
                        print("Original file has extra data")
                    elif len(our_data) > len(original_data):
                        print("Our file has extra data")
                
                return True
        except Exception as e:
            print(f"Error comparing files: {e}")
            return False

def verify_pak_file(filename):
    """Verify if the generated PAK file can be read."""
    try:
        with open(filename, "rb") as f:
            # Read Huffman node count
            node_count_bytes = f.read(2)
            node_count = struct.unpack("<H", node_count_bytes)[0]
            print(f"Huffman nodes: {node_count}")
            
            # Skip all nodes
            f.seek(node_count * 4, 1)
            
            # Read block count
            block_count_bytes = f.read(2)
            block_count = struct.unpack("<H", block_count_bytes)[0]
            print(f"Block count: {block_count}")
            
            # Read first few block infos
            for i in range(min(5, block_count)):
                block_info_bytes = f.read(6)
                block_id, offset = struct.unpack("<HI", block_info_bytes)
                print(f"Block {i}: ID={block_id}, offset=0x{offset:X}")
                
                # Verify offset is within file
                file_size = os.path.getsize(filename)
                if offset >= file_size:
                    print(f"Warning: Block {block_id} offset 0x{offset:X} exceeds file size 0x{file_size:X}")
            
            # Try to read the first block's strings
            if block_count > 0:
                # Go back to read the first block info
                f.seek(2 + (node_count * 4) + 2)
                first_block_bytes = f.read(6)
                first_block_id, first_block_offset = struct.unpack("<HI", first_block_bytes)
                
                # Go to the first block
                f.seek(first_block_offset)
                
                # Read string count
                string_count_bytes = f.read(2)
                string_count = struct.unpack("<H", string_count_bytes)[0]
                print(f"First block (ID={first_block_id}) has {string_count} strings")
                
                # Success
                return True
    except Exception as e:
        print(f"Verification error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    packer = StringsPacker()
    packer.debug = True  # Enable debug output
    
    # Load the Huffman tree from the original file's metadata
    metadata_file = "uw-strings-metadata.json"
    if not os.path.exists(metadata_file):
        print(f"Metadata file {metadata_file} not found")
        print("Run the enhanced extractor first to generate the metadata file")
        return
    
    print(f"Loading metadata from {metadata_file}...")
    if not packer.load_metadata(metadata_file):
        print("Failed to load metadata")
        return
    
    # Parse the text file with extracted strings
    input_file = "uw-strings.txt"
    if not os.path.exists(input_file):
        print(f"Input file {input_file} not found")
        return
    
    print(f"Parsing {input_file}...")
    if not packer.parse_text_file(input_file):
        print("Failed to parse input file")
        return
    
    # Write the packed data
    output_file = "strings.pak"
    print(f"Writing {output_file}...")
    if packer.write_pak_file(output_file):
        print(f"Successfully created {output_file}")
        
        # Verify the file is readable
        print(f"Verifying {output_file}...")
        if verify_pak_file(output_file):
            print("Verification successful!")
        else:
            print("Verification failed!")
        
        # If original file exists, compare them
        original_file = "original_strings.pak"
        if os.path.exists(original_file):
            print(f"Comparing with original {original_file}...")
            packer.compare_with_original(original_file, output_file)
    else:
        print(f"Failed to create {output_file}")

if __name__ == "__main__":
    main()
