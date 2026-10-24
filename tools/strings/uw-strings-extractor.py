import struct
import os
import json

class UaHuffNode:
    """Equivalent to ua_huff_node in Lua."""
    def __init__(self, symbol, parent, left, right):
        self.symbol = symbol
        self.parent = parent
        self.left = left
        self.right = right
    
    def to_dict(self):
        """Convert node to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "parent": self.parent,
            "left": self.left,
            "right": self.right
        }

class UaBlockInfo:
    """Equivalent to ua_block_info in Lua."""
    def __init__(self, block_id, offset):
        self.block_id = block_id
        self.offset = offset
    
    def to_dict(self):
        """Convert block info to dictionary for JSON serialization."""
        return {
            "block_id": self.block_id,
            "offset": self.offset
        }

class UaGameStrings:
    """Equivalent to ua_gamestrings in Lua."""
    def __init__(self):
        self.allstrings = {}
        self.huffman_nodes = []
        self.block_infos = []
    
    def load(self, filename):
        """Load and decode strings from the STRINGS.PAK file."""
        if not os.path.exists(filename):
            print(f"Could not open file {filename}")
            return None
        
        try:
            with open(filename, "rb") as fd:
                # Read number of nodes
                nodenum = struct.unpack("<H", fd.read(2))[0]
                
                # Read in node list
                self.huffman_nodes = []
                for _ in range(nodenum):
                    symbol = fd.read(1)[0]
                    parent = fd.read(1)[0]
                    left = fd.read(1)[0]
                    right = fd.read(1)[0]
                    self.huffman_nodes.append(UaHuffNode(symbol, parent, left, right))
                
                # Number of string blocks
                sblocks = struct.unpack("<H", fd.read(2))[0]
                
                # Read in all block infos
                self.block_infos = []
                for _ in range(sblocks):
                    block_id = struct.unpack("<H", fd.read(2))[0]
                    offset = struct.unpack("<I", fd.read(4))[0]  # 4-byte unsigned int
                    self.block_infos.append(UaBlockInfo(block_id, offset))
                
                # Process each block
                for i in range(sblocks):
                    allblockstrings = []
                    
                    fd.seek(self.block_infos[i].offset)
                    
                    # Number of strings
                    numstrings = struct.unpack("<H", fd.read(2))[0]
                    
                    # All string offsets
                    stroffsets = []
                    for _ in range(numstrings):
                        stroffsets.append(struct.unpack("<H", fd.read(2))[0])
                    
                    curoffset = self.block_infos[i].offset + (numstrings + 1) * 2
                    
                    for n in range(numstrings):
                        fd.seek(curoffset + stroffsets[n])
                        
                        string = ""
                        bit = 0
                        raw = 0
                        
                        while True:
                            node = nodenum - 1
                            
                            while self.huffman_nodes[node].left != 255 and self.huffman_nodes[node].right != 255:
                                if bit == 0:
                                    bit = 8
                                    raw_data = fd.read(1)
                                    if not raw_data:
                                        # Premature end of file
                                        n = numstrings
                                        i = sblocks
                                        break
                                    raw = raw_data[0]
                                
                                if (raw & 0x80) != 0:  # Check highest bit
                                    node = self.huffman_nodes[node].right
                                else:
                                    node = self.huffman_nodes[node].left
                                
                                raw = (raw << 1) & 0xFF  # Shift left by 1 bit
                                bit -= 1
                            
                            if 'raw_data' not in locals() or not raw_data:
                                break
                            
                            c = chr(self.huffman_nodes[node].symbol)
                            if c != '|':
                                string += c
                            else:
                                break  # End of string marker
                        
                        allblockstrings.append(string)
                    
                    self.allstrings[self.block_infos[i].block_id] = allblockstrings
                
                return self
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return None
    
    def get_string(self, block, string_nr):
        """Get a specific string from the loaded data."""
        res = ""
        
        # Try to find string block
        stringlist = self.allstrings.get(block)
        
        if stringlist:
            # Try to find string in list
            if string_nr < len(stringlist):
                res = stringlist[string_nr]
        
        return res
    
    def save_metadata(self, filename):
        """Save Huffman tree and block information to a JSON file."""
        try:
            metadata = {
                "huffman_nodes": [node.to_dict() for node in self.huffman_nodes],
                "block_infos": [block.to_dict() for block in self.block_infos]
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"Saved metadata to {filename}")
            return True
        except Exception as e:
            print(f"Error saving metadata: {e}")
            return False

def main():
    """Extract and save strings and Huffman tree from STRINGS.PAK."""
    print("Loading STRINGS.PAK...")
    uo_strings = UaGameStrings()
    if uo_strings.load('strings.pak') is None:
        print("Failed to load STRINGS.PAK. Exiting.")
        return
    
    # Save the Huffman tree and block info
    uo_strings.save_metadata("uw-strings-metadata.json")
    
    print("Writing strings to uw-strings.txt...")
    try:
        with open("uw-strings.txt", "w", encoding="utf-8") as file:
            # Count total blocks with strings
            total_blocks = sum(1 for _ in filter(None, uo_strings.allstrings.values()))
            file.write(f"STRINGS.PAK: {total_blocks} string blocks.\n\n")
            
            for i in range(1, 3899):
                stringlist = uo_strings.allstrings.get(i)
                if stringlist:
                    file.write(f"block: {i:04x}; {len(stringlist)} strings.\n")
                    for k in range(len(stringlist)):
                        text = uo_strings.get_string(i, k)
                        if '\n' in text:
                            text = text.replace('\n', '\\n')
                        file.write(f"{k}: {text}\n")
                    file.write('\n')
        print("Done writing strings.")
    except Exception as e:
        print(f"Error writing to uw-strings.txt: {e}")

if __name__ == "__main__":
    main()
