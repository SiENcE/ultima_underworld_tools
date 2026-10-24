#!/usr/bin/env python3
"""
Ultima Underworld STRINGS.PAK Translator Tool

This tool translates an extracted uw-strings.txt file into another language
while preserving the structure needed for repacking with uw-strings-packer.py.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
import queue
import threading
import time

# --- Translation Backend Options ---

# Option 1: Ollama - a local LLM runner
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Option 2: Local translation with Transformers
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    CUDA_AVAILABLE = False

# --- String Processing Classes ---

class StringBlock:
    """Represents a block of strings from the game."""
    def __init__(self, block_id, num_strings=0):
        self.block_id = block_id
        self.strings = []
        self.header = ""
    
    def add_string(self, index, text):
        """Add a string at the specified index, filling gaps if needed."""
        while len(self.strings) <= index:
            self.strings.append("")
        self.strings[index] = text
    
    def set_header(self, header):
        """Set the original header line for this block."""
        self.header = header

    def to_text(self, handle_umlauts="none"):
        """Convert the block back to text format for the output file."""
        lines = [self.header]
        for i, text in enumerate(self.strings):
            # Apply umlaut handling if enabled
            if handle_umlauts != "none":
                text = replace_umlauts(text, handle_umlauts)
                
            # Preserve newlines in output by escaping them
            if '\n' in text:
                text = text.replace('\n', '\\n')
            lines.append(f"{i}: {text}")
        return lines


class StringFileParser:
    """Parser for the uw-strings.txt file format."""
    def __init__(self):
        self.blocks = {}  # Dictionary mapping block_id to StringBlock objects
    
    def parse_file(self, filename):
        """Parse the extracted text file into blocks and strings."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                current_block = None
                current_block_id = None
                
                for line in f:
                    line = line.rstrip('\n')
                    if not line:
                        continue
                    
                    # Check if this is a block header
                    if line.startswith("block: "):
                        # Extract block ID
                        match = re.search(r"block: ([0-9a-fA-F]+);", line)
                        if match:
                            current_block_id = int(match.group(1), 16)
                            current_block = StringBlock(current_block_id)
                            current_block.set_header(line)
                            self.blocks[current_block_id] = current_block
                    
                    # Check if this is a string entry
                    elif current_block is not None and ":" in line:
                        parts = line.split(":", 1)
                        try:
                            index = int(parts[0].strip())
                            text = parts[1].strip()
                            
                            # Replace escaped newlines with actual newlines for processing
                            text = text.replace("\\n", "\n")
                            
                            current_block.add_string(index, text)
                        except ValueError:
                            print(f"Warning: Invalid string entry: {line}")
            
            return True
        except Exception as e:
            print(f"Error parsing {filename}: {e}")
            return False
    
    def write_file(self, filename, handle_umlauts="none"):
        """Write the blocks to a file in the same format."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Write header
                count = len(self.blocks)
                f.write(f"STRINGS.PAK: {count} string blocks.\n\n")
                
                # Write each block
                for block_id in sorted(self.blocks.keys()):
                    block = self.blocks[block_id]
                    for line in block.to_text(handle_umlauts):
                        f.write(f"{line}\n")
                    f.write("\n")  # Empty line between blocks
            
            return True
        except Exception as e:
            print(f"Error writing {filename}: {e}")
            return False
    
    def get_total_string_count(self):
        """Count the total number of strings across all blocks."""
        return sum(len(block.strings) for block in self.blocks.values())
    
    def limit_blocks(self, count):
        """Limit the number of blocks to process."""
        if count >= len(self.blocks):
            return  # No need to limit
        
        # Get the first N block IDs (sorted)
        block_ids = sorted(self.blocks.keys())[:count]
        
        # Keep only those blocks
        self.blocks = {block_id: self.blocks[block_id] for block_id in block_ids}

    def validate_translations(self, source_blocks, max_ratio=2.0, use_original_if_too_long=False):
        """
        Validate all translations against their original strings.
        
        Args:
            source_blocks (dict): Dictionary of original StringBlock objects
            max_ratio (float): Maximum allowed ratio of translation length to original length
            use_original_if_too_long (bool): If True, replace overly long translations with original text
            
        Returns:
            list: List of validation issues found
        """
        issues = []
        replacements = 0
        
        for block_id, block in self.blocks.items():
            # Skip if this block doesn't exist in the source
            if block_id not in source_blocks:
                continue
                
            source_block = source_blocks[block_id]
            
            # Compare each string
            for i, translated in enumerate(block.strings):
                # Skip if this string doesn't exist in the source
                if i >= len(source_block.strings):
                    continue
                    
                original = source_block.strings[i]
                
                # Skip empty strings
                if not original.strip():
                    continue
                    
                # Validate length
                if not validate_translation_length(original, translated, max_ratio):
                    original_len = len(original)
                    translated_len = len(translated)
                    ratio = translated_len / original_len
                    
                    issue = {
                        "block_id": block_id,
                        "string_idx": i,
                        "original": original,
                        "original_length": original_len,
                        "translated": translated,
                        "translated_length": translated_len,
                        "ratio": ratio
                    }
                    issues.append(issue)
                    
                    # Replace with original if requested
                    if use_original_if_too_long:
                        self.blocks[block_id].strings[i] = original
                        replacements += 1
        
        return issues, replacements

def validate_translation_length(original, translation, max_ratio=2.0):
    """
    Validate that the translation isn't too much longer than the original.
    
    Args:
        original (str): The original text
        translation (str): The translated text
        max_ratio (float): Maximum allowed ratio of translation length to original length
        
    Returns:
        bool: True if valid, False if too long
    """
    # Skip empty strings
    if not original.strip():
        return True
        
    # Calculate the length ratio
    original_len = len(original)
    translation_len = len(translation)
    ratio = translation_len / original_len if original_len > 0 else 0
    
    # Check if translation is too long
    return ratio <= max_ratio

def replace_umlauts(text, replacement_type="ascii"):
    """
    Replace German umlauts and special characters with equivalents
    based on the specified replacement type.
    
    Args:
        text (str): The string to process
        replacement_type (str): 
            "ascii" - Replace with ASCII equivalents (ä -> ae)
            "simple" - Replace with basic Latin characters (ä -> a)
            "none" - No replacement (will fail if character not in Huffman table)
        
    Returns:
        str: The processed string with umlauts replaced
    """
    if replacement_type == "none":
        return text
        
    if replacement_type == "ascii":
        # Full ASCII equivalent class StringBlock:
        replacements = {
            'ü': 'ue', 'Ü': 'Ue',
            'ö': 'oe', 'Ö': 'Oe',
            'ä': 'ae', 'Ä': 'Ae',
            'ß': 'ss',
            '¶': 'P',  # Paragraph symbol
            '„': '"',  # German quotation marks
            '‚': "'",  # German single quotation
            # Add any other special characters as needed
        }
    else:  # "simple"
        # Simple replacements (lose diacritics)
        replacements = {
            'ü': 'u', 'Ü': 'U',
            'ö': 'o', 'Ö': 'O',
            'ä': 'a', 'Ä': 'A',
            'ß': 's',
            '¶': 'P',
            '„': '"',
            '‚': "'",
        }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text

def preserve_newlines(text, translate_func):
    """Preserve newlines during translation by using a special token."""
    if not text or '\n' not in text:
        return translate_func(text)
    
    # Replace newlines with a unique token
    newline_token = "¶NEWLINE¶"
    text_with_tokens = text.replace('\n', newline_token)
    
    # Translate the text with tokens
    translated = translate_func(text_with_tokens)
    
    # Restore newlines
    result = translated.replace(newline_token, '\n')
    return result

def contains_special_chars(word, special_chars):
    """
    Check if a word contains any of the specified special characters.
    
    Args:
        word (str): The word to check
        special_chars (str): String of special characters to check for
        
    Returns:
        bool: True if the word contains any special character, False otherwise
    """
    if not word or not special_chars:
        return False
        
    return any(char in word for char in special_chars)

def mark_special_terms(text, special_chars):
    """
    Mark words containing special characters with markers to prevent translation.
    
    Args:
        text (str): The text to process
        special_chars (str): String of special characters to check for
        
    Returns:
        str: Text with special terms marked
    """
    if not text or not special_chars:
        return text
        
    # Split text into words, keeping delimiters
    import re
    words = re.findall(r'(\w+|\W+)', text)
    
    # Mark words containing special characters
    marked_text = ""
    for word in words:
        if word.strip() and contains_special_chars(word, special_chars):
            # Surround with markers that will be recognized during translation
            marked_text += f"<<{word}>>"
        else:
            marked_text += word
            
    return marked_text

def unmark_special_terms(text):
    """
    Remove markers from around special terms after translation.
    
    Args:
        text (str): Text with markers around special terms
        
    Returns:
        str: Clean text with markers removed
    """
    if not text:
        return text
        
    # Remove markers
    import re
    return re.sub(r'<<(.+?)>>', r'\1', text)

# --- Translation Backends ---

class TranslationBackend:
    """Base class for translation backends."""
    def __init__(self):
        self.name = "Base"
        self.preserve_special_chars = ""
    
    def initialize(self, source_lang, target_lang, preserve_special_chars=""):
        """Initialize the translation backend."""
        self.preserve_special_chars = preserve_special_chars
        return False
    
    def translate(self, text):
        """Translate a single string."""
        return text
    
    def translate_with_preservation(self, text):
        """Translate a string while preserving special terms."""
        if not text.strip() or not self.preserve_special_chars:
            return self.translate(text)
            
        # Mark special terms
        marked_text = mark_special_terms(text, self.preserve_special_chars)
        
        # Translate the marked text
        translated = self.translate(marked_text)
        
        # Remove markers
        return unmark_special_terms(translated)
    
    def translate_batch(self, texts, callback=None):
        """Translate a batch of strings."""
        results = []
        for text in texts:
            result = self.translate_with_preservation(text)
            results.append(result)
            if callback:
                callback(text, result)
        return results
    

class OllamaTranslationBackend(TranslationBackend):
    """Translation backend using Ollama."""
    def __init__(self):
        super().__init__()
        self.name = "Ollama"
        self.model = "llama3"  # Default model
        self.source_lang = "English"
        self.target_lang = "German"
        self.system_prompt = ""
    
    def initialize(self, source_lang, target_lang, model=None, preserve_special_chars=""):
        """Initialize the Ollama translation backend."""
        if not OLLAMA_AVAILABLE:
            print("Error: Ollama is not installed. Run: pip install ollama")
            return False
        
        if model:
            self.model = model
        
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.preserve_special_chars = preserve_special_chars
        
        # Update the system prompt with umlaut handling instructions
        umlaut_note = ""
        if target_lang.lower() in ["german", "de", "deutsch"]:
            umlaut_note = (
                f" Be careful with German umlauts (ä, ö, ü, ß) - if a literal translation would "
                f"use these characters, either provide an alternative without umlauts (e.g., use 'ae' instead of 'ä') "
                f"or include both versions (e.g., 'König (Koenig)')."
            )

        # Update system prompt to explain special term handling
        preservation_note = ""
        if preserve_special_chars:
            special_chars_display = " ".join(preserve_special_chars)
            preservation_note = (
                f" Any text between << and >> markers must be kept EXACTLY as is, without translation. "
                f"These are special terms that should remain in the original language. "
                f"For example, <<Arx>> should remain as Arx in your translation."
            )

        self.system_prompt = (
            f"You are translating text from the classic RPG game 'Ultima Underworld: The Stygian Abyss' from {source_lang} to {target_lang}. "
            f"This is a first-person fantasy RPG from 1992 set in a medieval underground world with magic, monsters, and a rich storyline. "
            f"Translate the following text, preserving the original fantasy tone and terminology. "
            f"Preserve any formatting, spacing, and special characters including ¶NEWLINE¶ tokens exactly as they appear. "
            f"Only respond with the translated text, nothing else. "
            f"Translate game-specific terms and character/location names appropriately for a fantasy setting."
            f"{umlaut_note}"
            f"{preservation_note}"
        )
        
        # Test the connection to Ollama
        try:
            models = ollama.list()
            if not any(m['name'] == self.model for m in models.get('models', [])):
                print(f"Warning: Model {self.model} not found in Ollama. Available models:")
                for m in models.get('models', []):
                    print(f"  - {m['name']}")
                print(f"Will try to use {self.model} anyway, but it might fail.")
            return True
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            print("Make sure Ollama is installed and running on your machine.")
            print("Installation instructions: https://github.com/ollama/ollama")
            return False
    
    def translate(self, text):
        """Translate a single string using Ollama."""
        if not text.strip():
            return text
        
        try:
            # Use a closure to capture the translation logic
            def translate_with_ollama(input_text):
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self.system_prompt + " Preserve any ¶NEWLINE¶ tokens exactly as they appear."
                        },
                        {
                            "role": "user",
                            "content": input_text
                        }
                    ],
                    stream=False,
                    options={"temperature": 0.2, "top_p": 0.9}
                )
                return response['message']['content'].strip()
            
            # Use the helper function to preserve newlines
            return preserve_newlines(text, translate_with_ollama)
        except Exception as e:
            print(f"Translation error: {e}")
            return text
    
    def translate_batch(self, texts, max_batch_size=5):
        """Translate a batch of texts with Ollama.
        Note: This creates sub-batches since Ollama doesn't natively support large batches."""
        if not texts:
            return texts
        
        results = []
        # Process in smaller sub-batches (Ollama can't handle large batches efficiently)
        for i in range(0, len(texts), max_batch_size):
            sub_batch = texts[i:i+max_batch_size]
            
            # Create a prompt with multiple texts to translate
            batch_prompt = "Translate each of the following texts:\n\n"
            for idx, text in enumerate(sub_batch):
                # Replace newlines with markers
                if '\n' in text:
                    text = text.replace('\n', "¶NEWLINE¶")
                batch_prompt += f"TEXT {idx+1}: {text}\n\n"
            
            batch_prompt += "TRANSLATIONS (keep same order and numbering):"
            
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": batch_prompt
                        }
                    ],
                    stream=False,
                    options={"temperature": 0.2, "top_p": 0.9}
                )
                
                response_text = response['message']['content']
                
                # Parse the response
                translated_batch = []
                current_text_idx = 0
                
                # Simple parsing approach - look for "TEXT X:" patterns
                for line in response_text.split('\n'):
                    line = line.strip()
                    if line.startswith("TEXT") and ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            trans_text = parts[1].strip()
                            trans_text = trans_text.replace("¶NEWLINE¶", '\n')
                            translated_batch.append(trans_text)
                            current_text_idx += 1
                
                # If we couldn't parse correctly, try to match the count at least
                if len(translated_batch) != len(sub_batch):
                    print(f"Warning: Batch parsing issue. Expected {len(sub_batch)} translations, got {len(translated_batch)}")
                    # Simple fallback - just do individual translations
                    translated_batch = []
                    for text in sub_batch:
                        translated_batch.append(self.translate(text))
                
                results.extend(translated_batch)
                
            except Exception as e:
                print(f"Batch translation error: {e}")
                # Fall back to individual translation
                for text in sub_batch:
                    results.append(self.translate(text))
        
        return results


class TransformersTranslationBackend(TranslationBackend):
    """Translation backend using Hugging Face Transformers."""
    def __init__(self):
        super().__init__()
        self.name = "Transformers"
        self.translator = None
        self.source_lang = "en"
        self.target_lang = "es"
    
    def initialize(self, source_lang, target_lang, model=None, preserve_special_chars=""):
        """Initialize the Transformers translation backend."""
        if not TRANSFORMERS_AVAILABLE:
            print("Error: Transformers is not installed. Run: pip install transformers sentencepiece")
            return False
        
        # Map language names to codes if needed
        lang_map = {
            "English": "en", "Spanish": "es", "French": "fr", "German": "de",
            "Italian": "it", "Portuguese": "pt", "Russian": "ru", "Japanese": "ja",
            "Chinese": "zh", "Korean": "ko", "Arabic": "ar"
        }
        
        self.source_lang = lang_map.get(source_lang, source_lang).lower()
        self.target_lang = lang_map.get(target_lang, target_lang).lower()
        self.preserve_special_chars = preserve_special_chars
        
        # Use specified model or default to Helsinki-NLP
        model_name = model or f"Helsinki-NLP/opus-mt-{self.source_lang}-{self.target_lang}"
        
        try:
            print(f"Loading translation model: {model_name}")
            # Enable GPU if available
            device = "cuda" if CUDA_AVAILABLE else "cpu"
            if device == "cuda":
                print(f"CUDA is available! Using GPU acceleration.")
            else:
                print(f"CUDA not available. Using CPU.")
            
            self.translator = pipeline("translation", model=model_name, device=0)
            return True
        except Exception as e:
            print(f"Error loading translation model: {e}")
            print(f"Try specifying a different model with --model parameter.")
            return False

    def setup_device(self, force_cpu=False, low_memory=False):
        """Configure device settings based on available hardware and memory constraints."""
        if not TRANSFORMERS_AVAILABLE:
            return
            
        if force_cpu:
            print("Forcing CPU mode as requested")
            self.device = "cpu"
            return
            
        if not CUDA_AVAILABLE:
            print("CUDA not available. Using CPU mode.")
            self.device = "cpu"
            return
            
        # Get GPU info
        import torch
        device_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(current_device)
        
        # Get memory info
        total_memory = torch.cuda.get_device_properties(current_device).total_memory
        total_memory_gb = round(total_memory / (1024**3), 2)
        
        print(f"Using GPU: {device_name} with {total_memory_gb}GB VRAM")
        
        # Set memory efficient settings for low-memory GPUs
        if low_memory or total_memory_gb < 8:
            print("Enabling low-memory optimizations for limited VRAM")
            
            # Set PyTorch to optimize for memory usage
            if hasattr(torch.cuda, 'empty_cache'):
                torch.cuda.empty_cache()
                
            # Load model in 16-bit precision if available
            if hasattr(self, 'translator') and self.translator is not None:
                try:
                    import torch.amp as amp
                    print("Enabling automatic mixed precision for memory efficiency")
                    self.amp_enabled = True
                except (ImportError, AttributeError):
                    self.amp_enabled = False
                    
        self.device = f"cuda:{current_device}"

    def translate(self, text):
        """Translate a single string using Transformers."""
        if not text.strip() or self.translator is None:
            return text
        
        try:
            # Use a closure to capture the translation logic
            def translate_with_transformers(input_text):
                result = self.translator(input_text, max_length=512)
                return result[0]['translation_text']
            
            # Use the helper function to preserve newlines
            return preserve_newlines(text, translate_with_transformers)
        except Exception as e:
            print(f"Translation error: {e}")
            return text
    
    def translate_batch(self, texts, progress_callback=None, current_progress=0, total_progress=1):
        """Translate a batch of strings using Dataset for optimal GPU utilization."""
        if not texts or self.translator is None:
            return texts
        
        try:
            # Import datasets library
            from datasets import Dataset
            
            # Filter out empty strings - we'll add them back after
            non_empty_texts = []
            indices = []
            
            for i, text in enumerate(texts):
                if text.strip():
                    non_empty_texts.append(text)
                    indices.append(i)
            
            if not non_empty_texts:
                return texts
            
            # Process batch with newline preservation
            processed_texts = []
            for text in non_empty_texts:
                if '\n' in text:
                    newline_token = "¶NEWLINE¶"
                    processed_texts.append(text.replace('\n', newline_token))
                else:
                    processed_texts.append(text)
            
            # Use a much smaller batch size for memory-constrained systems
            # Adjust these values based on available VRAM
            batch_size = 8  # Smaller batch size for limited VRAM
            chunk_size = 50  # Process fewer items at a time
            
            translated = []
            
            # Break the processing into very small chunks to avoid OOM errors
            for i in range(0, len(processed_texts), chunk_size):
                try:
                    # Get a chunk of texts
                    chunk = processed_texts[i:i+chunk_size]
                    
                    # Create a Dataset object for just this small chunk
                    chunk_dataset = Dataset.from_dict({"text": chunk})
                    
                    # Clear CUDA cache if available to free up memory
                    if CUDA_AVAILABLE:
                        import torch
                        torch.cuda.empty_cache()
                    
                    # Translate the chunk with small batch size
                    chunk_results = self.translator(
                        chunk_dataset["text"], 
                        batch_size=batch_size
                    )
                    
                    chunk_translated = [r["translation_text"] for r in chunk_results]
                    translated.extend(chunk_translated)
                    
                    # Update progress
                    if progress_callback:
                        items_done = min(current_progress + i + len(chunk), total_progress)
                        progress_callback(items_done, total_progress)
                    
                except RuntimeError as e:
                    if "CUDA out of memory" in str(e) or "OOM" in str(e):
                        # If we hit OOM, reduce batch size and try again
                        print(f"\nCUDA out of memory error. Reducing batch size...")
                        batch_size = max(1, batch_size // 2)
                        
                        # If batch size is already 1, switch to CPU
                        if batch_size == 1 and CUDA_AVAILABLE:
                            print("Switching to CPU for this chunk...")
                            device = self.translator.device
                            self.translator.to("cpu")
                            
                            # Process this chunk on CPU
                            chunk_results = self.translator(
                                chunk_dataset["text"], 
                                batch_size=1
                            )
                            
                            # Switch back to GPU for next chunks
                            self.translator.to(device)
                            
                            chunk_translated = [r["translation_text"] for r in chunk_results]
                            translated.extend(chunk_translated)
                        else:
                            # Try again with smaller batch size
                            i -= chunk_size  # Go back and retry this chunk
                            continue
                    else:
                        raise
            
            # Restore newlines
            translated = [t.replace("¶NEWLINE¶", '\n') for t in translated]
            
            # Reconstruct original list with translations
            result = list(texts)  # Make a copy
            for idx, trans in zip(indices, translated):
                result[idx] = trans
                
            return result
        except ImportError:
            print("Warning: 'datasets' library not found. Install with: pip install datasets")
            # Fall back to non-dataset batch processing
            return self._fallback_batch_translate(texts, progress_callback, 
                                                 current_progress, total_progress)
        except Exception as e:
            print(f"Batch translation error: {e}")
            print("Falling back to individual translation...")
            return self._fallback_batch_translate(texts, progress_callback,
                                                 current_progress, total_progress)

    def _fallback_batch_translate(self, texts, progress_callback=None, 
                                 current_progress=0, total_progress=1):
        """Fallback batch translation without datasets library."""
        results = []
        
        # Process in small chunks to avoid memory issues
        chunk_size = 20
        for i in range(0, len(texts), chunk_size):
            chunk = texts[i:i+chunk_size]
            
            # Clear CUDA cache if available
            if CUDA_AVAILABLE:
                import torch
                torch.cuda.empty_cache()
            
            for j, text in enumerate(chunk):
                # Skip empty strings
                if not text.strip():
                    results.append(text)
                    continue
                    
                # Use the helper function to preserve newlines
                translated = preserve_newlines(text, lambda t: self.translator(t, max_length=512)[0]['translation_text'])
                results.append(translated)
                
                # Update progress
                if progress_callback:
                    items_done = min(current_progress + i + j + 1, total_progress)
                    progress_callback(items_done, total_progress)
        
        return results


class DummyTranslationBackend(TranslationBackend):
    """Dummy backend that adds a prefix to each string for testing."""
    def __init__(self):
        super().__init__()
        self.name = "Dummy"
        self.target_lang = "Test"
    
    def initialize(self, source_lang, target_lang, model=None, preserve_special_chars=""):
        """Initialize the dummy translation backend."""
        self.target_lang = target_lang
        self.preserve_special_chars = preserve_special_chars
        return True
    
    def translate(self, text):
        """'Translate' by adding a prefix."""
        if not text.strip():
            return text
        
        # Use the helper function to preserve newlines
        return preserve_newlines(text, lambda t: f"[{self.target_lang}] {t}")


# --- Multithreaded Translation ---

class TranslationWorker:
    """Handles multithreaded translation to improve performance."""
    def __init__(self, backend, num_threads=4, batch_size=10):
        self.backend = backend
        self.num_threads = num_threads
        self.batch_size = batch_size
        self.input_queue = queue.Queue()
        self.output_dict = {}
        self.workers = []
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.progress_callback = None
        self.total_items = 0
        self.processed_items = 0
    
    def worker_thread(self):
        """Worker thread that processes translations."""
        while not self.stop_event.is_set():
            try:
                # Get a batch of items to translate
                items = []
                for _ in range(self.batch_size):
                    try:
                        item = self.input_queue.get(block=True, timeout=0.5)
                        items.append(item)
                    except queue.Empty:
                        break
                
                if not items:
                    continue
                
                # Process the batch
                for block_id, index, text in items:
                    translated = self.backend.translate(text)
                    
                    # Store the result
                    with self.lock:
                        self.output_dict[(block_id, index)] = translated
                        self.processed_items += 1
                        
                        # Report progress
                        if self.progress_callback:
                            self.progress_callback(self.processed_items, self.total_items)
                    
                    # Mark as done
                    self.input_queue.task_done()
            
            except Exception as e:
                print(f"Worker error: {e}")
    
    def start_workers(self):
        """Start the worker threads."""
        self.workers = []
        self.stop_event.clear()
        
        for _ in range(self.num_threads):
            thread = threading.Thread(target=self.worker_thread)
            thread.daemon = True
            thread.start()
            self.workers.append(thread)
    
    def stop_workers(self):
        """Stop the worker threads."""
        self.stop_event.set()
        for worker in self.workers:
            worker.join(timeout=1.0)
    
    def translate_strings(self, blocks, progress_callback=None):
        """Translate all strings in the blocks."""
        self.progress_callback = progress_callback
        self.output_dict = {}
        self.processed_items = 0
        
        # Count total strings and enqueue them
        self.total_items = 0
        for block_id, block in blocks.items():
            for index, text in enumerate(block.strings):
                if text.strip():  # Only translate non-empty strings
                    self.input_queue.put((block_id, index, text))
                    self.total_items += 1
        
        # Start workers
        self.start_workers()
        
        # Wait for completion
        self.input_queue.join()
        
        # Stop workers
        self.stop_workers()
        
        # Update blocks with translated strings
        for (block_id, index), translated in self.output_dict.items():
            if block_id in blocks:
                blocks[block_id].strings[index] = translated
        
        return blocks
    
    def translate_dataset(self, blocks, progress_callback=None, batch_size=32):
        """Translate strings using dataset approach with batching for GPU efficiency."""
        self.progress_callback = progress_callback
        self.output_dict = {}
        self.processed_items = 0
        
        # Build a dataset of all strings
        dataset = []
        for block_id, block in blocks.items():
            for index, text in enumerate(block.strings):
                if text.strip():  # Only include non-empty strings
                    dataset.append((block_id, index, text))
        
        self.total_items = len(dataset)
        
        # Process in reasonable chunks to show progress (1000 items per chunk)
        chunk_size = 1000  # Adjust based on your needs
        for i in range(0, self.total_items, chunk_size):
            chunk = dataset[i:i+chunk_size]
            
            # Extract just the text for batch processing
            chunk_ids = [(b_id, idx) for b_id, idx, _ in chunk]
            chunk_texts = [text for _, _, text in chunk]
            
            # Translate the chunk
            if hasattr(self.backend, 'translate_batch'):
                translated_texts = self.backend.translate_batch(
                    chunk_texts, 
                    progress_callback=progress_callback,
                    current_progress=i,
                    total_progress=self.total_items
                )
            else:
                # Fall back to sequential for backends without batch support
                translated_texts = []
                for text in chunk_texts:
                    translated_texts.append(self.backend.translate(text))
                    self.processed_items += 1
                    if progress_callback:
                        progress_callback(self.processed_items, self.total_items)
            
            # Update the output dictionary
            for (b_id, idx), translated in zip(chunk_ids, translated_texts):
                self.output_dict[(b_id, idx)] = translated
                self.processed_items += 1
        
        # Final progress update
        if progress_callback:
            progress_callback(self.total_items, self.total_items)
        
        # Update blocks with translated strings
        for (block_id, index), translated in self.output_dict.items():
            if block_id in blocks and index < len(blocks[block_id].strings):
                blocks[block_id].strings[index] = translated
        
        return blocks
    
    def translate_with_context(self, blocks, progress_callback=None):
        """Translate strings with block context for better coherence."""
        self.progress_callback = progress_callback
        self.output_dict = {}
        self.processed_items = 0
        
        # Count total strings
        self.total_items = 0
        for block in blocks.values():
            for text in block.strings:
                if text.strip():
                    self.total_items += 1
        
        # Process each block as a context unit
        for block_id, block in blocks.items():
            # Skip empty blocks
            if not any(s.strip() for s in block.strings):
                continue
                
            # Create context by joining all non-empty strings
            block_context = "\n---\n".join([
                f"String {i}: {text}" for i, text in enumerate(block.strings) if text.strip()
            ])
            
            # Include block info in context
            context_header = f"Block {block_id:04x}: The following strings are related and come from the same dialogue or text section in Ultima Underworld:\n\n"
            
            # Create a function to translate with context
            def translate_with_block_context(text_with_index):
                index, text = text_with_index
                if not text.strip():
                    return index, text
                
                # Highlight the current string in the context
                marked_context = context_header + block_context.replace(
                    f"String {index}: {text}", 
                    f"String {index} [TRANSLATE THIS]: {text}"
                )
                
                # Prepare translation prompt
                prompt = (
                    f"Below is a group of related text strings from Ultima Underworld. "
                    f"Please translate ONLY the string marked with [TRANSLATE THIS]. "
                    f"Consider the surrounding text for context but only return the translation of the marked string.\n\n"
                    f"{marked_context}\n\n"
                    f"Translation of string {index} ONLY:"
                )
                
                try:
                    # Create custom system prompt for context-aware translation
                    messages = [
                        {
                            "role": "system",
                            "content": self.backend.system_prompt
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                    
                    if hasattr(self.backend, 'model'):
                        response = ollama.chat(
                            model=self.backend.model,
                            messages=messages,
                            stream=False,
                            options={"temperature": 0.2, "top_p": 0.9}
                        )
                        translated = response['message']['content'].strip()
                    else:
                        # Fall back to regular translation for non-Ollama backends
                        translated = self.backend.translate(text)
                    
                    return index, translated
                except Exception as e:
                    print(f"\nError translating string {index} in block {block_id:04x}: {e}")
                    return index, text
            
            # Create a list of (index, text) pairs for non-empty strings
            string_pairs = [(i, s) for i, s in enumerate(block.strings) if s.strip()]
            
            # Process each string in the block
            for index, text in string_pairs:
                if self.stop_event.is_set():
                    break
                    
                idx, translated = translate_with_block_context((index, text))
                
                # Store results
                with self.lock:
                    self.output_dict[(block_id, idx)] = translated
                    self.processed_items += 1
                    
                    # Report progress
                    if self.progress_callback:
                        self.progress_callback(self.processed_items, self.total_items)
        
        # Update blocks with translated strings
        for (block_id, index), translated in self.output_dict.items():
            if block_id in blocks:
                try:
                    blocks[block_id].strings[index] = translated
                except IndexError:
                    print(f"Error: Index {index} out of range for block {block_id}")
        
        return blocks


# --- User Interface ---

def display_progress(current, total, prefix='Progress', bar_length=50):
    """Display a progress bar."""
    progress = float(current) / total if total > 0 else 0
    filled_length = int(bar_length * progress)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    percent = int(100 * progress)
    print(f'\r{prefix}: |{bar}| {percent}% ({current}/{total})', end='')
    if current == total:
        print()


def get_available_backends():
    """Return a list of available translation backends."""
    backends = [DummyTranslationBackend()]  # Always available for testing
    
    if OLLAMA_AVAILABLE:
        backends.append(OllamaTranslationBackend())
    
    if TRANSFORMERS_AVAILABLE:
        backends.append(TransformersTranslationBackend())
    
    return backends


def main():
    parser = argparse.ArgumentParser(description='Translate uw-strings.txt to another language.')
    parser.add_argument('input_file', help='Input strings file (uw-strings.txt)')
    parser.add_argument('output_file', help='Output translated strings file')
    parser.add_argument('--source', '-s', default='English', help='Source language (default: English)')
    parser.add_argument('--target', '-t', default='German', help='Target language (default: German)')
    parser.add_argument('--backend', '-b', choices=['ollama', 'transformers', 'dummy'], default='dummy',
                        help='Translation backend to use (default: dummy)')
    parser.add_argument('--model', '-m', help='Model to use for translation (backend-specific)')
    parser.add_argument('--threads', type=int, default=4, help='Number of translation threads (default: 4)')
    parser.add_argument('--batch-size', type=int, help='Batch size for translation (default: auto)')
    parser.add_argument('--test', action='store_true', help='Test mode: only translate first block')
    parser.add_argument('--blocks', '-n', type=int, help='Limit translation to specified number of blocks')
    parser.add_argument('--context', action='store_true', 
                    help='Translate with block context (only works with ollama backend)')
    parser.add_argument('--chunk-size', type=int, default=50, 
                    help='Number of strings to process in each chunk (default: 50)')
    parser.add_argument('--low-memory', action='store_true',
                    help='Enable low memory mode for GPUs with limited VRAM')
    parser.add_argument('--cpu', action='store_true',
                    help='Force using CPU even if GPU is available')
    parser.add_argument('--handle-umlauts', choices=['none', 'ascii', 'simple'], default='none',
                    help='How to handle German umlauts: none=keep as is, ascii=replace with ae/oe/etc, simple=remove diacritics')
    parser.add_argument('--validate', action='store_true',
                       help='Validate translation lengths and warn about overly long translations')
    parser.add_argument('--max-ratio', type=float, default=2.0,
                       help='Maximum allowed ratio of translation length to original length (default: 2.0)')
    parser.add_argument('--use-original-if-too-long', action='store_true',
                       help='Automatically use original text when translation exceeds max length ratio')
    parser.add_argument('--preserve-special-chars', 
                        help='Specify characters that identify words to keep untranslated (e.g. "X_$")')
    args = parser.parse_args()
    
    print(f"Ultima Underworld STRINGS.PAK Translator")
    print(f"=======================================")
    print(f"Input file: {args.input_file}")
    print(f"Output file: {args.output_file}")
    print(f"Source language: {args.source}")
    print(f"Target language: {args.target}")
    print(f"Translation backend: {args.backend}")
    if args.model:
        print(f"Model: {args.model}")
    print(f"Threads: {args.threads}")
    print(f"Test mode: {'Yes' if args.test else 'No'}")
    if args.blocks:
        print(f"Block limit: {args.blocks}")
    print(f"Contextual translation: {'Yes' if args.context else 'No'}")
    print()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file {args.input_file} not found")
        return 1
    
    # Parse input file
    parser = StringFileParser()
    print(f"Parsing input file {args.input_file}...")
    if not parser.parse_file(args.input_file):
        print("Failed to parse input file")
        return 1
    
    total_blocks = len(parser.blocks)
    total_strings = parser.get_total_string_count()
    print(f"Found {total_blocks} blocks with {total_strings} strings")
    
    # If testing, limit to first block only
    if args.test:
        print("Test mode: Only processing the first block")
        first_block_id = min(parser.blocks.keys())
        test_block = parser.blocks[first_block_id]
        parser.blocks = {first_block_id: test_block}
    # If block limit is specified, limit blocks
    elif args.blocks:
        if args.blocks < 1:
            print("Error: Block count must be at least 1")
            return 1
        if args.blocks < total_blocks:
            print(f"Limiting to first {args.blocks} blocks out of {total_blocks}")
            parser.limit_blocks(args.blocks)
    
    # Initialize translation backend with memory settings
    backend = None
    available_backends = get_available_backends()
    backend_map = {b.name.lower(): b for b in available_backends}
    
    if args.backend in backend_map:
        backend = backend_map[args.backend]
    else:
        print(f"Backend {args.backend} not available. Using Dummy backend.")
        backend = DummyTranslationBackend()
    
    print(f"Initializing {backend.name} translation backend...")
    
    # Configure memory settings for transformers backend
    if args.backend == 'transformers' and isinstance(backend, TransformersTranslationBackend):
        backend.setup_device(force_cpu=args.cpu, low_memory=args.low_memory)
    
    # Initialize with preserve_special_chars parameter
    if not backend.initialize(args.source, args.target, args.model, args.preserve_special_chars):
        print("Failed to initialize translation backend")
        return 1

    # If preserve-special-chars is provided, show info about it
    if args.preserve_special_chars:
        print(f"Words containing any of these characters will remain untranslated: {args.preserve_special_chars}")
    
    # Define batch size based on backend, memory settings, and CUDA availability
    batch_size = args.batch_size
    if batch_size is None:
        if args.backend == 'transformers':
            if args.low_memory or args.cpu:
                batch_size = 4  # Very conservative for low memory
            else:
                batch_size = 16 if CUDA_AVAILABLE else 8
        else:
            batch_size = 8
    
    # Define chunk size based on memory constraints
    chunk_size = args.chunk_size
    if args.low_memory and chunk_size > 20:
        chunk_size = 20  # Smaller chunks for low memory
    
    print(f"Using batch size: {batch_size}, chunk size: {chunk_size}")
    
    # Create translation worker
    worker = TranslationWorker(backend, num_threads=args.threads, batch_size=args.batch_size or 10)
    
    # Start translation
    print(f"Translating strings from {args.source} to {args.target}...")
    start_time = time.time()
    
    # Define progress callback
    def progress_update(current, total):
        display_progress(current, total, prefix=f"Translating with {backend.name}")
    
    # Choose translation method
    if args.context and args.backend == 'ollama':
        print("Using contextual translation...")
        worker.translate_with_context(parser.blocks, progress_callback=progress_update)
    else:
        # Use dataset approach for efficient batching
        worker.translate_dataset(parser.blocks, progress_callback=progress_update, batch_size=batch_size)

    # If validation is requested, perform it before writing the output file
    if args.validate:
        print("\nValidating translation lengths...")
        
        # First, load the original file for comparison
        original_parser = StringFileParser()
        if not original_parser.parse_file(args.input_file):
            print("Failed to parse original file for validation")
        else:
            # Perform validation
            issues, replacements = parser.validate_translations(
                original_parser.blocks, 
                args.max_ratio,
                args.use_original_if_too_long
            )
            
            # Report any issues found
            if issues:
                print(f"\nFound {len(issues)} strings with potentially excessive length:")
                print("-" * 80)
                
                for issue in issues:
                    block_id = issue["block_id"]
                    string_idx = issue["string_idx"]
                    original = issue["original"].replace("\n", "\\n")
                    translated = issue["translated"].replace("\n", "\\n")
                    
                    if len(original) > 50:
                        original = original[:47] + "..."
                    if len(translated) > 50:
                        translated = translated[:47] + "..."
                    
                    print(f"Block {block_id:04x}, String {string_idx}:")
                    print(f"  Original ({issue['original_length']} chars): {original}")
                    print(f"  Translated ({issue['translated_length']} chars): {translated}")
                    print(f"  Ratio: {issue['ratio']:.2f}x")
                    print("-" * 80)
                
                if args.use_original_if_too_long:
                    print(f"\nReplaced {replacements} overly long translations with original text.")
                else:
                    print(f"\nWarning: {len(issues)} translations exceed the maximum length ratio of {args.max_ratio}.")
                    print("These translations may cause issues in-game or be truncated.")
                    print("Consider revising them to be more concise.")
                    print("Use --use-original-if-too-long to automatically replace them.")
                    
                    # Ask if user wants to continue
                    if not args.test:  # Don't ask in test mode
                        response = input("\nDo you want to continue and write the output file anyway? (y/n): ")
                        if response.lower() != 'y':
                            print("Aborting without writing output file.")
                            return 1
            else:
                print("All translations have acceptable lengths.")
    
    # Write output file
    print(f"\nWriting translated strings to {args.output_file}...")
    if args.handle_umlauts != "none":
        print(f"Applying umlaut handling: {args.handle_umlauts}")
    if not parser.write_file(args.output_file, args.handle_umlauts):
        print("Failed to write output file")
        return 1
    
    elapsed = time.time() - start_time
    print(f"Translation completed in {elapsed:.2f} seconds")
    
    # Instructions for next steps
    print("\nTranslation completed successfully!")
    print("Next steps:")
    print(f"1. Review the translated file: {args.output_file}")
    print(f"2. Use uw-strings-packer.py to pack the translated strings:")
    print(f"   python uw-strings-packer.py")
    print(f"   (Make sure to rename the original strings.pak before running the packer)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
