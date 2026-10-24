@echo off
rem Example: translate extracted strings to German. Run from the folder containing uw-strings.txt.
python "%~dp0uw-strings-translator.py" uw-strings.txt uw-strings-translated.txt --source English --target German --handle-umlauts ascii --backend transformers --batch-size 12 --chunk-size 96 --context --validate --max-ratio 5 --use-original-if-too-long --preserve-special-chars "_@"
