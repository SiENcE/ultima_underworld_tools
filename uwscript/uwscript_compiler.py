#!/usr/bin/env python3
"""
Enhanced UWScript Compiler - Fixed Function Parameter Passing

Key improvements:
1. Proper stack frame setup for user-defined functions
2. Parameter binding to negative offsets from base pointer
3. Separate variable scopes for functions vs global scope
4. Correct stack cleanup on function return
"""

import sys
import re
import os
import argparse
from enum import Enum, auto
from typing import List, Dict, Tuple, Set, Optional, Union, Any

class TokenType(Enum):
    """Token types for the lexer"""
    KEYWORD = auto()
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    OPERATOR = auto()
    PUNCTUATION = auto()
    COMMENT = auto()
    EOL = auto()  # End of line
    EOF = auto()  # End of file

class Token:
    """Represents a token in the source code"""
    def __init__(self, type: TokenType, value: str, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column
    
    def __repr__(self):
        return f"Token({self.type}, '{self.value}', line={self.line}, col={self.column})"

class Lexer:
    """Tokenizes UWScript source code"""
    
    # Keywords in the language
    KEYWORDS = {
        # Control flow
        'if', 'else', 'elseif', 'endif', 'goto', 'label', 'exit',
        
        # Functions
        'function', 'endfunction', 'return',
        
        # Variables and values
        'let', 'true', 'false',
        
        # Dialogue
        'say', 'ask', 'menu', 'filtermenu',

        # Operators
        'and', 'or', 'not',
        
        # Loops
        'while', 'endwhile',
    }
    
    # Operators
    OPERATORS = {
        '+', '-', '*', '/', '%', '=', '==', '!=', '>', '<', '>=', '<=', '+=', '-=', '*=', '/=', '!'
    }
    
    # Punctuation
    PUNCTUATION = {
        '(', ')', '{', '}', '[', ']', ',', ':', ';', '"'
    }
    
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []
    
    def tokenize(self) -> List[Token]:
        """Convert the source code to a list of tokens"""
        while self.pos < len(self.source):
            char = self.source[self.pos]
            
            # Skip whitespace
            if char.isspace():
                if char == '\n':
                    self.tokens.append(Token(TokenType.EOL, '\n', self.line, self.column))
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.pos += 1
                continue
            
            # Comments
            if char == '/' and self.pos + 1 < len(self.source) and self.source[self.pos+1] == '/':
                self._tokenize_comment()
                continue
            
            # Identifiers and keywords
            if char.isalpha() or char == '_':
                self._tokenize_identifier()
                continue
            
            # Numbers
            if char.isdigit():
                self._tokenize_number()
                continue
            
            # Strings
            if char == '"':
                self._tokenize_string()
                continue
            
            # Operators and punctuation
            if char in self.OPERATORS or char in self.PUNCTUATION:
                self._tokenize_operator_or_punctuation()
                continue
            
            # Unknown character
            self._error(f"Unexpected character: '{char}'")
        
        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, '', self.line, self.column))
        
        return self.tokens
    
    def _tokenize_comment(self):
        """Tokenize a comment"""
        comment = ''
        start_column = self.column
        
        # Skip the // characters
        self.pos += 2
        self.column += 2
        
        # Consume until end of line
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            comment += self.source[self.pos]
            self.pos += 1
            self.column += 1
        
        self.tokens.append(Token(TokenType.COMMENT, comment, self.line, start_column))
    
    def _tokenize_identifier(self):
        """Tokenize an identifier or keyword"""
        identifier = ''
        start_column = self.column
        
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            identifier += self.source[self.pos]
            self.pos += 1
            self.column += 1
        
        # Check if it's a keyword
        if identifier in self.KEYWORDS:
            self.tokens.append(Token(TokenType.KEYWORD, identifier, self.line, start_column))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, identifier, self.line, start_column))
    
    def _tokenize_number(self):
        """Tokenize a number"""
        number = ''
        start_column = self.column
        
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            number += self.source[self.pos]
            self.pos += 1
            self.column += 1
        
        self.tokens.append(Token(TokenType.NUMBER, number, self.line, start_column))
    
    def _tokenize_string(self):
        """Tokenize a string"""
        string = ''
        start_column = self.column
        
        # Skip the opening quote
        self.pos += 1
        self.column += 1
        
        # Consume until closing quote
        while self.pos < len(self.source) and self.source[self.pos] != '"':
            # Handle escape sequences
            if self.source[self.pos] == '\\' and self.pos + 1 < len(self.source):
                self.pos += 1
                self.column += 1
                
                if self.source[self.pos] == 'n':
                    string += '\n'
                elif self.source[self.pos] == 't':
                    string += '\t'
                elif self.source[self.pos] == '"':
                    string += '"'
                elif self.source[self.pos] == '\\':
                    string += '\\'
                else:
                    string += '\\' + self.source[self.pos]
            else:
                string += self.source[self.pos]
            
            self.pos += 1
            self.column += 1
        
        # Skip the closing quote
        if self.pos < len(self.source) and self.source[self.pos] == '"':
            self.pos += 1
            self.column += 1
        else:
            self._error("Unterminated string")
        
        self.tokens.append(Token(TokenType.STRING, string, self.line, start_column))
    
    def _tokenize_operator_or_punctuation(self):
        """Tokenize an operator or punctuation"""
        char = self.source[self.pos]
        start_column = self.column
        
        # Check for two-character operators
        if self.pos + 1 < len(self.source):
            two_chars = char + self.source[self.pos+1]
            if two_chars in self.OPERATORS:
                self.tokens.append(Token(TokenType.OPERATOR, two_chars, self.line, start_column))
                self.pos += 2
                self.column += 2
                return
        
        # Single-character operator or punctuation
        if char in self.OPERATORS:
            self.tokens.append(Token(TokenType.OPERATOR, char, self.line, start_column))
        else:  # Must be punctuation
            self.tokens.append(Token(TokenType.PUNCTUATION, char, self.line, start_column))
        
        self.pos += 1
        self.column += 1
    
    def _error(self, message: str):
        """Raise a syntax error"""
        raise SyntaxError(f"Line {self.line}, column {self.column}: {message}")

class ASTNode:
    """Base class for all AST nodes"""
    def __init__(self, token: Optional[Token] = None):
        self.token = token
        self.children = []
    
    def add_child(self, child):
        """Add a child node"""
        self.children.append(child)
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.token})"

# AST node types for various constructs
class Program(ASTNode): pass
class Statement(ASTNode): pass
class Expression(ASTNode): pass
class BinaryOperation(Expression): pass
class UnaryOperation(Expression): pass
class Literal(Expression): pass
class Identifier(Expression): pass
class ArrayLiteral(Expression): pass
class ArrayAccess(Expression): pass
class VariableDeclaration(Statement): pass
class Assignment(Statement): pass
class IfStatement(Statement): pass
class WhileStatement(Statement): pass
class FunctionDefinition(Statement): pass
class FunctionCall(Expression): pass
class ReturnStatement(Statement): pass
class SayStatement(Statement): pass
class AskStatement(Statement): pass
class MenuStatement(Statement): pass
class FilterMenuStatement(Statement): pass
class GotoStatement(Statement): pass
class LabelStatement(Statement): pass
class ExitStatement(Statement): pass

class Parser:
    """Parses a list of tokens into an AST"""
    
    def __init__(self, tokens: List[Token], debug: bool = False):
        self.tokens = tokens
        self.pos = 0
        self.debug = debug
    
    def parse(self) -> Program:
        """Parse the tokens into an AST"""
        program = Program()
        
        while self.pos < len(self.tokens) and self.tokens[self.pos].type != TokenType.EOF:
            # Skip EOL tokens
            if self.tokens[self.pos].type == TokenType.EOL:
                self.pos += 1
                continue
            
            statement = self._parse_statement()
            if statement:
                program.add_child(statement)
        
        return program
    
    def _peek(self) -> Token:
        """Return the next token without consuming it"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, '', -1, -1)
    
    def _consume(self) -> Token:
        """Consume and return the next token"""
        token = self._peek()
        self.pos += 1
        return token
    
    def _match(self, type: TokenType, value: Optional[str] = None) -> bool:
        """Check if the next token matches the given type and value"""
        if self.pos >= len(self.tokens):
            return False
        
        if self.tokens[self.pos].type != type:
            return False
        
        if value is not None and self.tokens[self.pos].value != value:
            return False
        
        return True
    
    def _expect(self, type: TokenType, value: Optional[str] = None) -> Token:
        """Expect a token of given type and value, skip comments, raise error if not found"""
        # Skip any comments
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == TokenType.COMMENT:
            self._consume()
        
        if not self._match(type, value):
            expected = value if value else type.name
            got = self.tokens[self.pos].value if self.pos < len(self.tokens) else "EOF"
            line = self.tokens[self.pos].line if self.pos < len(self.tokens) else "unknown"
            column = self.tokens[self.pos].column if self.pos < len(self.tokens) else "unknown"
            raise SyntaxError(f"Line {line}, column {column}: Expected {expected}, got '{got}'")
        
        return self._consume()
    
    def _parse_statement(self):
        """Parse a statement"""
        # Skip comments and EOL tokens at the beginning of statements
        while self._match(TokenType.COMMENT) or self._match(TokenType.EOL):
            self._consume()
        
        # Check for end of file
        if self._match(TokenType.EOF):
            return None
        
        # Check statement type
        token = self._peek()
        
        if token.type == TokenType.KEYWORD:
            if token.value == 'let':
                return self._parse_variable_declaration()
            elif token.value == 'if':
                return self._parse_if_statement()
            elif token.value == 'while':
                return self._parse_while_statement()
            elif token.value == 'function':
                return self._parse_function_definition()
            elif token.value == 'return':
                return self._parse_return_statement()
            elif token.value == 'say':
                return self._parse_say_statement()
            elif token.value == 'ask':
                return self._parse_ask_statement()
            elif token.value == 'menu':
                return self._parse_menu_statement()
            elif token.value == 'filtermenu':
                return self._parse_filtermenu_statement()
            elif token.value == 'goto':
                return self._parse_goto_statement()
            elif token.value == 'label':
                return self._parse_label_statement()
            elif token.value == 'exit':
                return self._parse_exit_statement()
            # CRITICAL: These keywords signal end of current parsing context
            elif token.value in ['endif', 'else', 'elseif', 'endwhile', 'endfunction']:
                # Don't consume - let parent parser handle these
                return None
            else:
                self._error(f"Unexpected keyword: {token.value}")
        
        # Assignment or function call
        if token.type == TokenType.IDENTIFIER:
            # Look ahead to see if this is an assignment or array assignment
            saved_pos = self.pos
            
            try:
                # Try to parse as assignment first
                if self.pos + 1 < len(self.tokens):
                    next_token = self.tokens[self.pos + 1]
                    if next_token.type == TokenType.OPERATOR and next_token.value in ['=', '+=', '-=', '*=', '/=']:
                        return self._parse_assignment()
                    elif next_token.type == TokenType.PUNCTUATION and next_token.value == '[':
                        # Could be array assignment like: arr[index] = value
                        return self._parse_assignment()
                
                # Function call or variable reference
                expr = self._parse_expression()
                if self._match(TokenType.EOL):
                    self._consume()
                return expr
                
            except:
                # Reset position and try again
                self.pos = saved_pos
                self._error(f"Could not parse statement starting with: {token.value}")
        
        if token.type == TokenType.EOF:
            return None
            
        self._error(f"Unexpected token: {token.value}")
    
    def _parse_variable_declaration(self) -> VariableDeclaration:
        """Parse a variable declaration"""
        # Consume 'let'
        let_token = self._expect(TokenType.KEYWORD, 'let')
        
        # Variable name
        name_token = self._expect(TokenType.IDENTIFIER)
        
        # Expect '='
        self._expect(TokenType.OPERATOR, '=')
        
        # Parse the value expression
        value = self._parse_expression()
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = VariableDeclaration(let_token)
        node.name = name_token.value
        node.add_child(value)
        
        return node
    
    def _parse_assignment(self) -> Assignment:
        """Parse an assignment statement (including array assignments)"""
        # Variable name or array access
        target = self._parse_postfix()
        
        # Operator
        op_token = self._consume()  # This should be '=', '+=', etc.
        
        # Parse the value expression
        value = self._parse_expression()
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = Assignment(op_token)
        node.target = target  # This could be an Identifier or ArrayAccess
        node.operator = op_token.value
        node.add_child(value)
        
        return node
    
    def _parse_if_statement(self) -> IfStatement:
        """Parse an if statement with support for multiple elseif clauses"""
        # Consume 'if'
        if_token = self._expect(TokenType.KEYWORD, 'if')
        
        # Parse condition
        condition = self._parse_expression()
        
        # Expect EOL
        self._expect(TokenType.EOL)
        
        # Create the root node
        root_node = IfStatement(if_token)
        root_node.condition = condition
        root_node.true_branch = []
        root_node.false_branch = []
        
        # Parse the true branch
        while (self.pos < len(self.tokens) and
               not self._match(TokenType.KEYWORD, 'endif') and
               not self._match(TokenType.KEYWORD, 'else') and
               not self._match(TokenType.KEYWORD, 'elseif')):
            
            statement = self._parse_statement()
            if statement:
                root_node.true_branch.append(statement)
        
        # Keep track of the current node for chaining elseifs
        current_node = root_node
        
        # Handle multiple elseif clauses
        while self._match(TokenType.KEYWORD, 'elseif'):
            # Consume 'elseif'
            elseif_token = self._consume()
            elseif_condition = self._parse_expression()
            self._expect(TokenType.EOL)
            
            # Create a new if node for this elseif
            elseif_node = IfStatement(elseif_token)
            elseif_node.condition = elseif_condition
            elseif_node.true_branch = []
            elseif_node.false_branch = []
            
            # Parse the elseif true branch
            while (self.pos < len(self.tokens) and
                   not self._match(TokenType.KEYWORD, 'endif') and
                   not self._match(TokenType.KEYWORD, 'else') and
                   not self._match(TokenType.KEYWORD, 'elseif')):
                
                statement = self._parse_statement()
                if statement:
                    elseif_node.true_branch.append(statement)
            
            # Chain this elseif as the false branch of the current node
            current_node.false_branch.append(elseif_node)
            
            # Update current node for potential next elseif
            current_node = elseif_node
        
        # Handle final else clause (if present)
        if self._match(TokenType.KEYWORD, 'else'):
            self._consume()
            self._expect(TokenType.EOL)
            
            # Parse the else branch and add it to the last node's false branch
            while (self.pos < len(self.tokens) and
                   not self._match(TokenType.KEYWORD, 'endif')):
                
                statement = self._parse_statement()
                if statement:
                    current_node.false_branch.append(statement)
        
        # Expect 'endif'
        self._expect(TokenType.KEYWORD, 'endif')
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        return root_node
    
    def _parse_while_statement(self) -> WhileStatement:
        """Parse a while statement"""
        # Consume 'while'
        while_token = self._expect(TokenType.KEYWORD, 'while')
        
        # Parse condition
        condition = self._parse_expression()
        
        # Expect EOL
        self._expect(TokenType.EOL)
        
        # Create the node
        node = WhileStatement(while_token)
        node.condition = condition
        node.body = []
        
        # Parse the body
        while (self.pos < len(self.tokens) and
               not self._match(TokenType.KEYWORD, 'endwhile')):
            
            statement = self._parse_statement()
            if statement:
                node.body.append(statement)
        
        # Expect 'endwhile'
        self._expect(TokenType.KEYWORD, 'endwhile')
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        return node
    
    def _parse_function_definition(self) -> FunctionDefinition:
        """Parse a function definition"""
        # Consume 'function'
        function_token = self._expect(TokenType.KEYWORD, 'function')
        
        # Function name
        name_token = self._expect(TokenType.IDENTIFIER)
        
        # Parameters
        parameters = []
        
        # Expect '('
        self._expect(TokenType.PUNCTUATION, '(')
        
        # Parse parameters (if any)
        if not self._match(TokenType.PUNCTUATION, ')'):
            while True:
                param_name = self._expect(TokenType.IDENTIFIER)
                parameters.append(param_name.value)
                
                if not self._match(TokenType.PUNCTUATION, ','):
                    break
                
                self._consume()  # Consume the comma
        
        # Expect ')'
        self._expect(TokenType.PUNCTUATION, ')')
        
        # Expect EOL
        self._expect(TokenType.EOL)
        
        # Create the node
        node = FunctionDefinition(function_token)
        node.name = name_token.value
        node.parameters = parameters
        node.body = []
        
        # Debug output
        if hasattr(self, 'debug') and self.debug:
            print(f"Parsing function '{node.name}' body...")
        
        # Parse the body statements
        while self.pos < len(self.tokens):
            # Check for end of function
            if self._match(TokenType.KEYWORD, 'endfunction'):
                break
                
            # Check for EOF
            if self._match(TokenType.EOF):
                current_token = self._peek()
                raise SyntaxError(f"Missing 'endfunction' for function '{node.name}' started at line {function_token.line}")
            
            # Skip comments and empty lines
            if self._match(TokenType.COMMENT) or self._match(TokenType.EOL):
                self._consume()
                continue
            
            # Parse the statement
            statement = self._parse_statement()
            if statement:
                node.body.append(statement)
                if hasattr(self, 'debug') and self.debug:
                    print(f"  Added statement: {type(statement).__name__}")
        
        # Consume 'endfunction'
        self._expect(TokenType.KEYWORD, 'endfunction')
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        if hasattr(self, 'debug') and self.debug:
            print(f"Function '{node.name}' parsed successfully with {len(node.body)} statements")
        
        return node
    
    def _parse_return_statement(self) -> ReturnStatement:
        """Parse a return statement"""
        # Consume 'return'
        return_token = self._expect(TokenType.KEYWORD, 'return')
        
        # Create the node
        node = ReturnStatement(return_token)
        
        # Parse return value (if any)
        if not self._match(TokenType.EOL):
            value = self._parse_expression()
            node.add_child(value)
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        return node
    
    def _parse_say_statement(self) -> SayStatement:
        """Parse a say statement"""
        # Consume 'say'
        say_token = self._expect(TokenType.KEYWORD, 'say')
        
        # Parse the expression
        expr = self._parse_expression()
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = SayStatement(say_token)
        node.add_child(expr)
        
        return node
    
    def _parse_ask_statement(self) -> AskStatement:
        """Parse an ask statement"""
        # Consume 'ask'
        ask_token = self._expect(TokenType.KEYWORD, 'ask')
        
        # Variable to store the result
        if self._match(TokenType.IDENTIFIER):
            var_name = self._consume().value
        else:
            var_name = None
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = AskStatement(ask_token)
        node.variable = var_name
        
        return node
    
    def _parse_menu_statement(self) -> MenuStatement:
        """Parse a menu statement"""
        # Consume 'menu'
        menu_token = self._expect(TokenType.KEYWORD, 'menu')
        
        # Variable to store the result
        var_name = None
        if self._match(TokenType.IDENTIFIER):
            var_name = self._consume().value
        
        # Parse menu items - accept both list and direct string formats
        items = []
        
        # Check for list format with brackets
        if self._match(TokenType.PUNCTUATION, '['):
            self._consume()  # Consume '['
            
            # Skip any EOL tokens after the opening bracket
            while self._match(TokenType.EOL):
                self._consume()
            
            while not self._match(TokenType.PUNCTUATION, ']'):
                # Skip any leading EOL tokens before each item
                while self._match(TokenType.EOL):
                    self._consume()
                
                # Check if we've reached the end bracket after skipping EOLs
                if self._match(TokenType.PUNCTUATION, ']'):
                    break
                
                # Parse one menu item
                item = self._parse_expression()
                items.append(item)
                
                # Expect comma or end of list
                if self._match(TokenType.PUNCTUATION, ','):
                    self._consume()
                    # Skip any EOL tokens after the comma
                    while self._match(TokenType.EOL):
                        self._consume()
                else:
                    # Skip any trailing EOL tokens before the closing bracket
                    while self._match(TokenType.EOL):
                        self._consume()
                    break
            
            # Expect ']'
            self._expect(TokenType.PUNCTUATION, ']')
        
        # Check for comma-separated format
        else:
            # Parse first item
            item = self._parse_expression()
            items.append(item)
            
            # Parse additional items
            while self._match(TokenType.PUNCTUATION, ','):
                self._consume()  # Consume comma
                item = self._parse_expression()
                items.append(item)
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = MenuStatement(menu_token)
        node.variable = var_name
        node.items = items
        
        return node
    
    def _parse_filtermenu_statement(self) -> FilterMenuStatement:
        """Parse a filtermenu statement"""
        # Consume 'filtermenu'
        menu_token = self._expect(TokenType.KEYWORD, 'filtermenu')
        
        # Variable to store the result
        var_name = None
        if self._match(TokenType.IDENTIFIER):
            var_name = self._consume().value
        
        # Expect '['
        self._expect(TokenType.PUNCTUATION, '[')
        
        # Skip any EOL tokens after the opening bracket
        while self._match(TokenType.EOL):
            self._consume()
        
        # Parse menu items
        items = []
        flags = []
        
        while not self._match(TokenType.PUNCTUATION, ']'):
            # Skip any leading EOL tokens before each item
            while self._match(TokenType.EOL):
                self._consume()
            
            # Check if we've reached the end bracket after skipping EOLs
            if self._match(TokenType.PUNCTUATION, ']'):
                break
            
            # Parse one menu item
            item = self._parse_expression()
            items.append(item)
            
            # Expect comma
            self._expect(TokenType.PUNCTUATION, ',')
            
            # Skip any EOL tokens after the comma
            while self._match(TokenType.EOL):
                self._consume()
            
            # Parse the flag expression
            flag = self._parse_expression()
            flags.append(flag)
            
            # Expect comma or end of list
            if self._match(TokenType.PUNCTUATION, ','):
                self._consume()
                # Skip any EOL tokens after the comma
                while self._match(TokenType.EOL):
                    self._consume()
            else:
                # Skip any trailing EOL tokens before the closing bracket
                while self._match(TokenType.EOL):
                    self._consume()
                break
        
        # Expect ']'
        self._expect(TokenType.PUNCTUATION, ']')
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = FilterMenuStatement(menu_token)
        node.variable = var_name
        node.items = items
        node.flags = flags
        
        return node
        
    def _parse_goto_statement(self) -> GotoStatement:
        """Parse a goto statement"""
        # Consume 'goto'
        goto_token = self._expect(TokenType.KEYWORD, 'goto')
        
        # Label name
        label_token = self._expect(TokenType.IDENTIFIER)
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = GotoStatement(goto_token)
        node.label = label_token.value
        
        return node
    
    def _parse_label_statement(self) -> LabelStatement:
        """Parse a label statement"""
        # Consume 'label'
        label_token = self._expect(TokenType.KEYWORD, 'label')
        
        # Label name
        name_token = self._expect(TokenType.IDENTIFIER)
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        node = LabelStatement(label_token)
        node.name = name_token.value
        
        return node
    
    def _parse_exit_statement(self) -> ExitStatement:
        """Parse an exit statement"""
        # Consume 'exit'
        exit_token = self._expect(TokenType.KEYWORD, 'exit')
        
        # Expect EOL
        if self._match(TokenType.EOL):
            self._consume()
        
        return ExitStatement(exit_token)
    
    def _parse_expression(self) -> Expression:
        """Parse an expression"""
        return self._parse_logical_or()
    
    def _parse_logical_or(self) -> Expression:
        """Parse a logical OR expression"""
        left = self._parse_logical_and()
        
        while self._match(TokenType.KEYWORD, 'or'):
            op_token = self._consume()
            right = self._parse_logical_and()
            
            node = BinaryOperation(op_token)
            node.left = left
            node.right = right
            left = node
        
        return left
    
    def _parse_logical_and(self) -> Expression:
        """Parse a logical AND expression"""
        left = self._parse_equality()
        
        while self._match(TokenType.KEYWORD, 'and'):
            op_token = self._consume()
            right = self._parse_equality()
            
            node = BinaryOperation(op_token)
            node.left = left
            node.right = right
            left = node
        
        return left
    
    def _parse_equality(self) -> Expression:
        """Parse an equality expression"""
        left = self._parse_comparison()
        
        while self._match(TokenType.OPERATOR, '==') or self._match(TokenType.OPERATOR, '!='):
            op_token = self._consume()
            right = self._parse_comparison()
            
            node = BinaryOperation(op_token)
            node.left = left
            node.right = right
            left = node
        
        return left
    
    def _parse_comparison(self) -> Expression:
        """Parse a comparison expression"""
        left = self._parse_additive()
        
        while (self._match(TokenType.OPERATOR, '<') or 
               self._match(TokenType.OPERATOR, '>') or 
               self._match(TokenType.OPERATOR, '<=') or 
               self._match(TokenType.OPERATOR, '>=')):
            op_token = self._consume()
            right = self._parse_additive()
            
            node = BinaryOperation(op_token)
            node.left = left
            node.right = right
            left = node
        
        return left
    
    def _parse_additive(self) -> Expression:
        """Parse an additive expression"""
        left = self._parse_multiplicative()
        
        while self._match(TokenType.OPERATOR, '+') or self._match(TokenType.OPERATOR, '-'):
            op_token = self._consume()
            right = self._parse_multiplicative()
            
            node = BinaryOperation(op_token)
            node.left = left
            node.right = right
            left = node
        
        return left
    
    def _parse_multiplicative(self) -> Expression:
        """Parse a multiplicative expression"""
        left = self._parse_unary()
        
        while (self._match(TokenType.OPERATOR, '*') or 
               self._match(TokenType.OPERATOR, '/') or 
               self._match(TokenType.OPERATOR, '%')):
            op_token = self._consume()
            right = self._parse_unary()
            
            node = BinaryOperation(op_token)
            node.left = left
            node.right = right
            left = node
        
        return left
    
    def _parse_unary(self) -> Expression:
        """Parse a unary expression"""
        if self._match(TokenType.OPERATOR, '-') or self._match(TokenType.KEYWORD, 'not'):
            op_token = self._consume()
            right = self._parse_unary()
            
            node = UnaryOperation(op_token)
            node.operand = right
            return node
        
        return self._parse_postfix()
    
    def _parse_postfix(self) -> Expression:
        """Parse postfix expressions (array access, function calls)"""
        left = self._parse_primary()
        
        while True:
            if self._match(TokenType.PUNCTUATION, '['):
                # Array access
                self._consume()  # Consume '['
                index = self._parse_expression()
                self._expect(TokenType.PUNCTUATION, ']')
                
                node = ArrayAccess()
                node.array = left
                node.index = index
                left = node
                
            elif self._match(TokenType.PUNCTUATION, '('):
                # Function call
                self._consume()  # Consume '('
                
                if isinstance(left, Identifier):
                    node = FunctionCall()
                    node.name = left.name
                    node.arguments = []
                    
                    # Skip any EOL tokens or comments after the opening parenthesis
                    while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
                        self._consume()
                    
                    # Parse arguments (if any)
                    if not self._match(TokenType.PUNCTUATION, ')'):
                        while True:
                            # Skip any leading EOL tokens or comments before each argument
                            while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
                                self._consume()
                            
                            # Check if we've reached the end parenthesis after skipping EOLs/comments
                            if self._match(TokenType.PUNCTUATION, ')'):
                                break
                            
                            # Parse one argument
                            arg = self._parse_expression()
                            node.arguments.append(arg)
                            
                            # Expect comma or end of arguments
                            if self._match(TokenType.PUNCTUATION, ','):
                                self._consume()  # Consume the comma
                                # Skip any EOL tokens or comments after the comma
                                while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
                                    self._consume()
                            else:
                                # Skip any trailing EOL tokens or comments before the closing parenthesis
                                while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
                                    self._consume()
                                break
                    
                    # Expect ')'
                    self._expect(TokenType.PUNCTUATION, ')')
                    
                    left = node
                else:
                    self._error("Only identifiers can be called as functions")
            else:
                break
        
        return left
    
    def _parse_primary(self) -> Expression:
        """Parse a primary expression"""
        token = self._peek()
        
        if token.type == TokenType.NUMBER:
            # Number literal
            token = self._consume()
            node = Literal(token)
            node.value = int(token.value)
            return node
        
        elif token.type == TokenType.STRING:
            # String literal
            token = self._consume()
            node = Literal(token)
            node.value = token.value
            return node
        
        elif token.type == TokenType.KEYWORD and token.value in ['true', 'false']:
            # Boolean literal
            token = self._consume()
            node = Literal(token)
            node.value = token.value == 'true'
            return node
        
        elif token.type == TokenType.IDENTIFIER:
            # Variable reference
            token = self._consume()
            node = Identifier(token)
            node.name = token.value
            return node
        
        elif token.type == TokenType.PUNCTUATION and token.value == '(':
            # Parenthesized expression
            self._consume()  # Consume '('
            expr = self._parse_expression()
            self._expect(TokenType.PUNCTUATION, ')')
            return expr
        
        elif token.type == TokenType.PUNCTUATION and token.value == '[':
            # Array literal
            return self._parse_array_literal()
        
        self._error(f"Unexpected token in expression: {token.value}")
    
    def _parse_array_literal(self) -> ArrayLiteral:
        """Parse an array literal [1, 2, 3, 4]"""
        bracket_token = self._expect(TokenType.PUNCTUATION, '[')
        
        node = ArrayLiteral(bracket_token)
        node.elements = []
        
        # Skip any EOL tokens or comments after the opening bracket
        while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
            self._consume()
        
        # Parse array elements
        if not self._match(TokenType.PUNCTUATION, ']'):
            while True:
                # Skip any leading EOL tokens or comments before each element
                while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
                    self._consume()
                
                # Check if we've reached the end bracket after skipping EOLs/comments
                if self._match(TokenType.PUNCTUATION, ']'):
                    break
                
                # Parse one array element
                element = self._parse_expression()
                node.elements.append(element)
                
                # Expect comma or end of array
                if self._match(TokenType.PUNCTUATION, ','):
                    self._consume()
                    # Skip any EOL tokens or comments after the comma
                    while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
                        self._consume()
                else:
                    # Skip any trailing EOL tokens or comments before the closing bracket
                    while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
                        self._consume()
                    break
        
        # Expect ']'
        self._expect(TokenType.PUNCTUATION, ']')
        
        return node
    
    def _error(self, message: str):
        """Raise a syntax error"""
        line = self.tokens[self.pos].line if self.pos < len(self.tokens) else "unknown"
        column = self.tokens[self.pos].column if self.pos < len(self.tokens) else "unknown"
        raise SyntaxError(f"Line {line}, column {column}: {message}")

class TempVariableManager:
    """Manages temporary variables to prevent conflicts and reuse issues"""
    
    def __init__(self):
        self.scoped_temp_vars = []  # Stack of scoped temp variable ranges
        self.base_temp_var = 1000   # Start temp vars at high offset to avoid conflicts
        self.allocated_temps = set()  # Track all allocated temp vars
        self.call_depth = 0
        self.freed_temps = set()    # Track freed temp vars for reuse
    
    def enter_scope(self):
        """Enter a new scope for temporary variable allocation"""
        self.call_depth += 1
        self.scoped_temp_vars.append({
            'allocated_in_scope': set(), 
            'depth': self.call_depth
        })
    
    def exit_scope(self):
        """Exit the current scope and free temporary variables"""
        if self.scoped_temp_vars:
            scope = self.scoped_temp_vars.pop()
            # Mark temp vars in this scope as freed
            for temp_var in scope['allocated_in_scope']:
                self.allocated_temps.discard(temp_var)
                self.freed_temps.add(temp_var)
            self.call_depth -= 1
    
    def allocate_temp_var(self) -> int:
        """Allocate a temporary variable in the current scope"""
        # First, try to reuse a freed temp variable (lowest number first)
        if self.freed_temps:
            temp_var = min(self.freed_temps)
            self.freed_temps.remove(temp_var)
            self.allocated_temps.add(temp_var)
            
            # Add to current scope
            if self.scoped_temp_vars:
                self.scoped_temp_vars[-1]['allocated_in_scope'].add(temp_var)
            
            return temp_var
        
        # No freed vars available, find the next available temp var
        temp_var = self.base_temp_var
        while temp_var in self.allocated_temps:
            temp_var += 1
        
        # Allocate this temp var
        self.allocated_temps.add(temp_var)
        
        # Add to current scope  
        if self.scoped_temp_vars:
            self.scoped_temp_vars[-1]['allocated_in_scope'].add(temp_var)
        
        return temp_var
    
    def reset(self):
        """Reset the temp variable manager (useful for debugging)"""
        self.scoped_temp_vars.clear()
        self.allocated_temps.clear()
        self.freed_temps.clear()
        self.call_depth = 0
    
    def get_stats(self):
        """Get statistics about temp variable usage"""
        max_allocated = max(self.allocated_temps) if self.allocated_temps else self.base_temp_var - 1
        total_ever_used = len(self.allocated_temps) + len(self.freed_temps)
        return {
            'currently_allocated': len(self.allocated_temps),
            'total_ever_used': total_ever_used,
            'max_temp_var': max_allocated,
            'freed_available': len(self.freed_temps),
            'scope_depth': self.call_depth
        }

class FunctionScope:
    """Represents a function's variable scope"""
    def __init__(self, name: str, parameters: List[str]):
        self.name = name
        self.parameters = parameters
        self.local_variables = {}
        self.next_local_offset = 0
        
        # IMPORTANT: Parameters are accessed as negative offsets from BP
        # because they're pushed before the function call
        for i, param in enumerate(parameters):
            # Parameters are in reverse order on stack: last param pushed first
            # BP+0: saved BP
            # BP+1: return address  
            # BP+2: first parameter (rightmost in declaration)
            # BP+3: second parameter
            # etc.
            param_offset = -(i + 2)  # Start at -2 for first param
            self.local_variables[param] = param_offset
    
    def allocate_local_var(self, name: str, size: int = 1) -> int:
        """Allocate a local variable and return its offset"""
        if name in self.local_variables:
            return self.local_variables[name]
        
        offset = self.next_local_offset
        self.local_variables[name] = offset
        self.next_local_offset += size
        
        return offset

class CodeGenerator:
    """Generates UW assembly code from an AST - ENHANCED with proper function support"""
    
    def __init__(self):
        self.code = []
        self.string_literals = []
        self.labels = {}
        self.label_counter = 0
        
        # ENHANCED: Better variable scope management
        self.global_variables = {}  # Global scope variables
        self.functions = {}         # Function definitions
        self.function_scopes = {}   # Function scopes for parameter/local variable tracking
        self.current_function = None  # Currently processing function
        self.next_global_var = 0    # Next global variable offset
        
        self.imported_functions = {}
        self.string_block = 1  # Default string block
        self.vm_position = 0  # Track VM code position
        self.variable_types = {}  # Track if variable contains string ID or integer
        self.variable_sizes = {}  # Track array sizes
        self.function_code = []  # Store function bodies separately
        self.main_program_code = []  # Store main program code
        self.current_target = None  # Track which code section we're writing to
        
        # Improved temporary variable management
        self.temp_var_manager = TempVariableManager()
        
        # Built-in functions to UW function IDs
        self.builtin_functions = {
            'random': 5,
            'get_quest': 15,
            'set_quest': 16,
            'compare': 4,
            'string_length': 11,
            'contains': 7,
            'gronk_door': 37,

            # Fantasy console functions
            # Graphics functions
            'clear_screen': 100,
            'set_pixel': 101,
            'draw_line': 102,
            'draw_rect': 103,
            'fill_rect': 104,
            'draw_circle': 105,
            'draw_sprite': 106,
            'print': 107,
            'flip_display': 109,
            
            # Sound functions
            'play_tone': 200,
            
            # Input functions
            'is_key_pressed': 300,
            'is_key_released': 301,
            
            # Math functions
            'math_sin': 501,
            'math_cos': 502,
            'math_sqrt': 503,
        }
    
    def generate(self, ast: Program, string_block: int = 1) -> str:
        """Generate assembly code from an AST - ENHANCED"""
        self.string_block = string_block
        self.current_target = self.main_program_code  # Start with main program
        
        # Reset temp variable manager at start of compilation
        self.temp_var_manager.reset()
        
        # First pass to collect labels, functions and string literals
        self._first_pass(ast)
        
        # Reset temp variables after first pass
        if self.temp_var_manager.get_stats()['total_ever_used'] > 0:
            print(f"WARNING: First pass allocated {self.temp_var_manager.get_stats()['total_ever_used']} temp vars (should be 0)")
            self.temp_var_manager.reset()
        
        # Second pass to generate code
        self._generate_code(ast)
        
        # Ensure all scopes are properly closed
        if self.temp_var_manager.call_depth > 0:
            print(f"WARNING: Temp variable scope depth is {self.temp_var_manager.call_depth} (should be 0)")
            while self.temp_var_manager.call_depth > 0:
                self.temp_var_manager.exit_scope()
        
        # Combine main program code and function code
        self.code = self.main_program_code + self.function_code
        
        # Format the code
        return self._format_code()

    def _first_pass(self, node: ASTNode, is_function_body: bool = False):
        """First pass to collect labels, functions and string literals"""
        if isinstance(node, Program):
            # Initialize variables for global scope
            self.global_variables = {}
            self.next_global_var = 0
            
            for child in node.children:
                self._first_pass(child)
        
        elif isinstance(node, FunctionDefinition):
            # Register the function
            self.functions[node.name] = {
                'params': node.parameters,
                'body': node.body
            }
            
            # Create function scope for parameter/variable tracking
            self.function_scopes[node.name] = FunctionScope(node.name, node.parameters)
            
            # Process function body to collect string literals
            for stmt in node.body:
                self._first_pass(stmt, is_function_body=True)
            
            return
        
        elif isinstance(node, LabelStatement):
            # Register the label
            self.labels[node.name] = None  # Actual address will be filled in second pass
        
        elif isinstance(node, Literal) and node.token.type == TokenType.STRING:
            # Register string literal
            if node.token.value not in self.string_literals:
                self.string_literals.append(node.token.value)
        
        elif isinstance(node, SayStatement):
            # Process the expression for strings
            self._first_pass(node.children[0], is_function_body)

        elif isinstance(node, BinaryOperation):
            # Process both sides of the binary operation
            self._first_pass(node.left, is_function_body)
            self._first_pass(node.right, is_function_body)
        
        elif isinstance(node, UnaryOperation):
            # Process the operand of unary operations
            self._first_pass(node.operand, is_function_body)
        
        elif isinstance(node, ArrayLiteral):
            # Process array elements
            for element in node.elements:
                self._first_pass(element, is_function_body)
        
        elif isinstance(node, ArrayAccess):
            # Process array and index
            self._first_pass(node.array, is_function_body)
            self._first_pass(node.index, is_function_body)
        
        elif isinstance(node, MenuStatement):
            # Process menu items
            for item in node.items:
                self._first_pass(item, is_function_body)
        
        elif isinstance(node, FilterMenuStatement):
            # Process menu items and flags
            for item in node.items:
                self._first_pass(item, is_function_body)
            for flag in node.flags:
                self._first_pass(flag, is_function_body)

        # Process children recursively
        if hasattr(node, 'children'):
            for child in node.children:
                self._first_pass(child, is_function_body)
        
        # Process specific node types that have special child structures
        if isinstance(node, IfStatement):
            self._first_pass(node.condition, is_function_body)
            for stmt in node.true_branch:
                self._first_pass(stmt, is_function_body)
            for stmt in node.false_branch:
                self._first_pass(stmt, is_function_body)
        
        elif isinstance(node, WhileStatement):
            self._first_pass(node.condition, is_function_body)
            for stmt in node.body:
                self._first_pass(stmt, is_function_body)
        
        elif isinstance(node, FunctionCall):
            for arg in node.arguments:
                self._first_pass(arg, is_function_body)
        
        elif isinstance(node, VariableDeclaration):
            # Process the initialization expression
            if node.children:
                self._first_pass(node.children[0], is_function_body)
        
        elif isinstance(node, Assignment):
            # Process the assigned value
            if node.children:
                self._first_pass(node.children[0], is_function_body)
        
        elif isinstance(node, ReturnStatement):
            # Process the return value
            if node.children:
                self._first_pass(node.children[0], is_function_body)
    
    def _generate_code(self, node: ASTNode):
        """Generate code for a node - ENHANCED"""
        if isinstance(node, Program):
            # Start the program
            self._emit("START")
            
            # Generate code for each statement, separating functions from main code
            for child in node.children:
                if isinstance(child, FunctionDefinition):
                    # Switch to function code generation
                    old_target = self.current_target
                    old_function = self.current_function
                    self.current_target = self.function_code
                    self.current_function = child.name
                    self._generate_function_code(child)
                    self.current_target = old_target
                    self.current_function = old_function
                else:
                    self._generate_code(child)
            
            # End the program
            self._emit("EXIT_OP")
        
        elif isinstance(node, VariableDeclaration):
            # Generate code for the value
            self._generate_code(node.children[0])
            
            # Check if this is an array initialization
            if isinstance(node.children[0], ArrayLiteral):
                # For arrays, we need to allocate space for all elements
                array_size = len(node.children[0].elements)
                var_id = self._allocate_variable(node.name, array_size)
                
                # Track that this is an array
                self.variable_types[node.name] = 'array'
                self.variable_sizes[node.name] = array_size
                
                # The array elements are already on the stack in reverse order
                # We need to store them in forward order
                for i in range(array_size):
                    element_addr = var_id + i
                    
                    # Store each element
                    self._emit(f"PUSHI_EFF {element_addr}")
                    self._emit("SWAP")
                    self._emit("STO")
            else:
                # Regular variable
                # Track variable type
                if isinstance(node.children[0], Literal):
                    if node.children[0].token.type == TokenType.STRING:
                        self.variable_types[node.name] = 'string'
                    else:
                        self.variable_types[node.name] = 'integer'
                else:
                    self.variable_types[node.name] = 'integer'  # Default
                
                # Allocate variable
                var_id = self._allocate_variable(node.name)
                
                # Store the value in the variable
                self._emit(f"PUSHI_EFF {var_id}")
                self._emit("SWAP")
                self._emit("STO")
        
        elif isinstance(node, Assignment):
            # Generate code for the value
            self._generate_code(node.children[0])
            
            # Handle different assignment targets
            if isinstance(node.target, Identifier):
                # Simple variable assignment
                var_id = self._get_variable_offset(node.target.name)
                if var_id is None:
                    raise NameError(f"Variable '{node.target.name}' is not defined")
                
                if node.operator == '=':
                    # Simple assignment
                    self._emit(f"PUSHI_EFF {var_id}")
                    self._emit("SWAP")
                    self._emit("STO")
                else:
                    # Compound assignment (+=, -=, *=, /=)
                    # Load the current value
                    self._emit(f"PUSHI_EFF {var_id}")
                    self._emit("FETCHM")
                    
                    # Swap to get value, current on stack
                    self._emit("SWAP")
                    
                    # Apply the operation
                    if node.operator == '+=':
                        self._emit("OPADD")
                    elif node.operator == '-=':
                        self._emit("OPSUB")
                    elif node.operator == '*=':
                        self._emit("OPMUL")
                    elif node.operator == '/=':
                        self._emit("OPDIV")
                    
                    # Store the result
                    self._emit(f"PUSHI_EFF {var_id}")
                    self._emit("SWAP")
                    self._emit("STO")
                    
            elif isinstance(node.target, ArrayAccess):
                # Array element assignment
                if not isinstance(node.target.array, Identifier):
                    raise SyntaxError("Only simple array variables are supported")
                
                array_name = node.target.array.name
                var_id = self._get_variable_offset(array_name)
                if var_id is None:
                    raise NameError(f"Array '{array_name}' is not defined")
                
                if self.variable_types.get(array_name) != 'array':
                    raise TypeError(f"Variable '{array_name}' is not an array")
                
                if node.operator == '=':
                    # Simple assignment
                    # Generate code for the index
                    self._generate_code(node.target.index)
                    
                    # Calculate address: base + index
                    self._emit(f"PUSHI_EFF {var_id}")
                    self._emit("OPADD")
                    
                    # Value is already on stack, address is now on stack
                    # Swap them to get address, value
                    self._emit("SWAP")
                    self._emit("STO")
                else:
                    # Compound assignment (+=, -=, *=, /=)
                    # Calculate the target address first
                    self._generate_code(node.target.index)
                    self._emit(f"PUSHI_EFF {var_id}")
                    self._emit("OPADD")
                    
                    # Save the address in result register for later use
                    self._emit("SAVE_REG")
                    
                    # Load current value from address
                    self._emit("PUSH_REG")  # Push address back
                    self._emit("FETCHM")    # Load current value: [value, current_value]
                    
                    # Apply the operation (stack: [value, current_value])
                    if node.operator == '+=':
                        self._emit("OPADD")  # current_value + value (commutative)
                    elif node.operator == '-=':
                        self._emit("SWAP")   # [current_value, value]
                        self._emit("OPSUB")  # current_value - value
                    elif node.operator == '*=':
                        self._emit("OPMUL")  # current_value * value (commutative)
                    elif node.operator == '/=':
                        self._emit("SWAP")   # [current_value, value]
                        self._emit("OPDIV")  # current_value / value
                    
                    # Store result back to address
                    self._emit("PUSH_REG")  # Push address: [result, address]
                    self._emit("SWAP")      # [address, result]
                    self._emit("STO")       # Store result at address
            else:
                raise SyntaxError("Invalid assignment target")
        
        elif isinstance(node, IfStatement):
            # Create labels
            else_label = self._create_label()
            end_label = self._create_label()
            
            # Generate condition code
            self._generate_code(node.condition)
            
            # Branch if false
            self._emit(f"BEQ {else_label}")
            
            # Generate true branch code
            for stmt in node.true_branch:
                self._generate_code(stmt)
            
            # Jump to end
            self._emit(f"JMP {end_label}")
            
            # Else branch
            self._emit_label(else_label)
            
            # Generate false branch code
            for stmt in node.false_branch:
                self._generate_code(stmt)
            
            # End label
            self._emit_label(end_label)
        
        elif isinstance(node, WhileStatement):
            # Create labels
            start_label = self._create_label()
            end_label = self._create_label()
            
            # Start label
            self._emit_label(start_label)
            
            # Generate condition code
            self._generate_code(node.condition)
            
            # Branch if false
            self._emit(f"BEQ {end_label}")
            
            # Generate body code
            for stmt in node.body:
                self._generate_code(stmt)
            
            # Jump back to start
            self._emit(f"JMP {start_label}")
            
            # End label
            self._emit_label(end_label)
        
        elif isinstance(node, FunctionCall):
            if node.name in self.builtin_functions:
                # BUILTIN FUNCTION - use temp variables for argument passing
                self.temp_var_manager.enter_scope()
                
                try:
                    temp_vars = []
                    for i, arg in enumerate(node.arguments):
                        temp_var = self.temp_var_manager.allocate_temp_var()
                        temp_vars.append(temp_var)
                        
                        # Generate and store the argument
                        self._generate_code(arg)
                        self._emit(f"PUSHI_EFF {temp_var}")
                        self._emit("SWAP")
                        self._emit("STO")
                    
                    # Push addresses of temp variables for function call
                    for temp_var in temp_vars:
                        self._emit(f"PUSHI_EFF {temp_var}")
                    
                    # Push the number of arguments
                    self._emit(f"PUSHI {len(node.arguments)}")
                    
                    # Call the function
                    self._emit(f"CALLI {self.builtin_functions[node.name]}")
                    
                finally:
                    self.temp_var_manager.exit_scope()
                    
            else:
                # USER-DEFINED FUNCTION - ENHANCED with proper parameter passing
                if node.name not in self.functions:
                    raise NameError(f"Function '{node.name}' is not defined")
                
                # Generate code for arguments and push them onto the stack
                # Arguments are pushed in order (first arg pushed first)
                for arg in node.arguments:
                    self._generate_code(arg)
                
                # Call the function
                self._emit(f"CALL {node.name}")
                
                # IMPORTANT: If function has parameters, clean up the stack
                func_params = self.functions[node.name]['params']
                if func_params:
                    # Pop the parameters off the stack (caller cleans up)
                    for _ in func_params:
                        self._emit("POP")
        
        elif isinstance(node, ReturnStatement):
            # Generate code for return value (if any)
            if node.children:
                self._generate_code(node.children[0])  # Value already on stack
                # REMOVED: self._emit("SAVE_REG")
                # REMOVED: self._emit("PUSH_REG")
            else:
                self._emit("PUSHI 0")  # Default return value
            
            # Restore stack frame and return
            self._emit("BPTOSP")  # Restore stack pointer
            self._emit("POPBP")   # Restore previous base pointer
            self._emit("RET")
        
        elif isinstance(node, SayStatement):
            # Generate code for the expression (substitution handled in BinaryOperation)
            self._generate_code(node.children[0])
            
            # Emit say operation
            self._emit("SAY_OP")
        
        elif isinstance(node, AskStatement):
            # Call the built-in babl_ask function
            self._emit("PUSHI 0")  # No arguments
            self._emit("CALLI 3")  # babl_ask ID is 3
            
            # Save the result if a variable was specified
            if node.variable:
                var_id = self._allocate_variable(node.variable)
                self._emit("PUSH_REG")  # Get result from result register
                self._emit(f"PUSHI_EFF {var_id}")
                self._emit("SWAP")
                self._emit("STO")
        
        elif isinstance(node, MenuStatement):
            # Enter scope for menu processing
            self.temp_var_manager.enter_scope()
            
            try:
                # Create an array to hold the strings
                array_var = self.temp_var_manager.allocate_temp_var()
                
                # Generate code for each menu item
                for i, item in enumerate(node.items):
                    # Generate code for the item
                    self._generate_code(item)
                    
                    # Store in the array
                    self._emit(f"PUSHI_EFF {array_var}")
                    self._emit(f"PUSHI {i}")
                    self._emit("OPADD")  # Add index to base address
                    self._emit("SWAP")
                    self._emit("STO")
                
                # Add a 0 terminator
                self._emit("PUSHI 0")
                self._emit(f"PUSHI_EFF {array_var}")
                self._emit(f"PUSHI {len(node.items)}")
                self._emit("OPADD")  # Add index to base address
                self._emit("SWAP")
                self._emit("STO")
                
                # Call the babl_menu function
                self._emit(f"PUSHI_EFF {array_var}")
                self._emit("PUSHI 1")  # One argument
                self._emit("CALLI 0")  # babl_menu ID is 0
                
                # Save the result if a variable was specified
                if node.variable:
                    var_id = self._allocate_variable(node.variable)
                    self._emit("PUSH_REG")  # Get result from result register
                    self._emit(f"PUSHI_EFF {var_id}")
                    self._emit("SWAP")
                    self._emit("STO")
            
            finally:
                self.temp_var_manager.exit_scope()

        elif isinstance(node, FilterMenuStatement):
            # Enter scope for filtermenu processing  
            self.temp_var_manager.enter_scope()
            
            try:
                # Create arrays to hold the strings and flags
                strings_var = self.temp_var_manager.allocate_temp_var()
                flags_var = self.temp_var_manager.allocate_temp_var()
                
                # Generate code for each menu item and flag
                for i, (item, flag) in enumerate(zip(node.items, node.flags)):
                    # Generate code for the item
                    self._generate_code(item)
                    
                    # Store in the strings array
                    self._emit(f"PUSHI_EFF {strings_var}")
                    self._emit(f"PUSHI {i}")
                    self._emit("OPADD")  # Add index to base address
                    self._emit("SWAP")
                    self._emit("STO")
                    
                    # Generate code for the flag
                    self._generate_code(flag)
                    
                    # Store in the flags array
                    self._emit(f"PUSHI_EFF {flags_var}")
                    self._emit(f"PUSHI {i}")
                    self._emit("OPADD")  # Add index to base address
                    self._emit("SWAP")
                    self._emit("STO")
                
                # Add a 0 terminator for strings
                self._emit("PUSHI 0")
                self._emit(f"PUSHI_EFF {strings_var}")
                self._emit(f"PUSHI {len(node.items)}")
                self._emit("OPADD")  # Add index to base address
                self._emit("SWAP")
                self._emit("STO")
                
                # Call the babl_fmenu function
                self._emit(f"PUSHI_EFF {flags_var}")
                self._emit(f"PUSHI_EFF {strings_var}")
                self._emit("PUSHI 2")  # Two arguments
                self._emit("CALLI 1")  # babl_fmenu ID is 1
                
                # Save the result if a variable was specified
                if node.variable:
                    var_id = self._allocate_variable(node.variable)
                    self._emit("PUSH_REG")  # Get result from result register
                    self._emit(f"PUSHI_EFF {var_id}")
                    self._emit("SWAP")
                    self._emit("STO")
            
            finally:
                self.temp_var_manager.exit_scope()
        
        elif isinstance(node, GotoStatement):
            # Check if the label exists
            if node.label not in self.labels:
                raise NameError(f"Label '{node.label}' is not defined")
            
            # Jump to the label
            self._emit(f"JMP {node.label}")
        
        elif isinstance(node, LabelStatement):
            # Emit the label
            self._emit_label(node.name)
        
        elif isinstance(node, ExitStatement):
            # Exit the program
            self._emit("EXIT_OP")
        
        elif isinstance(node, ArrayLiteral):
            # Push elements in reverse order since stack is LIFO
            # This ensures they're stored in the correct forward order in memory
            for element in reversed(node.elements):
                self._generate_code(element)
        
        elif isinstance(node, ArrayAccess):
            if not isinstance(node.array, Identifier):
                raise SyntaxError("Only simple array variables are supported")
            
            array_name = node.array.name
            var_id = self._get_variable_offset(array_name)
            if var_id is None:
                raise NameError(f"Array '{array_name}' is not defined")
            
            # Skip type check if variable type unknown (function parameters)
            var_type = self.variable_types.get(array_name)
            if var_type is not None and var_type != 'array':
                raise TypeError(f"Variable '{array_name}' is not an array")
            
            # Generate code for the index
            self._generate_code(node.index)
            
            # Calculate address: base + index
            self._emit(f"PUSHI_EFF {var_id}")    # ← FIX: Use PUSHI_EFF instead of PUSHI
            self._emit("OPADD")
            
            # Load the value at that address
            self._emit("FETCHM")
        
        elif isinstance(node, BinaryOperation):
            # Check for string concatenation first
            if node.token.value == '+':
                # Check for nested concatenations (not supported yet)
                left_is_concat = isinstance(node.left, BinaryOperation) and node.left.token.value == '+'
                right_is_concat = isinstance(node.right, BinaryOperation) and node.right.token.value == '+'
                
                if left_is_concat or right_is_concat:
                    print(f"\n  WARNING: Multiple string concatenations not supported yet at line {node.token.line}")
                    print("  Use separate statements instead!!!")
                    # Fall back to numeric addition
                    self._generate_code(node.left)
                    self._generate_code(node.right)
                    self._emit("OPADD")
                    return

            # Check for string concatenation first
            if node.token.value == '+':
                # Check if left is string literal and right is variable
                if (isinstance(node.left, Literal) and 
                    node.left.token.type == TokenType.STRING and
                    isinstance(node.right, Identifier)):
                    
                    # Get the variable offset
                    var_offset = self._get_variable_offset(node.right.name)
                    if var_offset is not None:
                        # Determine substitution type based on variable type
                        var_type = self.variable_types.get(node.right.name, 'integer')
                        subst_type = 'SS' if var_type == 'string' else 'SI'
                        
                        # Create substituted string
                        original_string = node.left.value
                        substituted_string = f"{original_string}@{subst_type}{var_offset}"
                        
                        # Find and replace the original string instead of adding new one
                        try:
                            string_idx = self.string_literals.index(original_string)
                            self.string_literals[string_idx] = substituted_string
                        except ValueError:
                            self.string_literals.append(substituted_string)
                            string_idx = len(self.string_literals) - 1
                        
                        # Push the string index
                        self._emit(f"PUSHI {string_idx}")
                        return
                
                # Handle right string + left variable case similarly...
                elif (isinstance(node.right, Literal) and 
                      node.right.token.type == TokenType.STRING and
                      isinstance(node.left, Identifier)):
                    
                    var_offset = self._get_variable_offset(node.left.name)
                    if var_offset is not None:
                        # Determine substitution type
                        var_type = self.variable_types.get(node.left.name, 'integer')
                        subst_type = 'SS' if var_type == 'string' else 'SI'
                        
                        original_string = node.right.value
                        substituted_string = f"@{subst_type}{var_offset}{original_string}"
                        
                        try:
                            string_idx = self.string_literals.index(original_string)
                            self.string_literals[string_idx] = substituted_string
                        except ValueError:
                            self.string_literals.append(substituted_string)
                            string_idx = len(self.string_literals) - 1
                        
                        self._emit(f"PUSHI {string_idx}")
                        return
            
            # Fall back to original binary operation handling
            # Generate code for left and right operands
            self._generate_code(node.left)
            self._generate_code(node.right)
            
            # Emit the operation
            if node.token.value == '+':
                self._emit("OPADD")
            elif node.token.value == '-':
                self._emit("OPSUB")
            elif node.token.value == '*':
                self._emit("OPMUL")
            elif node.token.value == '/':
                self._emit("OPDIV")
            elif node.token.value == '%':
                self._emit("OPMOD")
            elif node.token.value == '==':
                self._emit("TSTEQ")
            elif node.token.value == '!=':
                self._emit("TSTNE")
            elif node.token.value == '<':
                self._emit("TSTLT")
            elif node.token.value == '>':
                self._emit("TSTGT")
            elif node.token.value == '<=':
                self._emit("TSTLE")
            elif node.token.value == '>=':
                self._emit("TSTGE")
            elif node.token.value == 'and':
                self._emit("OPAND")
            elif node.token.value == 'or':
                self._emit("OPOR")
        
        elif isinstance(node, UnaryOperation):
            # Generate code for the operand
            self._generate_code(node.operand)
            
            # Emit the operation
            if node.token.value == '-':
                self._emit("OPNEG")
            elif node.token.value == 'not':
                self._emit("OPNOT")
        
        elif isinstance(node, Literal):
            if node.token.type == TokenType.NUMBER:
                # Push the number
                self._emit(f"PUSHI {node.value}")
            elif node.token.type == TokenType.STRING:
                # Get the string index
                string_idx = self.string_literals.index(node.value)
                
                # Push the string index
                self._emit(f"PUSHI {string_idx}")
            elif node.token.type == TokenType.KEYWORD and node.token.value in ['true', 'false']:
                # Fix: Use node.token.value instead of node.value
                self._emit(f"PUSHI {1 if node.token.value == 'true' else 0}")
        
        elif isinstance(node, Identifier):
            # Get the variable
            var_id = self._get_variable_offset(node.name)
            if var_id is None:
                raise NameError(f"Variable '{node.name}' is not defined")
            
            # Check if this is an array - if so, push the base address
            if self.variable_types.get(node.name) == 'array':
                # For arrays, calculate the absolute memory address at runtime
                # Array base address = base_pointer + var_id
                self._emit(f"PUSHBP")           # Push base pointer
                self._emit(f"PUSHI {var_id}")   # Push variable offset
                self._emit("OPADD")             # Add to get absolute address
            else:
                # For regular variables, load the value
                self._emit(f"PUSHI_EFF {var_id}")
                self._emit("FETCHM")

    def _generate_function_code(self, node: FunctionDefinition):
        """Generate code for a function definition - ENHANCED with proper stack frame setup"""
        # Emit the function label
        self._emit_label(node.name)
        
        # ENHANCED: Set up proper stack frame for functions with parameters
        if node.parameters:
            # Save the current base pointer
            self._emit("PUSHBP")
            
            # Set new base pointer to current stack position
            self._emit("SPTOBP")
            
            # Reserve space for local variables if needed
            # (This would be calculated during analysis of function body)
            # For now, we'll reserve a small amount
            self._emit("PUSHI 10")  # Reserve space for 10 local variables
            self._emit("ADDSP")
        
        # Generate code for function body
        for stmt in node.body:
            self._generate_code(stmt)
        
        # If no explicit return was found, add an implicit return
        if not node.body or not isinstance(node.body[-1], ReturnStatement):
            # ENHANCED: Proper stack cleanup for implicit return
            if node.parameters:
                self._emit("BPTOSP")  # Restore stack pointer
                self._emit("POPBP")   # Restore previous base pointer
            self._emit("RET")
    
    def _get_variable_offset(self, name: str) -> Optional[int]:
        """Get variable offset, checking function scope first, then global scope - ENHANCED"""
        # If we're in a function, check function scope first
        if self.current_function and self.current_function in self.function_scopes:
            scope = self.function_scopes[self.current_function]
            if name in scope.local_variables:
                return scope.local_variables[name]
        
        # Check global scope
        if name in self.global_variables:
            return self.global_variables[name]
        
        return None
    
    def _allocate_variable(self, name: str, size: int = 1) -> int:
        """Allocate a variable in the appropriate scope - ENHANCED"""
        # If we're in a function, allocate in function scope
        if self.current_function and self.current_function in self.function_scopes:
            scope = self.function_scopes[self.current_function]
            return scope.allocate_local_var(name, size)
        
        # Otherwise, allocate in global scope
        if name in self.global_variables:
            return self.global_variables[name]
        
        offset = self.next_global_var
        self.global_variables[name] = offset
        self.next_global_var += size
        
        return offset
    
    def _format_code(self) -> str:
        """Format the generated assembly code - ENHANCED with better scope reporting"""
        # Get temp variable stats
        temp_stats = self.temp_var_manager.get_stats()
        
        # Add headers and metadata
        result = [
            "; UWScript compiled to UW assembly - ENHANCED VERSION with Function Parameters",
            f"; String Block: {self.string_block}",
            "; String literals:",
        ]
        
        # Add string literals
        for i, string in enumerate(self.string_literals):
            result.append(f"; {i}: \"{string}\"")
        
        result.append("")
        
        # Add global variable mappings
        result.append("; Global Variables:")
        for name, offset in self.global_variables.items():
            var_type = self.variable_types.get(name, 'integer')
            if var_type == 'array':
                size = self.variable_sizes.get(name, 0)
                result.append(f"; {name} -> {offset} (array[{size}])")
            else:
                result.append(f"; {name} -> {offset} ({var_type})")
        
        result.append("")
        
        # Add function scope information
        result.append("; Function Scopes:")
        for func_name, scope in self.function_scopes.items():
            result.append(f"; Function {func_name}:")
            result.append(f";   Parameters: {scope.parameters}")
            for var_name, offset in scope.local_variables.items():
                if var_name in scope.parameters:
                    result.append(f";   {var_name} -> {offset} (parameter)")
                else:
                    result.append(f";   {var_name} -> {offset} (local)")
        
        result.append("")
        
        # Add temp variable info
        result.append(f"; Temp variables - Total used: {temp_stats['total_ever_used']}")
        result.append(f"; Temp variables - Currently allocated: {temp_stats['currently_allocated']}")
        result.append(f"; Temp variables - Max temp var: {temp_stats['max_temp_var']}")
        result.append("")
        
        # Add the code
        result.extend(self.code)
        
        return "\n".join(result)
    
    def _emit(self, line: str):
        """Emit a line of assembly code to the current target"""
        if self.current_target is not None:
            self.current_target.append(line)
        else:
            self.code.append(line)
        
        # Update VM position based on instruction type
        if not line.endswith(':'):  # Not a label
            if ' ' in line:  # Instruction with operand
                self.vm_position += 2
            else:  # Instruction without operand
                self.vm_position += 1

    def _emit_label(self, name: str):
        """Emit a label to the current target"""
        if self.current_target is not None:
            self.current_target.append(f"{name}:")
        else:
            self.code.append(f"{name}:")
        self.labels[name] = self.vm_position

    def _create_label(self) -> str:
        """Create a unique label name"""
        label = f"label_{self.label_counter}"
        self.label_counter += 1
        self.labels[label] = None  # Will be filled in when emitted
        return label

class SimpleParser:
    """
    A simplified parser that just extracts string literals and basic structure.
    This avoids the complex parsing rules that cause errors in the full parser.
    """
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.strings = []
    
    def parse(self):
        """Extract string literals and basic structure"""
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            
            # Extract string literals
            if token.type == TokenType.STRING:
                if token.value not in self.strings:
                    self.strings.append(token.value)
            
            self.pos += 1
        
        return self.strings

def generate_strings_file(strings: List[str], block_id: int) -> str:
    """Generate UW-style strings.txt file content"""
    output = [f"STRINGS.PAK: 1 string blocks.\n"]
    output.append(f"block: {block_id:04x}; {len(strings)} strings.")
    
    for i, s in enumerate(strings):
        # Replace newlines with \n in the output
        s_escaped = s.replace('\n', '\\n')
        output.append(f"{i}: {s_escaped}")
    
    output.append("")  # Empty line at end
    return "\n".join(output)

def extract_strings(source: str, block_id: int = 1) -> str:
    """Extract string literals from source code and format for UW"""
    # Tokenize the source
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    
    # Use the simple parser to extract strings
    parser = SimpleParser(tokens)
    strings = parser.parse()
    
    # Generate the strings file content
    return generate_strings_file(strings, block_id)

def compile_uwscript(source: str, block_id: int = 1, debug: bool = False) -> Dict[str, str]:
    """
    Compile UWScript code and extract strings - ENHANCED
    
    Args:
        source: The UWScript source code
        block_id: The string block ID to use
        debug: Enable debug output
        
    Returns:
        Dict with "assembly" and "strings" keys
    """
    # Tokenize the source
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    
    # Parse the tokens
    parser = Parser(tokens, debug=debug)
    ast = parser.parse()
    
    # Generate code (this will collect all strings including substituted ones)
    generator = CodeGenerator()
    assembly = generator.generate(ast, block_id)
    
    # Generate strings content using the generator's complete string list
    strings_content = generate_strings_file(generator.string_literals, block_id)
    
    return {
        "assembly": assembly,
        "strings": strings_content
    }

def main():
    parser = argparse.ArgumentParser(description="Compile UWScript to UW assembly and extract strings - ENHANCED")
    parser.add_argument("input", help="Input UWScript file")
    parser.add_argument("-o", "--output", help="Output assembly file")
    parser.add_argument("-s", "--strings", help="Output strings file")
    parser.add_argument("-b", "--block", type=int, default=1, help="String block ID (default: 1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Read the input file
    try:
        with open(args.input, "r") as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        return 1
    
    try:
        # Compile the source
        result = compile_uwscript(source, args.block, debug=args.debug)
        
        # Write the output files
        if args.output:
            with open(args.output, "w") as f:
                f.write(result["assembly"])
            if args.verbose:
                print(f"Assembly written to {args.output}")
        else:
            print(result["assembly"])
        
        # Always generate a strings file
        strings_file = args.strings or f"{os.path.splitext(args.input)[0]}_strings.txt"
        with open(strings_file, "w") as f:
            f.write(result["strings"])
        
        if args.verbose:
            print(f"Strings written to {strings_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
