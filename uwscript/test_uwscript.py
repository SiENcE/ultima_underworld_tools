#!/usr/bin/env python3
"""
Tests for the UWScript compiler and VM.

    python -m unittest test_uwscript -v       (from the uwscript folder)
    python test_uwscript.py

Each test compiles a small program, runs it in the VM with scripted player
input and checks what the NPC says.
"""

import contextlib
import glob
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest

UWSCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, UWSCRIPT_DIR)

from uwscript_compiler import compile_uwscript, UWScriptError  # noqa: E402
from uwscript_vm import UltimaUnderworldVM, VMError  # noqa: E402


def run(source, inputs=(), quests=None):
    """Compile and run a program. Returns (said lines, full output, vm)."""
    result = compile_uwscript(source)
    vm = UltimaUnderworldVM()
    answers = list(inputs)
    def scripted_input(prompt=''):
        if not answers:
            raise EOFError
        return answers.pop(0)
    vm.input_func = scripted_input
    vm.quest_flags.update(quests or {})

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert vm.load_string_blocks_text(result['strings'])
        assert vm.parse_asm_text(result['assembly'])
        vm.initialize_memory()
        vm.execute()
    text = output.getvalue()
    said = re.findall(r'^NPC: "(.*?)"$', text, re.M | re.S)
    return said, text, vm


def says(source, **kwargs):
    return run(source, **kwargs)[0]


class TestFunctions(unittest.TestCase):

    def test_return_values(self):
        self.assertEqual(says('''
function seven()
    return 7
endfunction
function sub(a, b)
    return a - b
endfunction
say "" + seven() + " " + sub(10, 3)
'''), ["7 7"])

    def test_return_without_parameters_does_not_restart_program(self):
        self.assertEqual(says('''
say "start"
function f()
    return 1
endfunction
let x = f()
say "end " + x
'''), ["start", "end 1"])

    def test_parameter_order(self):
        self.assertEqual(says('''
function show(a, b, c)
    say "a=" + a + " b=" + b + " c=" + c
endfunction
show(1, 2, 3)
'''), ["a=1 b=2 c=3"])

    def test_globals_inside_functions(self):
        self.assertEqual(says('''
let counter = 5
function bump(n)
    counter = counter + n
    counter += 1
endfunction
bump(2)
say "counter " + counter
'''), ["counter 8"])

    def test_locals_do_not_overwrite_globals(self):
        self.assertEqual(says('''
let g = 42
function f()
    let tmp = 99
    let g = 1
endfunction
f()
say "g " + g
'''), ["g 42"])

    def test_large_local_array(self):
        self.assertEqual(says('''
function f()
    let arr = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
    return arr[0] + arr[19]
endfunction
say "sum " + f()
'''), ["sum 21"])

    def test_array_parameter(self):
        self.assertEqual(says('''
let data = [5, 6, 7]
function first_plus_second(arr)
    arr[1] += 10
    return arr[0] + arr[1]
endfunction
say "" + first_plus_second(data) + " " + data[1]
'''), ["21 16"])

    def test_recursion(self):
        self.assertEqual(says('''
function factorial(n)
    if n <= 1
        return 1
    else
        return n * factorial(n - 1)
    endif
endfunction
function depth(n)
    if n <= 0
        return 0
    endif
    return depth(n - 1) + 1
endfunction
say "" + factorial(5) + " " + depth(200)
'''), ["120 200"])

    def test_runaway_recursion_reports_stack_overflow(self):
        with self.assertRaises(VMError) as ctx:
            run('''
function forever(n)
    return forever(n + 1)
endfunction
forever(1)
''')
        self.assertIn("Stack overflow", str(ctx.exception))

    def test_nested_calls_and_temporaries(self):
        # Formerly expected 3990 / 12475 / 16, which were miscalculated
        said = says('''
function stress(a, b, c, d, e)
    let local1 = a + b
    let local2 = c + d
    let local3 = e * 2
    return local1 + local2 + local3
endfunction
function nested(x)
    let r1 = stress(x, x+1, x+2, x+3, x+4)
    let r2 = stress(x*2, x*3, x*4, x*5, x*6)
    return r1 + r2
endfunction
function efficient_return(x)
    return x * 3 + 7
endfunction
function complex(a, b, c)
    let t1 = a + b
    let t2 = b + c
    return t1 + t2 + efficient_return(t1)
endfunction
let total = 0
let i = 0
while i < 20
    total = total + nested(i)
    i += 1
endwhile
let simple = 0
i = 0
while i < 50
    simple = simple + stress(i, i+1, i+2, i+3, i+4)
    i += 1
endwhile
say "" + total + " " + simple + " " + complex(1, 2, 3)
''')
        self.assertEqual(said, ["6360 8050 24"])

    def test_return_value_does_not_use_redundant_register_moves(self):
        assembly = compile_uwscript('''
function f(x)
    return x * 2
endfunction
let r = f(1)
''')['assembly']
        self.assertNotRegex(assembly, r'SAVE_REG\s*\nPUSH_REG')


class TestStack(unittest.TestCase):

    def test_stack_is_balanced_in_loops(self):
        _, _, vm = run('''
let i = 0
while i < 10
    menu c ["A", "B"]
    filtermenu d ["X", 1, "Y", i > 3]
    set_quest(1, 2)
    ask answer
    let r = random(3) + get_quest(1)
    i += 1
endwhile
exit
''', inputs=['1', '1', 'text'] * 10)
        self.assertEqual(vm.stack_pointer, vm.stack_base)

    def test_function_called_as_statement_leaves_nothing_on_stack(self):
        _, _, vm = run('''
function f(a)
    return a
endfunction
let i = 0
while i < 50
    f(i)
    i += 1
endwhile
exit
''')
        self.assertEqual(vm.stack_pointer, vm.stack_base)


class TestBuiltins(unittest.TestCase):

    def test_quests(self):
        said, text, _ = run('''
set_quest(7, 3)
say "q7=" + get_quest(7) + " q5=" + get_quest(5)
''', quests={5: 1})
        self.assertEqual(said, ["q7=3 q5=1"])
        self.assertIn("Setting quest 7 to 3", text)

    def test_random_range(self):
        _, _, vm = run('''
let i = 0
let ok = 1
while i < 30
    let r = random(4)
    if r < 1 or r > 4
        ok = 0
    endif
    i += 1
endwhile
let one = random(1)
exit
''')
        self.assertEqual(vm.get_mem(96 + 1), 1)   # ok
        self.assertEqual(vm.get_mem(96 + 3), 1)   # one

    def test_string_builtins(self):
        self.assertEqual(says('''
ask name
say "You said: " + name
if contains(name, "world")
    say "contains"
endif
if compare(name, "HELLO WORLD")
    say "compare"
endif
say "length " + string_length(name)
''', inputs=['Hello World']), ["You said: Hello World", "contains", "compare", "length 11"])

    def test_string_equality_uses_compare(self):
        self.assertEqual(says('''
ask answer
if answer == "echo"
    say "right"
endif
if answer != "map"
    say "not map"
endif
''', inputs=['Echo']), ["right", "not map"])

    def test_arity_is_checked(self):
        with self.assertRaisesRegex(UWScriptError, "expects 2 argument"):
            compile_uwscript('set_quest(1)')
        with self.assertRaisesRegex(UWScriptError, "expects 2 argument"):
            compile_uwscript('function f(a, b)\nendfunction\nf(1)')


class TestDialogue(unittest.TestCase):

    def test_menu_with_first_string_as_option(self):
        said, text, _ = run('''
menu c ["Yes", "No"]
say "picked " + c
''', inputs=['2'])
        self.assertIn("1. Yes", text)
        self.assertEqual(said, ["picked 2"])

    def test_filtermenu_returns_position_in_full_list(self):
        said, text, _ = run('''
let gold = 20
filtermenu f [
    "Sword", gold >= 50,
    "Dagger", gold >= 10,
    "Leave", true
]
say "picked " + f
''', inputs=['2'])
        self.assertNotIn("Sword", text)
        self.assertEqual(said, ["picked 3"])

    def test_menu_options_with_values(self):
        said, text, _ = run('''
let gold = 7
menu c ["Pay " + gold + " gold", "Leave"]
''', inputs=['1'])
        self.assertIn("1. Pay 7 gold", text)

    def test_running_out_of_input_ends_conversation(self):
        said, text, vm = run('''
label top
menu c ["Again"]
goto top
''', inputs=['1', '1'])
        self.assertTrue(vm.finished)
        self.assertIn("(no more input)", text)


class TestStrings(unittest.TestCase):

    def test_literal_reused_after_concatenation(self):
        self.assertEqual(says('''
let n = 3
say "Count: "
say "Count: " + n
say "Count: "
'''), ["Count: ", "Count: 3", "Count: "])

    def test_chained_concatenation(self):
        self.assertEqual(says('''
let a = 1
let b = 2
let items = ["sword", "shield"]
say "a=" + a + " b=" + b + " sum=" + (a + b) + " n=" + 5 + " " + items[1] + "!"
say "Hello " + "World"
'''), ["a=1 b=2 sum=3 n=5 shield!", "Hello World"])

    def test_stored_strings_are_snapshots(self):
        self.assertEqual(says('''
let hp = 10
let msg = "HP: " + hp
hp = 0
say msg + " (now " + hp + ")"
let greeting = "Hello"
greeting += ", Avatar"
say greeting
'''), ["HP: 10 (now 0)", "Hello, Avatar"])

    def test_string_variables_and_parameters(self):
        self.assertEqual(says('''
let base = "Value: "
let num = 42
let concat = base + num
say concat
function greet(who, times)
    say "Hi " + who + " x" + times
endfunction
greet("Bob", 2)
function title(name)
    return "Sir " + name
endfunction
say title("Garamon")
'''), ["Value: 42", "Hi Bob x2", "Sir Garamon"])

    def test_newlines_in_strings(self):
        result = compile_uwscript('say "Line1\\nLine2 how 13"\nsay "Note: x"')
        for line in result['assembly'].splitlines():
            self.assertFalse(line.startswith('Line2'))
        self.assertEqual(says('say "Line1\\nLine2"'), ["Line1\nLine2"])

    def test_trailing_spaces_are_kept(self):
        self.assertEqual(says('say "a "\nsay " b"'), ["a ", " b"])


class TestOperators(unittest.TestCase):

    def test_logical_operators_are_boolean(self):
        self.assertEqual(says('''
let a = 1
let b = 2
if a and b
    say "and"
endif
if !0 and not (a == 2)
    say "not"
endif
if 0 or b
    say "or"
endif
'''), ["and", "not", "or"])

    def test_arithmetic(self):
        self.assertEqual(says('''
let x = 17
x %= 5
let y = -3 + 10 * 2 - 8 / 4
say "" + x + " " + y + " " + (7 % 3)
'''), ["2 15 1"])


class TestArrays(unittest.TestCase):

    def test_nested_arrays(self):
        self.assertEqual(says('''
let b = [[0, 1, 2], [3, 4, 5]]
let i = 1
b[i][0] += 10
say "" + b[1][2] + " " + b[i][1] + " " + b[1][0]
'''), ["5 4 13"])

    def test_constant_index_bounds(self):
        with self.assertRaisesRegex(UWScriptError, "out of bounds"):
            compile_uwscript('let a = [1, 2, 3]\nlet x = a[3]')

    def test_ragged_arrays_are_rejected(self):
        with self.assertRaisesRegex(UWScriptError, "same size"):
            compile_uwscript('let a = [[1, 2], [3]]')

    def test_variable_indices(self):
        self.assertEqual(says('''
let numbers = [100, 200, 300, 400, 500]
let order = [4, 3, 2, 1, 0]
let i = 0
let total = 0
while i < 5
    total = total + numbers[order[i]] * (i + 1)
    i += 1
endwhile
say "" + total
'''), ["3500"])


class TestErrors(unittest.TestCase):

    def assertCompileError(self, source, pattern):
        with self.assertRaisesRegex(UWScriptError, pattern):
            compile_uwscript(source)

    def test_missing_block_end(self):
        self.assertCompileError('if 1\n    say "x"\n', "Missing 'endif'")
        self.assertCompileError('while 1\n    say "x"\n', "Missing 'endwhile'")
        self.assertCompileError('function f()\n    say "x"\n', "Missing 'endfunction'")

    def test_stray_block_end(self):
        self.assertCompileError('say "x"\nendif\n', "without a matching")
        self.assertCompileError('if 1\nendwhile\nendif\n', "Unexpected 'endwhile'")

    def test_nested_function_definition(self):
        self.assertCompileError('if 1\n    function g()\n    endfunction\nendif\n', "top level")

    def test_return_outside_function(self):
        self.assertCompileError('return 1', "outside of a function")

    def test_syntax_error_messages_are_specific(self):
        self.assertCompileError('x = (1 + \n', "Unexpected end of line in expression")
        self.assertCompileError('say "a" "b"', 'after statement')
        self.assertCompileError('x\n', "assignment or a function call")

    def test_undefined_names(self):
        self.assertCompileError('x = 1', "not defined")
        self.assertCompileError('foo()', "not defined")
        self.assertCompileError('goto nowhere', "Label 'nowhere' is not defined")

    def test_unterminated_string(self):
        self.assertCompileError('say "abc\nsay "d"', "Unterminated string")

    def test_label_scopes(self):
        self.assertCompileError('label a\nfunction f()\n    goto a\nendfunction', "not defined in function")


class TestReviewFindings(unittest.TestCase):
    """Regressions found in review of the rewritten compiler."""

    def test_string_built_from_itself(self):
        self.assertEqual(says('''
let s = ""
let i = 0
while i < 3
    s += "x"
    i += 1
endwhile
say s
let t = "a"
t = t + "b"
t = t + "c"
say t
function wrap(n)
    if n == 0
        return "."
    endif
    return "<" + wrap(n - 1) + ">"
endfunction
say wrap(3)
'''), ["xxx", "abc", "<<<.>>>"])
        warnings = compile_uwscript('let s = ""\ns += "x"')['warnings']
        self.assertEqual(len(warnings), 1)

    def test_plain_stored_strings_stay_engine_compatible(self):
        result = compile_uwscript('let hp = 3\nlet msg = "HP: " + hp\nsay msg')
        self.assertEqual(result['warnings'], [])
        self.assertNotIn("CALLI 600", result['assembly'])

    def test_append_to_string_array_element(self):
        self.assertEqual(says('let a = ["x"]\na[0] += "y"\na[0] += "z"\nsay a[0]'), ["xyz"])

    def test_assigning_a_row_is_an_error(self):
        for source in ('let m = [[1,2],[3,4]]\nm[1] = 9', 'let m = [[1,2],[3,4]]\nm[1] += 5'):
            with self.assertRaisesRegex(UWScriptError, "whole row"):
                compile_uwscript(source)

    def test_same_label_in_different_scopes(self):
        self.assertEqual(says('''
let n = 0
label top
n += 1
function f()
    let i = 0
    label top
    i += 1
    if i < 3
        goto top
    endif
    return i
endfunction
function g()
    label top
    return 7
endfunction
if n < 2
    goto top
endif
say "" + n + " " + f() + " " + g()
'''), ["2 3 7"])

    def test_short_menu_with_variable_options(self):
        said, text, _ = run('''
let a = "Yes"
let b = "No"
menu a, b
menu c a, b
say "c=" + c
''', inputs=['1', '2'])
        self.assertIn("1. Yes", text)
        self.assertEqual(said, ["c=2"])

    def test_16_bit_arithmetic(self):
        self.assertEqual(says('''
let a = -7
say "" + (a / 2) + " " + (a % 2) + " " + (7 / -2) + " " + 300 * 300
let b = 65535
if b == -1
    say "wraps"
endif
'''), ["-3 -1 -3 24464", "wraps"])

    def test_header_text_inside_strings(self):
        self.assertEqual(says('say "a; String Block: 2"\nsay "b; Slot: 12"'),
                         ["a; String Block: 2", "b; Slot: 12"])

    def test_arithmetic_on_strings_is_an_error(self):
        with self.assertRaisesRegex(UWScriptError, "cannot be used with a string"):
            compile_uwscript('let x = 5\nsay "n=" + x - 1')
        self.assertEqual(says('let x = 5\nsay "n=" + (x - 1)'), ["n=4"])

    def test_menu_and_ask_in_functions_write_globals(self):
        self.assertEqual(says('''
let answer = 0
let name = "?"
function pick()
    menu answer ["a", "b"]
    ask name
endfunction
pick()
say "" + answer + " " + name
''', inputs=['2', 'Bob']), ["2 Bob"])


class TestSamplesAndCommandLine(unittest.TestCase):

    def test_all_samples_run(self):
        samples = sorted(glob.glob(os.path.join(UWSCRIPT_DIR, 'samples', '*.uws')))
        self.assertGreater(len(samples), 10)
        for path in samples:
            with self.subTest(sample=os.path.basename(path)):
                with open(path, encoding='utf-8') as f:
                    said, text, vm = run(f.read(), inputs=['1', 'mellon', '2', '1', '3'] * 4)
                self.assertTrue(said, "the sample said nothing")
                self.assertNotIn("Invalid string", text)
                self.assertNotIn("@", "".join(said), "unresolved text substitution")

    def test_selftest_passes(self):
        with open(os.path.join(UWSCRIPT_DIR, 'samples', 'selftest.uws'), encoding='utf-8') as f:
            said = says(f.read())
        self.assertIn("PASS: all self tests passed", said)

    def test_command_line_default_file_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'hello.uws')
            with open(source, 'w') as f:
                f.write('say "Hello, World!"\n')
            subprocess.run([sys.executable, os.path.join(UWSCRIPT_DIR, 'uwscript_compiler.py'), source],
                           check=True)
            self.assertTrue(os.path.exists(os.path.join(tmp, 'hello.asm')))
            self.assertTrue(os.path.exists(os.path.join(tmp, 'hello_strings.txt')))

            for program in ('hello.asm', 'hello.uws'):
                out = subprocess.run([sys.executable, os.path.join(UWSCRIPT_DIR, 'uwscript_vm.py'),
                                      os.path.join(tmp, program)], capture_output=True, text=True)
                self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
                self.assertIn('NPC: "Hello, World!"', out.stdout)

    def test_command_line_reports_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'bad.uws')
            with open(source, 'w') as f:
                f.write('if 1\n')
            out = subprocess.run([sys.executable, os.path.join(UWSCRIPT_DIR, 'uwscript_compiler.py'), source],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 1)
            self.assertIn("Missing 'endif'", out.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
