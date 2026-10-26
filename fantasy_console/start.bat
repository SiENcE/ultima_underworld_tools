@echo off
rem Compile a UWScript program and run it on the fantasy console.
rem Usage: start.bat path\to\program.uws
rem The compiled files are written next to the program (program.asm, program_strings.txt).
python "%~dp0..\uwscript\uwscript_compiler.py" --target console -v %1 || exit /b 1
python "%~dp0fantasy_console.py" "%~dpn1.asm"
