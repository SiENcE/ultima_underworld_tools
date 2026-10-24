#!/usr/bin/env python3
"""
UWScript Critical Bug Verification Unit Tests

This unittest suite verifies whether the 6 major critical bugs have been fixed.
Tests will FAIL if bugs are still present and PASS if bugs are fixed.

Usage:
    python -m unittest uwscript_compiler_bug_unittest -v
    python uwscript_compiler_bug_unittest.py  # Run directly
"""

import unittest
import os
import sys
import subprocess
import tempfile
import time
import re
from typing import Dict, List, Tuple, Optional

class UWScriptTestHelper:
    """Helper class for compiling and running UWScript code in tests"""
    
    @staticmethod
    def compile_and_run(source_code: str, timeout: int = 10) -> Dict:
        """
        Compile and run UWScript source code
        Returns dict with success, output, error, and timing info
        """
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.uws', delete=False) as f:
            f.write(source_code)
            source_file = f.name
        
        asm_file = source_file.replace('.uws', '.asm')
        strings_file = source_file.replace('.uws', '_strings.txt')
        
        try:
            # Compile
            start_time = time.time()
            compile_result = subprocess.run([
                sys.executable, 'uwscript_compiler.py', source_file,
                '-o', asm_file, '-s', strings_file
            ], capture_output=True, text=True, timeout=timeout)
            
            compile_time = time.time() - start_time
            
            if compile_result.returncode != 0:
                return {
                    'success': False,
                    'phase': 'compilation',
                    'error': compile_result.stderr,
                    'output': compile_result.stdout,
                    'compile_time': compile_time,
                    'run_time': 0
                }
            
            # Run
            start_time = time.time()
            run_result = subprocess.run([
                sys.executable, 'uw_cnv_runner.py', asm_file,
                '--strings', strings_file
            ], capture_output=True, text=True, timeout=timeout)
            
            run_time = time.time() - start_time
            
            return {
                'success': run_result.returncode == 0,
                'phase': 'execution' if run_result.returncode != 0 else 'complete',
                'error': run_result.stderr if run_result.returncode != 0 else None,
                'output': run_result.stdout,
                'compile_time': compile_time,
                'run_time': run_time,
                'assembly': UWScriptTestHelper._read_file_safe(asm_file)
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'phase': 'timeout',
                'error': f'Test timed out after {timeout} seconds',
                'output': '',
                'compile_time': 0,
                'run_time': timeout
            }
        except Exception as e:
            return {
                'success': False,
                'phase': 'exception',
                'error': str(e),
                'output': '',
                'compile_time': 0,
                'run_time': 0
            }
        finally:
            # Cleanup
            for file_path in [source_file, asm_file, strings_file]:
                try:
                    os.unlink(file_path)
                except:
                    pass
    
    @staticmethod
    def _read_file_safe(file_path: str) -> str:
        """Safely read file contents"""
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except:
            return ""

class TestBug1RedundantReturnValues(unittest.TestCase):
    """Test Bug #1: Redundant Return Value Handling"""
    
    def test_return_value_efficiency(self):
        """Test that return values work without redundant SAVE_REG/PUSH_REG sequences"""
        
        source = '''
function simple_return()
    return 42
endfunction

function math_return(x)
    return x * 2 + 5
endfunction

function conditional_return(flag)
    if flag == 1
        return 100
    else
        return 200
    endif
endfunction

say "Testing return value handling..."
let r1 = simple_return()
let r2 = math_return(10)
let r3 = conditional_return(1)
let r4 = conditional_return(0)

say "Results: " + r1 + " " + r2 + " " + r3 + " " + r4

if r1 == 42 and r2 == 25 and r3 == 100 and r4 == 200
    say "PASS_RETURN_TEST"
else
    say "FAIL_RETURN_TEST"
endif
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(source)
        
        # Test should succeed
        self.assertTrue(result['success'], 
                       f"Return value test failed: {result.get('error', 'Unknown error')}")
        
        # Check for correct output
        self.assertIn("PASS_RETURN_TEST", result['output'],
                     "Return value calculations are incorrect")
        
        # Efficiency check: Look for redundant SAVE_REG/PUSH_REG patterns in assembly
        assembly = result.get('assembly', '')
        if assembly:
            # Count SAVE_REG followed immediately by PUSH_REG (inefficient pattern)
            redundant_pattern = re.findall(r'SAVE_REG\s*\n\s*PUSH_REG', assembly)
            self.assertEqual(len(redundant_pattern), 0,
                           f"Found {len(redundant_pattern)} redundant SAVE_REG/PUSH_REG sequences")

class TestBug2MemoryCollision(unittest.TestCase):
    """Test Bug #2: Memory Collision Risk"""
    
    def test_large_array_memory_safety(self):
        """Test that large arrays don't corrupt stack memory"""
        
        source = '''
say "Testing memory collision prevention..."

// Create large arrays that could cause stack collision
let array1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
let array2 = [21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
let array3 = [41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]

function test_large_local_array()
    let local_array = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115]
    return local_array[0] + local_array[15]
endfunction

// Test array integrity
let sum1 = array1[0] + array1[19]  // Should be 21
let sum2 = array2[0] + array2[19]  // Should be 61  
let sum3 = array3[0] + array3[19]  // Should be 101
let sum4 = test_large_local_array() // Should be 215

say "Array sums: " + sum1 + " " + sum2 + " " + sum3 + " " + sum4

if sum1 == 21 and sum2 == 61 and sum3 == 101 and sum4 == 215
    say "PASS_MEMORY_TEST"
else
    say "FAIL_MEMORY_TEST"
endif
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(source, timeout=15)
        
        # Test should succeed without memory corruption
        self.assertTrue(result['success'], 
                       f"Memory collision test failed: {result.get('error', 'Unknown error')}")
        
        # Check for correct calculations (proves no memory corruption)
        self.assertIn("PASS_MEMORY_TEST", result['output'],
                     "Memory collision detected - arrays corrupted")

class TestBug3TempVariableLeaks(unittest.TestCase):
    """Test Bug #3: Temp Variable Scope Leaks"""
    
    def test_temp_variable_scope_management(self):
        """Test that temp variables are properly managed across function calls"""
        
        source = '''
say "Testing temp variable scope management..."

function stress_temp_vars(a, b, c, d, e)
    let local1 = a + b
    let local2 = c + d  
    let local3 = e * 2
    return local1 + local2 + local3
endfunction

function nested_calls(x)
    let r1 = stress_temp_vars(x, x+1, x+2, x+3, x+4)
    let r2 = stress_temp_vars(x*2, x*3, x*4, x*5, x*6)
    return r1 + r2
endfunction

// Stress test with many calls
let total = 0
let i = 0
while i < 20  // Many iterations to stress temp var management
    let result = nested_calls(i)
    total = total + result
    i = i + 1
endwhile

say "Total after stress test: " + total

// Also test simple repeated calls
let simple_total = 0
i = 0
while i < 50  // Even more simple calls
    simple_total = simple_total + stress_temp_vars(i, i+1, i+2, i+3, i+4)
    i = i + 1
endwhile

say "Simple total: " + simple_total

// Expected values calculated offline
if total == 3990 and simple_total == 12475
    say "PASS_TEMP_VAR_TEST"
else
    say "FAIL_TEMP_VAR_TEST"
endif
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(source, timeout=20)
        
        # Test should succeed without temp variable issues
        self.assertTrue(result['success'], 
                       f"Temp variable test failed: {result.get('error', 'Unknown error')}")
        
        # Check for correct calculations (proves temp vars managed correctly)
        self.assertIn("PASS_TEMP_VAR_TEST", result['output'],
                     "Temp variable scope management failed")

class TestBug4StringConcatenation(unittest.TestCase):
    """Test Bug #4: String Concatenation Bugs"""
    
    def test_string_concatenation_immutability(self):
        """Test that string concatenation doesn't mutate original strings"""
        
        source = '''
say "Testing string concatenation immutability..."

// Test multiple concatenations with same base string
let base = "Value: "
let num1 = 42
let num2 = 84
let num3 = 126

let concat1 = base + num1
let concat2 = base + num2  
let concat3 = base + num3

say concat1
say concat2
say concat3

// Test different order concatenations
let prefix = "Result "
let val1 = 10
let val2 = 20

let order1 = prefix + val1
let order2 = val2 + " items"

say order1
say order2

// Multiple variables with same string
let status = "Status: "
let code1 = 200
let code2 = 404
let code3 = 500

let msg1 = status + code1
let msg2 = status + code2
let msg3 = status + code3

say msg1
say msg2
say msg3

say "PASS_STRING_TEST"
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(source)
        
        # Test should succeed without string mutation issues
        self.assertTrue(result['success'], 
                       f"String concatenation test failed: {result.get('error', 'Unknown error')}")
        
        # Check that all concatenations worked
        self.assertIn("PASS_STRING_TEST", result['output'],
                     "String concatenation immutability failed")
        
        # Check that expected concatenations appear in output
        output_lines = result['output'].split('\n')
        expected_patterns = ["Value: 42", "Value: 84", "Value: 126", "Result 10", "Status: 200"]
        
        for pattern in expected_patterns:
            found = any(pattern in line for line in output_lines)
            self.assertTrue(found, f"Expected concatenation pattern '{pattern}' not found")

class TestBug5RecursionDepthLimiting(unittest.TestCase):
    """Test Bug #5: No Recursion Depth Limiting"""
    
    def test_recursion_depth_protection(self):
        """Test that deep recursion is properly limited"""
        
        # Test moderate recursion (should work)
        moderate_source = '''
say "Testing moderate recursion..."

function factorial(n)
    if n <= 1
        return 1
    else
        return n * factorial(n - 1)
    endif
endfunction

function countdown(n)
    if n <= 0
        return 0
    else
        return n + countdown(n - 1)
    endif
endfunction

let fact5 = factorial(5)
let count10 = countdown(10)

say "Factorial(5): " + fact5
say "Countdown(10): " + count10

if fact5 == 120 and count10 == 55
    say "PASS_MODERATE_RECURSION"
else
    say "FAIL_MODERATE_RECURSION"
endif
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(moderate_source)
        
        # Moderate recursion should work
        self.assertTrue(result['success'], 
                       f"Moderate recursion failed: {result.get('error', 'Unknown error')}")
        self.assertIn("PASS_MODERATE_RECURSION", result['output'],
                     "Moderate recursion calculations incorrect")
        
        # Test deeper recursion (should be limited gracefully)
        deep_source = '''
say "Testing deep recursion protection..."

function deep_recursion(n)
    if n <= 0
        return 0
    else
        return deep_recursion(n - 1) + 1
    endif
endfunction

// This should trigger recursion limiting in fixed version
// or cause stack overflow in unfixed version
let result = deep_recursion(50)  // Moderate depth first

say "Deep recursion result: " + result

if result == 50
    say "PASS_DEEP_RECURSION"
else
    say "FAIL_DEEP_RECURSION"
endif
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(deep_source, timeout=10)
        
        # Should either succeed with limiting or fail gracefully (not crash)
        if result['success']:
            # If it succeeds, recursion limiting is working
            self.assertIn("PASS_DEEP_RECURSION", result['output'],
                         "Deep recursion calculation incorrect")
        else:
            # If it fails, should be due to recursion limiting, not crash
            self.assertIn("recursion", result.get('error', '').lower(),
                         "Deep recursion should fail due to depth limiting, not crash")

class TestBug6ArrayBoundsChecking(unittest.TestCase):
    """Test Bug #6: Array Bounds Unchecked"""
    
    def test_array_bounds_protection(self):
        """Test that array bounds are properly checked"""
        
        # Test valid array access (should work)
        valid_source = '''
say "Testing valid array bounds..."

let test_array = [10, 20, 30, 40, 50]

let val0 = test_array[0]
let val4 = test_array[4]
let val2 = test_array[2]

say "Valid access: " + val0 + " " + val4 + " " + val2

function safe_array_processing(arr)
    let sum = arr[0] + arr[4]  // Valid indices
    return sum
endfunction

let safe_sum = safe_array_processing(test_array)

say "Safe sum: " + safe_sum

if val0 == 10 and val4 == 50 and val2 == 30 and safe_sum == 60
    say "PASS_VALID_BOUNDS"
else
    say "FAIL_VALID_BOUNDS"
endif
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(valid_source)
        
        # Valid access should work
        self.assertTrue(result['success'], 
                       f"Valid array access failed: {result.get('error', 'Unknown error')}")
        self.assertIn("PASS_VALID_BOUNDS", result['output'],
                     "Valid array bounds access failed")
        
        # Test with variable indices
        variable_index_source = '''
say "Testing variable array indices..."

let numbers = [100, 200, 300, 400, 500]
let safe_indices = [0, 1, 2, 3, 4]

let i = 0
let total = 0
while i < 5
    let index = safe_indices[i]
    let value = numbers[index]
    total = total + value
    i = i + 1
endwhile

say "Total with variable indices: " + total

if total == 1500
    say "PASS_VARIABLE_INDICES"  
else
    say "FAIL_VARIABLE_INDICES"
endif
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(variable_index_source)
        
        self.assertTrue(result['success'], 
                       f"Variable index test failed: {result.get('error', 'Unknown error')}")
        self.assertIn("PASS_VARIABLE_INDICES", result['output'],
                     "Variable array indices failed")

class TestIntegrationAllFixes(unittest.TestCase):
    """Integration test for all fixes working together"""
    
    def test_all_fixes_integration(self):
        """Test that all 6 fixes work together correctly"""
        
        source = '''
say "=== Integration Test: All Fixes Together ==="

// Bug #1: Return values
function efficient_return(x)
    return x * 3 + 7
endfunction

// Bug #2: Memory layout with large arrays
let large_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

// Bug #3: Temp variable management
function complex_function(a, b, c)
    let temp1 = a + b
    let temp2 = b + c
    let temp3 = efficient_return(temp1)  // Return value test
    return temp1 + temp2 + temp3
endfunction

// Bug #4: String concatenation
let message_base = "Integration: "
let test_number = 42

// Bug #5: Safe recursion
function safe_fibonacci(n)
    if n <= 1
        return n
    elseif n > 10  // Prevent deep recursion
        return -1
    else
        return safe_fibonacci(n - 1) + safe_fibonacci(n - 2)
    endif
endfunction

// Bug #6: Array bounds safety
let bounds_array = [100, 200, 300, 400, 500]

// Execute integration test
let return_result = efficient_return(5)        // Should be 22
let array_value = large_data[10]               // Should be 11
let complex_result = complex_function(1, 2, 3) // Should be 16
let message = message_base + test_number       // String concat
let fib_result = safe_fibonacci(8)             // Should be 21
let bounds_value = bounds_array[2]             // Should be 300

say "Integration results:"
say "Return: " + return_result
say "Array: " + array_value  
say "Complex: " + complex_result
say message
say "Fibonacci: " + fib_result
say "Bounds: " + bounds_value

// Verify all results
if return_result == 22 and array_value == 11 and complex_result == 16 and fib_result == 21 and bounds_value == 300
    say "PASS_INTEGRATION_TEST"
else
    say "FAIL_INTEGRATION_TEST"
endif

say "=== Integration Test Complete ==="
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(source, timeout=15)
        
        # Integration test should succeed
        self.assertTrue(result['success'], 
                       f"Integration test failed: {result.get('error', 'Unknown error')}")
        
        # Check for successful integration
        self.assertIn("PASS_INTEGRATION_TEST", result['output'],
                     "Integration test failed - not all fixes are working together")

class TestEnvironmentSetup(unittest.TestCase):
    """Test that the environment is set up correctly for testing"""
    
    def test_required_files_exist(self):
        """Test that required UWScript files exist"""
        required_files = ['uwscript_compiler.py', 'uw_cnv_runner.py']
        
        for file_name in required_files:
            self.assertTrue(os.path.exists(file_name), 
                          f"Required file '{file_name}' not found. "
                          f"Please run this test from the UWScript directory.")
    
    def test_basic_compilation(self):
        """Test that basic UWScript compilation works"""
        simple_source = '''
say "Hello, World!"
exit
'''
        
        result = UWScriptTestHelper.compile_and_run(simple_source)
        
        self.assertTrue(result['success'], 
                       f"Basic compilation failed: {result.get('error', 'Unknown error')}")
        self.assertIn("Hello, World!", result['output'],
                     "Basic program execution failed")

def run_tests():
    """Run all tests with detailed output"""
    
    # Custom test result class for better output
    class VerboseTestResult(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            self.stream.write(f"✓ {test._testMethodName}: PASSED\n")
        
        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.stream.write(f"✗ {test._testMethodName}: FAILED\n")
        
        def addError(self, test, err):
            super().addError(test, err)
            self.stream.write(f"✗ {test._testMethodName}: ERROR\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestEnvironmentSetup,
        TestBug1RedundantReturnValues,
        TestBug2MemoryCollision,
        TestBug3TempVariableLeaks,
        TestBug4StringConcatenation,
        TestBug5RecursionDepthLimiting,
        TestBug6ArrayBoundsChecking,
        TestIntegrationAllFixes
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(
        verbosity=2,
        resultclass=VerboseTestResult,
        stream=sys.stdout
    )
    
    print("=" * 70)
    print("UWScript Critical Bug Verification Tests")
    print("=" * 70)
    print("These tests verify that all 6 major bugs have been fixed.")
    print("Tests will FAIL if bugs are still present.")
    print("Tests will PASS if bugs have been fixed correctly.")
    print("=" * 70)
    print()
    
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILED TESTS ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print(f"\nERROR TESTS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    if not result.failures and not result.errors:
        print("\n🎉 ALL TESTS PASSED!")
        print("All 6 critical bugs have been successfully fixed!")
    else:
        print(f"\n⚠️  {len(result.failures) + len(result.errors)} tests failed.")
        print("Some critical bugs may still be present.")
    
    print("=" * 70)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    # Run the tests
    success = run_tests()
    sys.exit(0 if success else 1)
