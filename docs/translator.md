# Ultima Underworld Strings Translator

A comprehensive tool for translating Ultima Underworld game text strings while preserving the exact format required for reimporting into the game.

## Overview

This translator tool processes extracted `uw-strings.txt` files from Ultima Underworld: The Stygian Abyss. It preserves the block structure and formatting of the original text while enabling translation to various languages. The tool supports multiple translation backends and can adapt to different hardware configurations.

## Features

- Preserves exact game file structure and special formatting
- Multiple translation backends (Ollama, Transformers)
- Context-aware translation for better quality
- Optimized for different hardware configurations (high and low-end GPUs, CPU)
- Multi-threaded processing with memory-efficient batching
- Translation validation to prevent overly long strings
- Special character preservation for game-specific terms
- Customizable umlaut handling for German translations
- Automatic error recovery for out-of-memory situations

## Installation

### Basic Dependencies

```bash
pip install -r string_tools/requirements-translator.txt
```

### Optional Dependencies

For GPU acceleration with Transformers backend:
```bash
pip install torch
```

For Ollama backend:
1. Install Ollama from https://ollama.ai/
2. Pull a suitable language model:
   ```bash
   ollama pull llama3   # For latest llama3 model
   ```

## Usage

### Basic Usage

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --source English --target German --backend ollama
```

### Using Transformers Backend

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend transformers
```

### For Memory-Constrained Systems (6GB VRAM or less)

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend transformers --low-memory --batch-size 4 --chunk-size 20
```

### For CPU-Only Processing

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend transformers --cpu
```

### With Contextual Translation (for better quality)

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend ollama --context
```

### Translation Validation (to prevent lengthy translations)

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend ollama --validate --max-ratio 2.0
```

### Preserve Special Terms

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --preserve-special-chars "X_$"
```

### German Umlaut Handling

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --target German --handle-umlauts ascii
```

### Test Mode (translate only first block)

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend ollama --test
```

### Processing a Limited Number of Blocks

This is useful for testing or when dividing work across multiple runs:

```bash
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend transformers --blocks 20
```

### Using a Specific Model

```bash
# With Ollama backend
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend ollama --model llama3:8b

# With Transformers backend
python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-translated.txt --backend transformers --model Helsinki-NLP/opus-mt-en-de
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--source`, `-s` | Source language (default: English) |
| `--target`, `-t` | Target language (default: German) |
| `--backend`, `-b` | Translation backend: `ollama`, `transformers`, or `dummy` |
| `--model`, `-m` | Specific model to use for translation |
| `--threads` | Number of translation threads (default: 4) |
| `--batch-size` | Batch size for translation (default: auto-determined) |
| `--test` | Test mode - only translate the first block |
| `--blocks`, `-n` | Limit translation to specified number of blocks |
| `--context` | Translate with block context (only works with Ollama backend) |
| `--chunk-size` | Number of strings to process in each chunk (default: 50) |
| `--low-memory` | Enable low memory mode for GPUs with limited VRAM |
| `--cpu` | Force using CPU even if GPU is available |
| `--validate` | Validate translation lengths and warn about overly long translations |
| `--max-ratio` | Maximum allowed ratio of translation length to original length (default: 2.0) |
| `--use-original-if-too-long` | Automatically use original text when translation exceeds max length ratio |
| `--handle-umlauts` | How to handle German umlauts: `none`=keep as is, `ascii`=replace with ae/oe/etc, `simple`=remove diacritics |
| `--preserve-special-chars` | Specify characters that identify words to keep untranslated (e.g. "X_$") |

## Translation Backends

### Ollama

Uses locally run LLMs through the Ollama framework. Works well for maintaining tone and style but can be slower.

Pros:
- Better preservation of game-specific terminology
- Context-aware translation option
- No internet connection required

Cons:
- May be slower than transformer models
- Requires more system resources

### Transformers

Uses Hugging Face's translation models. Faster and more resource-efficient.

Pros:
- More efficient for batch translation
- GPU acceleration for faster processing
- More memory efficient

Cons:
- May not capture game-specific terminology as well
- Limited context awareness

### Dummy

For testing translation pipeline. Simply adds a prefix to strings.

## Memory Management Tips

If you have limited GPU memory (6GB VRAM or less):

1. Start with `--low-memory` flag which:
   - Reduces batch and chunk sizes
   - Clears CUDA cache between batches
   - Implements automatic recovery from memory errors

2. If still encountering memory issues:
   - Reduce batch size manually: `--batch-size 2`
   - Reduce chunk size: `--chunk-size 10`
   - Try CPU mode: `--cpu`

3. Process the file in blocks:
   ```bash
   # First run - first 50 blocks
   python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-part1.txt --blocks 50
   
   # Second run - next 50 blocks
   # (Modify the script to start from block 51, or create a version that supports offset)
   ```

## Special Character Preservation

The `--preserve-special-chars` option allows you to specify characters that identify words which should remain untranslated. This is useful for:

- Game-specific terminology (e.g., spell names with special characters)
- Variable placeholders in dialogue
- Special formatting markers

For example, `--preserve-special-chars "X_$"` will prevent any words containing X, underscore, or $ from being translated.

## Umlaut Handling

When translating to German or other languages with special characters, you can control how umlauts and other diacritics are handled:

- `--handle-umlauts none`: Keep all special characters as is (default)
- `--handle-umlauts ascii`: Replace with ASCII equivalents (ä→ae, ö→oe, etc.)
- `--handle-umlauts simple`: Replace with basic characters (ä→a, ö→o, etc.)

This is helpful if the game's character set doesn't support certain special characters.

## Translation Validation

Use the `--validate` option to check if translations exceed a reasonable length compared to the original text:

- `--max-ratio 2.0`: Set the maximum allowed length ratio (default is 2.0)
- `--use-original-if-too-long`: Automatically revert to original text for strings that exceed the max ratio

This helps prevent issues with text overflow in game UI elements that have fixed width constraints.

## Workflow

1. Extract strings from STRINGS.PAK using `string_tools/uw-strings-extractor.py`
2. Translate the extracted strings using this tool
3. Pack the translated strings back using `string_tools/uw-strings-packer.py`

## Troubleshooting

### CUDA Out of Memory Errors

If you see `CUDA out of memory` errors:
- Try `--low-memory` flag
- Reduce batch size with `--batch-size 2`
- Reduce chunk size with `--chunk-size 10`
- Fall back to CPU with `--cpu`

The translator now includes automatic recovery from out-of-memory errors by reducing batch size dynamically and switching to CPU processing for problematic chunks when necessary.

### Unsupported Model Parameters

If you see errors about unsupported parameters:
- Try a different model with `--model` parameter
- Update the transformers library: `pip install --upgrade transformers`

### Slow Translation

If translation is too slow:
- If using CPU, try GPU if available
- Increase batch size (for GPU with sufficient memory)
- Reduce number of threads if CPU-bound

### Translation Length Issues

If you see warnings about translation length:
- Check the output file for strings that may be too long
- Use `--validate --use-original-if-too-long` to automatically handle problematic translations
- Consider using a different model that produces more concise translations

## Advanced Usage

### Creating a Multi-Stage Pipeline

For highest quality translations, consider a multi-stage approach:

1. Initial machine translation:
   ```bash
   python string_tools/uw-strings-translator.py uw-strings.txt uw-strings-draft.txt --backend transformers
   ```

2. Refinement with context-aware LLM:
   ```bash
   python string_tools/uw-strings-translator.py uw-strings-draft.txt uw-strings-final.txt --backend ollama --context
   ```

3. Validation and length checking:
   ```bash
   python string_tools/uw-strings-translator.py uw-strings-final.txt uw-strings-validated.txt --validate --use-original-if-too-long
   ```

### Language Code Reference

When using Transformers backend, you may need to specify language codes. Common codes:

- English: `en`
- German: `de`
- Spanish: `es`
- French: `fr`
- Italian: `it`
- Japanese: `ja`
- Russian: `ru`

The tool will attempt to convert full language names to codes automatically.

## After Translation

After completing translation, use the packer to create a new STRINGS.PAK file:

```bash
python string_tools/uw-strings-packer.py
```

Make sure to back up your original STRINGS.PAK file before replacing it!
