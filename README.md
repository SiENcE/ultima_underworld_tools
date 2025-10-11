# Ultima Underworld Tools

A collection of Python utilities for analyzing, extracting, and modifying content from Ultima Underworld games. These tools allow you to examine the structure of STRINGS.PAK and CNV.ARK files, extract and modify game strings and conversations, and even run conversation scripts in a virtual machine.

## Tools Included

### String Tools
1. **uw-strings-analyzer.py** - Analyzes the structure of STRINGS.PAK, showing the Huffman tree, block information, and more
2. **uw-strings-extractor.py** - Extracts all strings from STRINGS.PAK into a text file
3. **uw-strings-packer.py** - Repacks modified strings back into a new STRINGS.PAK file
4. **uw-strings-translator.py** - Tool for translating Ultima Underworld game text strings using Ollama (for local LLM translation) or Transformers (see [README_translator.md](/README_translator.md))

### Conversation Tools
5. **uw_cnv_decompiler.py** - Extracts conversations from CNV.ARK, decompresses UW2 archives, and decompiles bytecode to readable assembly
6. **uw_cnv_compiler.py** - Compiles conversation assembly files back to binary format and can update a slot in the CNV.ARK file
7. **uw_cnv_runner.py** - A virtual machine for running and testing Ultima Underworld conversation scripts

## Requirements

- Python 3.6 or higher
- Optional dependencies for the translator tool: Ollama or Transformers (see README_translator.md)

## Installation

Clone this repository or download the scripts:

```bash
git clone https://github.com/SiENcE/ultima_underworld_tools.git
cd ultima_underworld_tools
```

## Usage

### String Tools

#### 1. Analyzing STRINGS.PAK

Use the analyzer to examine the structure of your STRINGS.PAK file:

```bash
python uw-strings-analyzer.py path/to/strings.pak
```

Optional hexdump feature:

```bash
python uw-strings-analyzer.py path/to/strings.pak --hexdump [offset] [length]
```

This will generate a detailed analysis including:
- File header information
- Huffman tree structure
- Block information
- String encoding samples
- File integrity check

The analysis will also be exported to a `strings-analysis.json` file.

#### 2. Extracting Strings

To extract all strings from STRINGS.PAK to a text file:

```bash
python uw-strings-extractor.py
```

This assumes `strings.pak` is in the current directory. It will:
- Extract all strings into `uw-strings.txt`
- Save Huffman tree and block metadata to `uw-strings-metadata.json` (needed for repacking)

#### 3. Modifying and Repacking Strings

1. Edit the extracted `uw-strings.txt` file with any text editor
2. Run the packer to create a new STRINGS.PAK file:

```bash
python uw-strings-packer.py
```

#### 4. Translating Strings

See [README_translator.md](/README_translator.md) for detailed instructions on using the translator tool.

### Conversation Tools

#### 1. Extracting and Decompiling Conversations

Extract all conversations from CNV.ARK and decompile to assembly:

```bash
python uw_cnv_extractor_decompress_decompiler.py path/to/cnv.ark --output-dir conversations
```

This will:
- Automatically detect and decompress UW2 archives if needed
- Extract all conversation slots to individual binary and ASM files
- Create detailed metadata files with information about each conversation

You can also decompile a single binary conversation file:

```bash
python uw_cnv_extractor_decompress_decompiler.py path/to/conversation_XXXX.bin --decompile-binary
```

#### 2. Compiling Conversations

After modifying a conversation ASM file, compile it back to binary format:

```bash
python uw_cnv_compiler.py path/to/conversation_XXXX.asm --output output.bin
```

You can also update the original CNV.ARK file:

```bash
python uw_cnv_compiler.py path/to/conversation_XXXX.asm --update-cnv path/to/cnv.ark
```

#### 3. Running Conversations

Test a conversation script using the conversation virtual machine:

```bash
python uw_cnv_runner.py path/to/conversation_XXXX.asm --strings path/to/string_block.txt
```

This interactive tool allows you to:
- Execute conversation scripts
- Make dialogue choices
- Test conversation logic
- Simulate game world variables

## Notes on Editing

### Editing Strings

When modifying the extracted strings:
- Keep the `block:` and string index format intact
- You can modify the content of each string
- Use `\n` for line breaks
- Don't remove the ending pipe character (`|`) if present
- Adding new blocks or changing block IDs is not recommended

### Editing Conversations

When modifying conversation assembly files:
- Keep label definitions intact (lines ending with `:`)
- Instructions should maintain proper format (opcode with/without operand)
- Branches and jumps reference labels by name
- Don't modify the `Import` section comments as they're used by the compiler

## Technical Details

### STRINGS.PAK Format

STRINGS.PAK uses Huffman compression with the following structure:
- File header with Huffman tree nodes
- Block info table with block IDs and offsets
- Multiple string blocks containing:
  - String count
  - String offset table
  - Huffman-encoded string data

### CNV.ARK Format

The CNV.ARK file contains conversation scripts and uses:
- Compressed format in UW2 (uncompressed in UW1)
- File header with slot offsets
- Conversation headers with Huffman codes
- Import tables listing variables and functions
- Bytecode for script execution

See spec.txt for complete technical details on the conversation format.

## License

This project is licensed under the MIT License with additional terms - see the [LICENSE](LICENSE) file for details.
**Important:** Use of this software for training AI or machine learning models is strictly prohibited. See the LICENSE file for details.

## Author

Florian Fischer
