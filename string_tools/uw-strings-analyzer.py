#!/usr/bin/env python3
"""
STRINGS.PAK Analyzer Tool

This tool provides detailed analysis of Ultima Underworld STRINGS.PAK files,
showing their internal structure, Huffman tree, and string encoding.
"""

import struct
import os
import sys
import json
import binascii
import math
from collections import defaultdict

class StringsPakAnalyzer:
    def __init__(self, filename):
        self.filename = filename
        self.filesize = 0
        self.huffman_nodes = []
        self.block_infos = []
        self.string_counts = {}
        self.string_samples = {}
        self.huffman_code_map = {}
        
    def analyze(self):
        """Perform full analysis of the file."""
        try:
            # Get file size
            self.filesize = os.path.getsize(self.filename)
            print(f"=== STRINGS.PAK Analysis: {self.filename} ===")
            print(f"File size: {self.filesize} bytes")
            
            with open(self.filename, "rb") as f:
                # Read and analyze file header
                self._analyze_header(f)
                
                # Analyze Huffman tree
                self._analyze_huffman_tree()
                
                # Analyze blocks
                self._analyze_blocks(f)
                
                # Analyze string encodings (sample from each block)
                self._analyze_string_encodings(f)
                
                # Verify file integrity
                self._verify_file_integrity(f)
                
            return True
        except Exception as e:
            print(f"Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _analyze_header(self, f):
        """Analyze the file header including Huffman nodes and block info."""
        f.seek(0)
        
        # Read and display file header
        print("\n=== File Header ===")
        
        # Number of Huffman nodes
        node_count_bytes = f.read(2)
        node_count = struct.unpack("<H", node_count_bytes)[0]
        print(f"Number of Huffman nodes: {node_count}")
        print(f"Header bytes: {binascii.hexlify(node_count_bytes).decode()}")
        
        # Read all Huffman nodes
        for i in range(node_count):
            node_bytes = f.read(4)
            symbol, parent, left, right = struct.unpack("<BBBB", node_bytes)
            self.huffman_nodes.append({
                "index": i,
                "symbol": symbol,
                "symbol_char": chr(symbol) if 32 <= symbol <= 126 else f"<{symbol}>",
                "parent": parent,
                "left": left,
                "right": right,
                "bytes": binascii.hexlify(node_bytes).decode()
            })
        
        # Number of blocks
        block_count_bytes = f.read(2)
        block_count = struct.unpack("<H", block_count_bytes)[0]
        print(f"Number of string blocks: {block_count}")
        print(f"Block count bytes: {binascii.hexlify(block_count_bytes).decode()}")
        
        # Read all block info
        for i in range(block_count):
            block_info_bytes = f.read(6)
            block_id, offset = struct.unpack("<HI", block_info_bytes)
            self.block_infos.append({
                "index": i,
                "block_id": block_id,
                "offset": offset,
                "bytes": binascii.hexlify(block_info_bytes).decode()
            })
    
    def _analyze_huffman_tree(self):
        """Analyze the Huffman tree structure."""
        print("\n=== Huffman Tree Analysis ===")
        
        # Display all nodes
        print("Node structure:")
        print(f"{'Index':<6} {'Symbol':<8} {'Parent':<8} {'Left':<8} {'Right':<8} {'Bytes':<10}")
        print("=" * 60)
        
        leaf_nodes = 0
        internal_nodes = 0
        
        for node in self.huffman_nodes:
            print(f"{node['index']:<6} {node['symbol_char']:<8} {node['parent']:<8} {node['left']:<8} {node['right']:<8} {node['bytes']}")
            
            if node['left'] == 255 and node['right'] == 255:
                leaf_nodes += 1
            else:
                internal_nodes += 1
        
        print(f"\nTotal nodes: {len(self.huffman_nodes)}")
        print(f"Leaf nodes: {leaf_nodes}")
        print(f"Internal nodes: {internal_nodes}")
        
        # Find the root node (usually the last one)
        root_idx = len(self.huffman_nodes) - 1
        print(f"Root node index: {root_idx}")
        
        # Generate Huffman codes
        self._generate_huffman_codes(root_idx)
        
        # Display some Huffman codes
        print("\nSample Huffman codes:")
        print(f"{'Character':<10} {'Code':<20} {'Bits':<6}")
        print("=" * 40)
        
        # Sort by code length for better readability
        sorted_codes = sorted(
            [(char, code, len(code)) for char, code in self.huffman_code_map.items()],
            key=lambda x: (x[2], x[0])
        )
        
        for char, code, bits in sorted_codes[:20]:  # Show first 20 codes
            display_char = char if 32 <= ord(char) <= 126 else f"<{ord(char)}>"
            print(f"{display_char:<10} {code:<20} {bits:<6}")
        
        if len(sorted_codes) > 20:
            print(f"... and {len(sorted_codes) - 20} more codes")
    
    def _generate_huffman_codes(self, root_idx):
        """Generate Huffman codes from the tree."""
        def generate_codes(node_idx, code=""):
            if node_idx >= len(self.huffman_nodes):
                return
            
            node = self.huffman_nodes[node_idx]
            
            # Leaf node
            if node['left'] == 255 and node['right'] == 255:
                char = chr(node['symbol'])
                self.huffman_code_map[char] = code
                return
            
            # Traverse left (0)
            if node['left'] != 255:
                generate_codes(node['left'], code + "0")
            
            # Traverse right (1)
            if node['right'] != 255:
                generate_codes(node['right'], code + "1")
        
        # Start generating codes from the root
        generate_codes(root_idx)
    
    def _analyze_blocks(self, f):
        """Analyze block structures and string offsets."""
        print("\n=== Block Information ===")
        print(f"{'Index':<6} {'ID':<6} {'Offset':<10} {'Strings':<8} {'Data Size':<10} {'Bytes'}")
        print("=" * 70)
        
        # The size of the header is 2 bytes (node count) + nodes + 2 bytes (block count) + block infos
        header_size = 2 + (len(self.huffman_nodes) * 4) + 2 + (len(self.block_infos) * 6)
        
        # Analyze each block
        for i, block in enumerate(self.block_infos):
            block_id = block['block_id']
            offset = block['offset']
            
            # Seek to block position
            f.seek(offset)
            
            # Read string count
            string_count_bytes = f.read(2)
            string_count = struct.unpack("<H", string_count_bytes)[0]
            
            # Read string offsets
            string_offsets = []
            for _ in range(string_count):
                offset_bytes = f.read(2)
                string_offset = struct.unpack("<H", offset_bytes)[0]
                string_offsets.append(string_offset)
            
            # Calculate block data size
            next_block_offset = self.filesize
            if i < len(self.block_infos) - 1:
                next_block_offset = self.block_infos[i + 1]['offset']
            block_size = next_block_offset - offset
            
            # Store information for later use
            self.string_counts[block_id] = string_count
            
            # Display block info
            block_hex = block['bytes']
            print(f"{i:<6} {block_id:<6} {offset:<10} {string_count:<8} {block_size:<10} {block_hex}")
            
            # Sample some string offsets (first 3)
            if string_offsets:
                print(f"  String offsets (first {min(3, len(string_offsets))}): {string_offsets[:3]}")
                
                # Check if string offsets are sequential
                is_sequential = all(string_offsets[i] < string_offsets[i+1] for i in range(len(string_offsets)-1))
                print(f"  Sequential offsets: {is_sequential}")
        
        print(f"\nTotal blocks: {len(self.block_infos)}")
        print(f"Total strings: {sum(self.string_counts.values())}")
        
        # Analyze block distribution
        block_sizes = []
        for i, block in enumerate(self.block_infos):
            next_offset = self.filesize
            if i < len(self.block_infos) - 1:
                next_offset = self.block_infos[i + 1]['offset']
            size = next_offset - block['offset']
            block_sizes.append(size)
        
        if block_sizes:
            avg_size = sum(block_sizes) / len(block_sizes)
            min_size = min(block_sizes)
            max_size = max(block_sizes)
            print(f"Average block size: {avg_size:.2f} bytes")
            print(f"Min block size: {min_size} bytes")
            print(f"Max block size: {max_size} bytes")
    
    def _analyze_string_encodings(self, f):
        """Analyze string encoding samples from each block."""
        print("\n=== String Encoding Analysis ===")
        
        # Sample strings from a few blocks
        sample_blocks = min(5, len(self.block_infos))
        print(f"Sampling strings from {sample_blocks} blocks...")
        
        for i in range(sample_blocks):
            block = self.block_infos[i]
            block_id = block['block_id']
            offset = block['offset']
            
            f.seek(offset)
            
            # Read string count
            string_count = struct.unpack("<H", f.read(2))[0]
            
            # Read string offsets
            string_offsets = []
            for _ in range(string_count):
                string_offset = struct.unpack("<H", f.read(2))[0]
                string_offsets.append(string_offset)
            
            # Sample the first string if available
            if string_offsets:
                base_offset = offset + 2 + (string_count * 2)
                string_pos = base_offset + string_offsets[0]
                
                f.seek(string_pos)
                
                # Read a sample of the encoded string (up to 16 bytes)
                sample_bytes = f.read(16)
                hex_bytes = binascii.hexlify(sample_bytes).decode()
                
                # Try to decode the string
                decoded_string = self._decode_string_sample(f, block_id, 0)
                
                print(f"\nBlock {block_id}, String 0:")
                print(f"  Offset: {string_pos} (0x{string_pos:X})")
                print(f"  Encoded bytes: {hex_bytes}")
                print(f"  Decoded: \"{decoded_string}\"")
                
                # Save for later comparison
                if block_id not in self.string_samples:
                    self.string_samples[block_id] = []
                self.string_samples[block_id].append(decoded_string)
    
    def _decode_string_sample(self, f, block_id, string_idx):
        """Attempt to decode a string from the file."""
        # Position at the block
        block_info = next((b for b in self.block_infos if b['block_id'] == block_id), None)
        if not block_info:
            return "<block not found>"
        
        offset = block_info['offset']
        f.seek(offset)
        
        # Read string count
        string_count = struct.unpack("<H", f.read(2))[0]
        
        if string_idx >= string_count:
            return "<string index out of range>"
        
        # Read all string offsets
        string_offsets = []
        for _ in range(string_count):
            string_offset = struct.unpack("<H", f.read(2))[0]
            string_offsets.append(string_offset)
        
        # Position at the string
        base_offset = offset + 2 + (string_count * 2)
        string_pos = base_offset + string_offsets[string_idx]
        f.seek(string_pos)
        
        # Decode using Huffman tree
        decoded = ""
        bit = 0
        raw = 0
        root_idx = len(self.huffman_nodes) - 1
        
        try:
            while True:
                node_idx = root_idx
                
                while self.huffman_nodes[node_idx]['left'] != 255 and self.huffman_nodes[node_idx]['right'] != 255:
                    if bit == 0:
                        bit = 8
                        raw_data = f.read(1)
                        if not raw_data:
                            break
                        raw = raw_data[0]
                    
                    if (raw & 0x80) != 0:  # Check highest bit
                        node_idx = self.huffman_nodes[node_idx]['right']
                    else:
                        node_idx = self.huffman_nodes[node_idx]['left']
                    
                    raw = (raw << 1) & 0xFF  # Shift left by 1 bit
                    bit = bit - 1
                
                if 'raw_data' not in locals() or not raw_data:
                    break
                
                c = chr(self.huffman_nodes[node_idx]['symbol'])
                if c != '|':
                    decoded += c
                else:
                    break  # End of string marker
        except Exception as e:
            return f"<decode error: {e}>"
        
        return decoded
    
    def _verify_file_integrity(self, f):
        """Verify file integrity and structure consistency."""
        print("\n=== File Integrity Check ===")
        
        # Check if all referenced offsets are within file bounds
        valid_offsets = True
        for block in self.block_infos:
            if block['offset'] >= self.filesize:
                print(f"Error: Block {block['block_id']} offset {block['offset']} is outside file bounds")
                valid_offsets = False
        
        # Check if blocks are in ascending offset order
        ascending_order = True
        for i in range(len(self.block_infos) - 1):
            if self.block_infos[i]['offset'] >= self.block_infos[i + 1]['offset']:
                print(f"Warning: Blocks not in ascending offset order: {self.block_infos[i]['block_id']} ({self.block_infos[i]['offset']}) >= {self.block_infos[i + 1]['block_id']} ({self.block_infos[i + 1]['offset']})")
                ascending_order = False
        
        # Check Huffman tree references
        valid_tree = True
        for node in self.huffman_nodes:
            # Check parent references
            if node['parent'] != 0 and node['parent'] >= len(self.huffman_nodes):
                print(f"Error: Node {node['index']} has invalid parent reference: {node['parent']}")
                valid_tree = False
            
            # Check child references
            if node['left'] != 255 and node['left'] >= len(self.huffman_nodes):
                print(f"Error: Node {node['index']} has invalid left child reference: {node['left']}")
                valid_tree = False
            
            if node['right'] != 255 and node['right'] >= len(self.huffman_nodes):
                print(f"Error: Node {node['index']} has invalid right child reference: {node['right']}")
                valid_tree = False
        
        # Check Huffman code generation
        if not self.huffman_code_map:
            print("Warning: No Huffman codes were generated")
            valid_codes = False
        else:
            valid_codes = True
            print(f"Huffman codes were generated for {len(self.huffman_code_map)} characters")
        
        # Overall integrity
        if valid_offsets and ascending_order and valid_tree and valid_codes:
            print("File structure appears valid and consistent")
        else:
            print("File structure has issues (see warnings/errors above)")
    
    def export_metadata(self, filename="strings-analysis.json"):
        """Export analysis data to a JSON file."""
        try:
            data = {
                "file_info": {
                    "filename": self.filename,
                    "filesize": self.filesize
                },
                "huffman_nodes": self.huffman_nodes,
                "huffman_codes": self.huffman_code_map,
                "block_infos": self.block_infos,
                "string_counts": self.string_counts,
                "string_samples": self.string_samples
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"\nAnalysis data exported to {filename}")
            return True
        except Exception as e:
            print(f"Error exporting metadata: {e}")
            return False
    
    def hexdump(self, start=0, length=128):
        """Show a hexdump of part of the file."""
        print(f"\n=== Hexdump: Offset {start} to {start+length-1} ===")
        
        try:
            with open(self.filename, 'rb') as f:
                f.seek(start)
                data = f.read(length)
                
                # Format as hexdump with 16 bytes per line
                for i in range(0, len(data), 16):
                    line_data = data[i:i+16]
                    hex_values = ' '.join(f'{b:02x}' for b in line_data)
                    
                    # Pad hex values to align ASCII representation
                    hex_padding = ' ' * (3 * (16 - len(line_data)))
                    
                    # ASCII representation
                    ascii_repr = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in line_data)
                    
                    print(f"{start+i:08x}:  {hex_values}{hex_padding}  |{ascii_repr}|")
        except Exception as e:
            print(f"Error generating hexdump: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python strings_analyzer.py <strings.pak> [--hexdump <offset> <length>]")
        return
    
    filename = sys.argv[1]
    
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found")
        return
    
    analyzer = StringsPakAnalyzer(filename)
    if not analyzer.analyze():
        print("Analysis failed")
        return
    
    # Export analysis data
    analyzer.export_metadata()
    
    # Check for hexdump request
    if "--hexdump" in sys.argv:
        try:
            idx = sys.argv.index("--hexdump")
            offset = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 0
            length = int(sys.argv[idx + 2]) if len(sys.argv) > idx + 2 else 128
            analyzer.hexdump(offset, length)
        except (IndexError, ValueError):
            print("Invalid hexdump parameters. Using defaults.")
            analyzer.hexdump()

if __name__ == "__main__":
    main()
