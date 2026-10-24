@echo off
rem Compile a UWScript program and run it on the fantasy console.
rem Usage: start.bat path\to\program.uws
python "%~dp0..\uwscript\uwscript_compiler.py" -v -s uw-strings.txt -o output.asm %1 || exit /b 1
python "%~dp0fantasy_console.py" output.asm --strings uw-strings.txt
