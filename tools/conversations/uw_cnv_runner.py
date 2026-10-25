#!/usr/bin/env python3
"""
Run an Ultima Underworld conversation in the terminal.

    python uw_cnv_runner.py conversation_0001.asm --strings uw-strings.txt
    python uw_cnv_runner.py conversation_0001.asm --set npc_attitude=3 --quest 5=1 --debug

This is the shared conversation VM from ../../uwscript/uwscript_vm.py (also
used for UWScript programs and by the fantasy console); run it with --help
for all options. Decompiled conversations from uw_cnv_decompiler.py keep
their memory slot count and import table, so they run like in the game.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uwscript'))

from uwscript_vm import UltimaUnderworldVM, VMError, load_program, main  # noqa: E402,F401

if __name__ == "__main__":
    sys.exit(main())
