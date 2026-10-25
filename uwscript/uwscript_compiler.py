#!/usr/bin/env python3
"""
UWScript compiler.

Compiles a UWScript program (.uws) into Ultima Underworld conversation
assembly (.asm) and the matching string block (<name>_strings.txt).

    python uwscript_compiler.py program.uws            # -> program.asm, program_strings.txt
    python uwscript_compiler.py program.uws -o out.asm -s out_strings.txt -b 1

The language is described in docs/uwscript-language-spec.md, the generated
code (memory layout, calling convention) in docs/compiler-internals.md.
"""

import argparse
import os
import sys
from enum import Enum, auto
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uw_engine import (FUNCTION_IDS, GAME_GLOBALS, GAME_GLOBAL_ADDRESSES, IMPORTED_FUNCTIONS,  # noqa: E402
                       PRIVATE_GLOBALS_BASE)

# Compilation targets: 'uw' produces conversations the original game can run;
# 'console' also allows the fantasy console functions and VM extensions.
TARGETS = ('uw', 'console')

# Absolute address of the first UWScript global: the conversation's private
# globals start after the game globals (0..30), as in the game.
GLOBALS_BASE = PRIVATE_GLOBALS_BASE
# Upper limit for the memory slots (globals); the stack follows them.
MAX_MEMORY_SLOTS = 0x8000
MAX_WORD = 65535


class UWScriptError(Exception):
    """A compile error with a source position."""

    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None):
        self.message = message
        self.line = line
        self.column = column
        if line is not None and column is not None:
            text = f"Line {line}, column {column}: {message}"
        elif line is not None:
            text = f"Line {line}: {message}"
        else:
            text = message
        super().__init__(text)


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    OPERATOR = auto()
    PUNCTUATION = auto()
    COMMENT = auto()
    EOL = auto()
    EOF = auto()


class Token:
    def __init__(self, type: TokenType, value: str, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.column})"


class Lexer:
    """Tokenizes UWScript source code."""

    KEYWORDS = {
        'if', 'else', 'elseif', 'endif', 'goto', 'label', 'exit',
        'function', 'endfunction', 'return',
        'let', 'true', 'false',
        'say', 'ask', 'menu', 'filtermenu',
        'and', 'or', 'not',
        'while', 'endwhile',
    }

    OPERATORS = {
        '+', '-', '*', '/', '%', '=', '==', '!=', '>', '<', '>=', '<=',
        '+=', '-=', '*=', '/=', '%=', '!',
    }

    PUNCTUATION = {'(', ')', '[', ']', ','}

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            char = self.source[self.pos]

            if char == '\n':
                self.tokens.append(Token(TokenType.EOL, '\n', self.line, self.column))
                self.line += 1
                self.column = 1
                self.pos += 1
                continue

            if char.isspace():
                self._advance()
                continue

            if char == '/' and self._peek_char(1) == '/':
                self._tokenize_comment()
            elif char.isalpha() or char == '_':
                self._tokenize_identifier()
            elif char.isdigit():
                self._tokenize_number()
            elif char == '"':
                self._tokenize_string()
            elif char in self.OPERATORS or char in self.PUNCTUATION or char == '!':
                self._tokenize_operator_or_punctuation()
            else:
                self._error(f"Unexpected character: '{char}'")

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.column))
        return self.tokens

    def _peek_char(self, offset: int = 0) -> str:
        pos = self.pos + offset
        return self.source[pos] if pos < len(self.source) else ''

    def _advance(self) -> str:
        char = self.source[self.pos]
        self.pos += 1
        self.column += 1
        return char

    def _tokenize_comment(self):
        start_column = self.column
        self._advance()
        self._advance()
        comment = ''
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            comment += self._advance()
        self.tokens.append(Token(TokenType.COMMENT, comment, self.line, start_column))

    def _tokenize_identifier(self):
        start_column = self.column
        identifier = ''
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            identifier += self._advance()
        token_type = TokenType.KEYWORD if identifier in self.KEYWORDS else TokenType.IDENTIFIER
        self.tokens.append(Token(token_type, identifier, self.line, start_column))

    def _tokenize_number(self):
        start_column = self.column
        number = ''
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            number += self._advance()
        if self._peek_char().isalpha() or self._peek_char() == '_':
            self._error(f"Invalid number: '{number}{self._peek_char()}'")
        if int(number) > MAX_WORD:
            raise UWScriptError(f"Number {number} is too large (maximum is {MAX_WORD})", self.line, start_column)
        self.tokens.append(Token(TokenType.NUMBER, number, self.line, start_column))

    def _tokenize_string(self):
        start_line = self.line
        start_column = self.column
        self._advance()  # opening quote
        string = ''
        escapes = {'n': '\n', 't': '\t', '"': '"', '\\': '\\'}

        while True:
            if self.pos >= len(self.source) or self.source[self.pos] == '\n':
                raise UWScriptError("Unterminated string", start_line, start_column)
            char = self._advance()
            if char == '"':
                break
            if char == '\\' and self.pos < len(self.source) and self.source[self.pos] != '\n':
                escaped = self._advance()
                string += escapes.get(escaped, '\\' + escaped)
            else:
                string += char

        self.tokens.append(Token(TokenType.STRING, string, start_line, start_column))

    def _tokenize_operator_or_punctuation(self):
        start_column = self.column
        two_chars = self.source[self.pos:self.pos + 2]
        if two_chars in self.OPERATORS:
            self._advance()
            self._advance()
            self.tokens.append(Token(TokenType.OPERATOR, two_chars, self.line, start_column))
            return

        char = self._advance()
        token_type = TokenType.OPERATOR if char in self.OPERATORS else TokenType.PUNCTUATION
        self.tokens.append(Token(token_type, char, self.line, start_column))

    def _error(self, message: str):
        raise UWScriptError(message, self.line, self.column)


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------

class ASTNode:
    def __init__(self, token: Optional[Token] = None):
        self.token = token
        self.children = []

    @property
    def line(self) -> Optional[int]:
        return self.token.line if self.token else None

    def add_child(self, child):
        self.children.append(child)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.token})"


class Program(ASTNode): pass
class Statement(ASTNode): pass
class Expression(ASTNode):
    parenthesized = False
class BinaryOperation(Expression): pass
class UnaryOperation(Expression): pass
class Literal(Expression): pass
class Identifier(Expression): pass
class ArrayLiteral(Expression): pass
class ArrayAccess(Expression): pass
class FunctionCall(Expression): pass
class VariableDeclaration(Statement): pass
class Assignment(Statement): pass
class IfStatement(Statement): pass
class WhileStatement(Statement): pass
class FunctionDefinition(Statement): pass
class ReturnStatement(Statement): pass
class SayStatement(Statement): pass
class AskStatement(Statement): pass
class MenuStatement(Statement): pass
class FilterMenuStatement(Statement): pass
class GotoStatement(Statement): pass
class LabelStatement(Statement): pass
class ExitStatement(Statement): pass


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

BLOCK_END_KEYWORDS = {'endif', 'else', 'elseif', 'endwhile', 'endfunction'}
ASSIGNMENT_OPERATORS = {'=', '+=', '-=', '*=', '/=', '%='}


class Parser:
    """Parses a list of tokens into an AST."""

    def __init__(self, tokens: List[Token], debug: bool = False):
        self.tokens = tokens
        self.pos = 0
        self.debug = debug
        self.block_depth = 0
        self.function_depth = 0

    def parse(self) -> Program:
        program = Program()
        while True:
            self._skip_newlines()
            token = self._peek()
            if token.type == TokenType.EOF:
                break
            if token.type == TokenType.KEYWORD and token.value in BLOCK_END_KEYWORDS:
                self._error(f"'{token.value}' without a matching opening statement", token)
            program.add_child(self._parse_statement())
        return program

    # -- token helpers ------------------------------------------------------

    def _peek(self, offset: int = 0) -> Token:
        pos = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[pos]

    def _consume(self) -> Token:
        token = self._peek()
        if token.type != TokenType.EOF:
            self.pos += 1
        return token

    def _match(self, type: TokenType, value: Optional[str] = None) -> bool:
        token = self._peek()
        return token.type == type and (value is None or token.value == value)

    def _expect(self, type: TokenType, value: Optional[str] = None, what: Optional[str] = None) -> Token:
        if not self._match(type, value):
            expected = what or (f"'{value}'" if value else type.name.lower())
            self._error(f"Expected {expected}, got {self._describe(self._peek())}")
        return self._consume()

    def _skip_newlines(self):
        while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
            self.pos += 1

    def _end_statement(self):
        """A statement must be followed by a comment, a line break or the end of the file."""
        while self._match(TokenType.COMMENT):
            self.pos += 1
        token = self._peek()
        if token.type == TokenType.EOL:
            self.pos += 1
        elif token.type != TokenType.EOF:
            self._error(f"Unexpected {self._describe(token)} after statement", token)

    @staticmethod
    def _describe(token: Token) -> str:
        if token.type == TokenType.EOF:
            return "end of file"
        if token.type == TokenType.EOL:
            return "end of line"
        if token.type == TokenType.STRING:
            return f'string "{token.value}"'
        return f"'{token.value}'"

    def _error(self, message: str, token: Optional[Token] = None):
        token = token or self._peek()
        raise UWScriptError(message, token.line, token.column)

    def _parse_block(self, terminators: set, opener: Token) -> list:
        """Parse statements until one of the terminator keywords (not consumed)."""
        statements = []
        self.block_depth += 1
        while True:
            self._skip_newlines()
            token = self._peek()
            closing = next(t for t in terminators if t.startswith('end'))
            expected = ' or '.join(f"'{t}'" for t in sorted(terminators))
            if token.type == TokenType.EOF:
                self._error(f"Missing '{closing}' for '{opener.value}' started at line {opener.line}", token)
            if token.type == TokenType.KEYWORD and token.value in terminators:
                break
            if token.type == TokenType.KEYWORD and token.value in BLOCK_END_KEYWORDS:
                self._error(f"Unexpected '{token.value}' inside '{opener.value}' block started at line "
                            f"{opener.line} (expected {expected})", token)
            statements.append(self._parse_statement())
        self.block_depth -= 1
        return statements

    # -- statements ---------------------------------------------------------

    def _parse_statement(self):
        token = self._peek()

        if token.type == TokenType.KEYWORD:
            handler = {
                'let': self._parse_variable_declaration,
                'if': self._parse_if_statement,
                'while': self._parse_while_statement,
                'function': self._parse_function_definition,
                'return': self._parse_return_statement,
                'say': self._parse_say_statement,
                'ask': self._parse_ask_statement,
                'menu': self._parse_menu_statement,
                'filtermenu': self._parse_filtermenu_statement,
                'goto': self._parse_goto_statement,
                'label': self._parse_label_statement,
                'exit': self._parse_exit_statement,
            }.get(token.value)
            if handler is None:
                self._error(f"Unexpected keyword '{token.value}'", token)
            return handler()

        if token.type == TokenType.IDENTIFIER:
            return self._parse_assignment_or_call()

        self._error(f"Unexpected {self._describe(token)} at start of statement", token)

    def _parse_assignment_or_call(self):
        start = self._peek()
        expr = self._parse_postfix()
        token = self._peek()

        if token.type == TokenType.OPERATOR and token.value in ASSIGNMENT_OPERATORS:
            if not isinstance(expr, (Identifier, ArrayAccess)):
                self._error("Invalid assignment target", start)
            op_token = self._consume()
            value = self._parse_expression()
            self._end_statement()
            node = Assignment(op_token)
            node.target = expr
            node.operator = op_token.value
            node.add_child(value)
            return node

        if isinstance(expr, FunctionCall):
            self._end_statement()
            return expr

        if token.type == TokenType.OPERATOR and token.value == '==':
            self._error("Use '=' to assign a value ('==' compares values)", token)
        self._error(f"Expected an assignment or a function call starting with '{start.value}'", start)

    def _parse_variable_declaration(self) -> VariableDeclaration:
        let_token = self._expect(TokenType.KEYWORD, 'let')
        name_token = self._expect(TokenType.IDENTIFIER, what="variable name")
        node = VariableDeclaration(let_token)
        node.name = name_token.value

        # "let name" without a value declares a saved global: it keeps the
        # value from the last conversation (0 the first time)
        while self._match(TokenType.COMMENT):
            self.pos += 1
        if self._match(TokenType.EOL) or self._match(TokenType.EOF):
            if self.function_depth > 0:
                self._error("Local variables need a value (only globals can be declared without one)",
                            name_token)
            self._end_statement()
            return node

        self._expect(TokenType.OPERATOR, '=')
        node.add_child(self._parse_expression())
        self._end_statement()
        return node

    def _parse_if_statement(self) -> IfStatement:
        if_token = self._expect(TokenType.KEYWORD, 'if')
        root = IfStatement(if_token)
        root.condition = self._parse_expression()
        self._end_statement()
        root.true_branch = self._parse_block({'elseif', 'else', 'endif'}, if_token)
        root.false_branch = []

        current = root
        while self._match(TokenType.KEYWORD, 'elseif'):
            elseif_token = self._consume()
            node = IfStatement(elseif_token)
            node.condition = self._parse_expression()
            self._end_statement()
            node.true_branch = self._parse_block({'elseif', 'else', 'endif'}, if_token)
            node.false_branch = []
            current.false_branch = [node]
            current = node

        if self._match(TokenType.KEYWORD, 'else'):
            self._consume()
            self._end_statement()
            current.false_branch = self._parse_block({'endif'}, if_token)

        self._expect(TokenType.KEYWORD, 'endif')
        self._end_statement()
        return root

    def _parse_while_statement(self) -> WhileStatement:
        while_token = self._expect(TokenType.KEYWORD, 'while')
        node = WhileStatement(while_token)
        node.condition = self._parse_expression()
        self._end_statement()
        node.body = self._parse_block({'endwhile'}, while_token)
        self._expect(TokenType.KEYWORD, 'endwhile')
        self._end_statement()
        return node

    def _parse_function_definition(self) -> FunctionDefinition:
        function_token = self._expect(TokenType.KEYWORD, 'function')
        if self.block_depth > 0 or self.function_depth > 0:
            self._error("Functions can only be defined at the top level of a program", function_token)
        name_token = self._expect(TokenType.IDENTIFIER, what="function name")

        parameters = []
        self._expect(TokenType.PUNCTUATION, '(')
        if not self._match(TokenType.PUNCTUATION, ')'):
            while True:
                param = self._expect(TokenType.IDENTIFIER, what="parameter name")
                if param.value in parameters:
                    self._error(f"Duplicate parameter '{param.value}'", param)
                parameters.append(param.value)
                if not self._match(TokenType.PUNCTUATION, ','):
                    break
                self._consume()
        self._expect(TokenType.PUNCTUATION, ')')
        self._end_statement()

        node = FunctionDefinition(function_token)
        node.name = name_token.value
        node.parameters = parameters
        self.function_depth += 1
        node.body = self._parse_block({'endfunction'}, function_token)
        self.function_depth -= 1
        self._expect(TokenType.KEYWORD, 'endfunction')
        self._end_statement()

        if self.debug:
            print(f"Parsed function '{node.name}' with {len(node.body)} statements")
        return node

    def _parse_return_statement(self) -> ReturnStatement:
        return_token = self._expect(TokenType.KEYWORD, 'return')
        if self.function_depth == 0:
            self._error("'return' outside of a function (use 'exit' to end the conversation)", return_token)
        node = ReturnStatement(return_token)
        if not (self._match(TokenType.EOL) or self._match(TokenType.EOF) or self._match(TokenType.COMMENT)):
            node.add_child(self._parse_expression())
        self._end_statement()
        return node

    def _parse_say_statement(self) -> SayStatement:
        say_token = self._expect(TokenType.KEYWORD, 'say')
        node = SayStatement(say_token)
        node.add_child(self._parse_expression())
        self._end_statement()
        return node

    def _parse_ask_statement(self) -> AskStatement:
        ask_token = self._expect(TokenType.KEYWORD, 'ask')
        node = AskStatement(ask_token)
        node.variable = self._consume().value if self._match(TokenType.IDENTIFIER) else None
        self._end_statement()
        return node

    def _skip_list_newlines(self):
        while self._match(TokenType.EOL) or self._match(TokenType.COMMENT):
            self.pos += 1

    def _parse_menu_statement(self) -> MenuStatement:
        menu_token = self._expect(TokenType.KEYWORD, 'menu')
        # The result variable is optional: an identifier is the variable only
        # when the option list follows it (menu choice "A", "B" / menu choice [...]),
        # otherwise it is the first option (menu a, b)
        variable = None
        if self._match(TokenType.IDENTIFIER) and self._starts_option_list(self._peek(1)):
            variable = self._consume().value
        items = []

        if self._match(TokenType.PUNCTUATION, '['):
            self._consume()
            self._skip_list_newlines()
            while not self._match(TokenType.PUNCTUATION, ']'):
                items.append(self._parse_expression())
                self._skip_list_newlines()
                if not self._match(TokenType.PUNCTUATION, ','):
                    break
                self._consume()
                self._skip_list_newlines()
            self._expect(TokenType.PUNCTUATION, ']')
        else:
            items.append(self._parse_expression())
            while self._match(TokenType.PUNCTUATION, ','):
                self._consume()
                items.append(self._parse_expression())

        if not items:
            self._error("A menu needs at least one option", menu_token)
        self._end_statement()

        node = MenuStatement(menu_token)
        node.variable = variable
        node.items = items
        return node

    @staticmethod
    def _starts_option_list(token: Token) -> bool:
        if token.type in (TokenType.STRING, TokenType.NUMBER, TokenType.IDENTIFIER):
            return True
        if token.type == TokenType.PUNCTUATION:
            return token.value == '['
        if token.type == TokenType.KEYWORD:
            return token.value in ('true', 'false', 'not')
        if token.type == TokenType.OPERATOR:
            return token.value in ('-', '!')
        return False

    def _parse_filtermenu_statement(self) -> FilterMenuStatement:
        menu_token = self._expect(TokenType.KEYWORD, 'filtermenu')
        variable = self._consume().value if self._match(TokenType.IDENTIFIER) else None
        self._expect(TokenType.PUNCTUATION, '[')
        self._skip_list_newlines()

        items = []
        flags = []
        while not self._match(TokenType.PUNCTUATION, ']'):
            items.append(self._parse_expression())
            self._skip_list_newlines()
            self._expect(TokenType.PUNCTUATION, ',', what="',' followed by the option's condition")
            self._skip_list_newlines()
            flags.append(self._parse_expression())
            self._skip_list_newlines()
            if not self._match(TokenType.PUNCTUATION, ','):
                break
            self._consume()
            self._skip_list_newlines()
        self._expect(TokenType.PUNCTUATION, ']')

        if not items:
            self._error("A filtermenu needs at least one option", menu_token)
        self._end_statement()

        node = FilterMenuStatement(menu_token)
        node.variable = variable
        node.items = items
        node.flags = flags
        return node

    def _parse_goto_statement(self) -> GotoStatement:
        goto_token = self._expect(TokenType.KEYWORD, 'goto')
        node = GotoStatement(goto_token)
        node.label = self._expect(TokenType.IDENTIFIER, what="label name").value
        self._end_statement()
        return node

    def _parse_label_statement(self) -> LabelStatement:
        label_token = self._expect(TokenType.KEYWORD, 'label')
        node = LabelStatement(label_token)
        node.name = self._expect(TokenType.IDENTIFIER, what="label name").value
        self._end_statement()
        return node

    def _parse_exit_statement(self) -> ExitStatement:
        exit_token = self._expect(TokenType.KEYWORD, 'exit')
        self._end_statement()
        return ExitStatement(exit_token)

    # -- expressions --------------------------------------------------------

    def _parse_expression(self) -> Expression:
        return self._parse_logical_or()

    def _parse_binary(self, operand, operators, token_type=TokenType.OPERATOR) -> Expression:
        left = operand()
        while self._peek().type == token_type and self._peek().value in operators:
            node = BinaryOperation(self._consume())
            node.left = left
            node.right = operand()
            left = node
        return left

    def _parse_logical_or(self):
        return self._parse_binary(self._parse_logical_and, {'or'}, TokenType.KEYWORD)

    def _parse_logical_and(self):
        return self._parse_binary(self._parse_equality, {'and'}, TokenType.KEYWORD)

    def _parse_equality(self):
        return self._parse_binary(self._parse_comparison, {'==', '!='})

    def _parse_comparison(self):
        return self._parse_binary(self._parse_additive, {'<', '>', '<=', '>='})

    def _parse_additive(self):
        return self._parse_binary(self._parse_multiplicative, {'+', '-'})

    def _parse_multiplicative(self):
        return self._parse_binary(self._parse_unary, {'*', '/', '%'})

    def _parse_unary(self) -> Expression:
        if self._match(TokenType.OPERATOR, '-') or self._match(TokenType.OPERATOR, '!') \
                or self._match(TokenType.KEYWORD, 'not'):
            node = UnaryOperation(self._consume())
            node.op = 'not' if node.token.value in ('!', 'not') else '-'
            node.operand = self._parse_unary()
            return node
        return self._parse_postfix()

    def _parse_postfix(self) -> Expression:
        left = self._parse_primary()

        while True:
            if self._match(TokenType.PUNCTUATION, '['):
                bracket = self._consume()
                node = ArrayAccess(bracket)
                node.array = left
                node.index = self._parse_expression()
                self._expect(TokenType.PUNCTUATION, ']')
                left = node

            elif self._match(TokenType.PUNCTUATION, '('):
                paren = self._consume()
                if not isinstance(left, Identifier) or left.parenthesized:
                    self._error("Only named functions can be called", paren)
                node = FunctionCall(left.token)
                node.name = left.name
                node.arguments = []
                self._skip_list_newlines()
                while not self._match(TokenType.PUNCTUATION, ')'):
                    node.arguments.append(self._parse_expression())
                    self._skip_list_newlines()
                    if not self._match(TokenType.PUNCTUATION, ','):
                        break
                    self._consume()
                    self._skip_list_newlines()
                self._expect(TokenType.PUNCTUATION, ')')
                left = node
            else:
                return left

    def _parse_primary(self) -> Expression:
        token = self._peek()

        if token.type == TokenType.NUMBER:
            node = Literal(self._consume())
            node.value = int(token.value)
            return node

        if token.type == TokenType.STRING:
            node = Literal(self._consume())
            node.value = token.value
            return node

        if token.type == TokenType.KEYWORD and token.value in ('true', 'false'):
            node = Literal(self._consume())
            node.value = token.value == 'true'
            return node

        if token.type == TokenType.IDENTIFIER:
            node = Identifier(self._consume())
            node.name = token.value
            return node

        if token.type == TokenType.PUNCTUATION and token.value == '(':
            self._consume()
            expr = self._parse_expression()
            self._expect(TokenType.PUNCTUATION, ')')
            expr.parenthesized = True
            return expr

        if token.type == TokenType.PUNCTUATION and token.value == '[':
            return self._parse_array_literal()

        self._error(f"Unexpected {self._describe(token)} in expression", token)

    def _parse_array_literal(self) -> ArrayLiteral:
        node = ArrayLiteral(self._expect(TokenType.PUNCTUATION, '['))
        node.elements = []
        self._skip_list_newlines()
        while not self._match(TokenType.PUNCTUATION, ']'):
            node.elements.append(self._parse_expression())
            self._skip_list_newlines()
            if not self._match(TokenType.PUNCTUATION, ','):
                break
            self._consume()
            self._skip_list_newlines()
        self._expect(TokenType.PUNCTUATION, ']')
        return node


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

class Builtin:
    """An imported function called with CALLI.

    `order` is how the arguments are pushed:
      'engine'  - like the original game: last argument first, so the first
                  argument sits right below the argument count.
      'console' - first argument first (what the fantasy console expects).
    `engine_args` maps the UWScript argument order to the engine's order.
    `import_name` is the name in the conversation's import table (the game
    looks functions up by name), `returns` is 'int', 'string' or 'void'.
    """

    def __init__(self, func_id: int, min_args: int, max_args: Optional[int] = None,
                 order: str = 'engine', engine_args: Optional[tuple] = None,
                 import_name: Optional[str] = None, returns: Optional[str] = None):
        self.id = func_id
        self.min_args = min_args
        self.max_args = min_args if max_args is None else max_args
        self.order = order
        self.engine_args = engine_args
        engine_name, engine_returns = IMPORTED_FUNCTIONS.get(func_id, (None, 'int'))
        self.import_name = import_name or engine_name
        self.returns = returns or (engine_returns if order == 'engine' else 'int')


def _uw(name: str, min_args: int, max_args: Optional[int] = None, **kwargs) -> Builtin:
    return Builtin(FUNCTION_IDS[name], min_args, max_args, **kwargs)


def _console(func_id: int, name: str, min_args: int, max_args: Optional[int] = None) -> Builtin:
    return Builtin(func_id, min_args, max_args, order='console', import_name=f"console_{name}")


# UWScript name -> overloads (chosen by the number of arguments)
BUILTINS: Dict[str, List[Builtin]] = {
    # Ultima Underworld: strings and dialogue
    'print': [_uw('print', 1), _console(107, 'print', 4)],
    'compare': [_uw('compare', 2)],
    'contains': [_uw('contains', 2)],
    'string_length': [_uw('length', 1)],
    'sex': [_uw('sex', 2)],
    # Ultima Underworld: quests, randomness and the world
    'random': [_uw('random', 1)],
    'get_quest': [_uw('get_quest', 1)],
    # UWScript: set_quest(quest, value); the engine takes (value, quest)
    'set_quest': [_uw('set_quest', 2, engine_args=(1, 0))],
    'gronk_door': [_uw('gronk_door', 3)],
    'place_object': [_uw('place_object', 3)],
    'remove_talker': [_uw('remove_talker', 0)],
    'set_attitude': [_uw('set_attitude', 2)],
    'set_race_attitude': [_uw('set_race_attitude', 1, 3)],
    'x_skills': [_uw('x_skills', 2)],
    'x_traps': [_uw('x_traps', 2)],
    'x_obj_stuff': [_uw('x_obj_stuff', 9)],
    # Ultima Underworld: inventory and bartering
    'show_inv': [_uw('show_inv', 2)],
    'give_to_npc': [_uw('give_to_npc', 2)],
    'give_ptr_npc': [_uw('give_ptr_npc', 2)],
    'take_from_npc': [_uw('take_from_npc', 1)],
    'take_id_from_npc': [_uw('take_id_from_npc', 1)],
    'take_from_npc_inv': [_uw('take_from_npc_inv', 1)],
    'identify_inv': [_uw('identify_inv', 4)],
    'do_offer': [_uw('do_offer', 5, 7)],
    'do_demand': [_uw('do_demand', 2)],
    'do_inv_create': [_uw('do_inv_create', 1)],
    'do_inv_delete': [_uw('do_inv_delete', 1)],
    'check_inv_quality': [_uw('check_inv_quality', 1)],
    'set_inv_quality': [_uw('set_inv_quality', 2)],
    'count_inv': [_uw('count_inv', 1)],
    'setup_to_barter': [_uw('setup_to_barter', 0)],
    'do_judgement': [_uw('do_judgement', 0)],
    'do_decline': [_uw('do_decline', 0)],
    'set_likes_dislikes': [_uw('set_likes_dislikes', 2)],
    'find_inv': [_uw('find_inv', 2)],
    'find_barter': [_uw('find_barter', 1)],
    'find_barter_total': [_uw('find_barter_total', 4)],

    # Fantasy console: graphics
    'clear_screen': [_console(100, 'clear_screen', 0, 1)],
    'set_pixel': [_console(101, 'set_pixel', 3)],
    'draw_line': [_console(102, 'draw_line', 5)],
    'draw_rect': [_console(103, 'draw_rect', 5)],
    'fill_rect': [_console(104, 'fill_rect', 5)],
    'draw_circle': [_console(105, 'draw_circle', 4)],
    'draw_sprite': [_console(106, 'draw_sprite', 3)],
    'fill_circle': [_console(108, 'fill_circle', 4)],
    'flip_display': [_console(109, 'flip_display', 0)],
    'get_pixel': [_console(110, 'get_pixel', 2)],
    # Fantasy console: sound, input, math, system
    'play_tone': [_console(200, 'play_tone', 3)],
    'is_key_pressed': [_console(300, 'is_key_pressed', 1)],
    'is_key_released': [_console(301, 'is_key_released', 1)],
    'math_sin': [_console(501, 'math_sin', 1)],
    'math_cos': [_console(502, 'math_cos', 1)],
    'math_sqrt': [_console(503, 'math_sqrt', 1)],
    'delay': [_console(900, 'delay', 1)],
    'get_frame': [_console(901, 'get_frame', 0)],
}

BABL_MENU = FUNCTION_IDS['babl_menu']
BABL_FMENU = FUNCTION_IDS['babl_fmenu']
BABL_ASK = FUNCTION_IDS['babl_ask']
# Fantasy console / UWScript VM only: expands a string template now and
# returns the id of the resulting text
FREEZE_STRING = 600

ARITHMETIC_OPS = {'+': 'OPADD', '-': 'OPSUB', '*': 'OPMUL', '/': 'OPDIV', '%': 'OPMOD'}
COMPARISON_OPS = {'==': 'TSTEQ', '!=': 'TSTNE', '<': 'TSTLT', '>': 'TSTGT', '<=': 'TSTLE', '>=': 'TSTGE'}
COMPOUND_OPS = {'+=': 'OPADD', '-=': 'OPSUB', '*=': 'OPMUL', '/=': 'OPDIV', '%=': 'OPMOD'}


class HiddenSlot:
    """A compiler-owned global memory slot whose address is fixed at the end."""

    def __init__(self, pool: str, index: int):
        self.pool = pool
        self.index = index
        self.addr: Optional[int] = None

    def __int__(self):
        if self.addr is None:
            raise RuntimeError("Hidden slot address not resolved")
        return self.addr


class Loc:
    """A variable location: an absolute address or an offset from the frame pointer."""

    def __init__(self, frame: bool, value):
        self.frame = frame
        self.value = value

    def plus(self, offset: int) -> 'Loc':
        return Loc(self.frame, self.value + offset)


class SubstRef(tuple):
    """A text substitution (@GI12, @SS0, ...) inside a string template."""

    def __new__(cls, source: str, kind: str, num):
        return super().__new__(cls, (source, kind, num))

    def render(self) -> str:
        source, kind, num = self
        return f"@{source}{kind}{int(num)}"


class Symbol:
    def __init__(self, name: str, kind: str, offset: int, size: int = 1,
                 dims: Optional[List[int]] = None, vtype: str = 'int', elem_type: str = 'int'):
        self.name = name
        self.kind = kind          # 'global', 'game', 'local' or 'param'
        self.offset = offset      # global index, game global address, frame offset or parameter offset
        self.size = size
        self.dims = dims          # array dimensions, None for scalars
        self.vtype = vtype        # 'int' or 'string' (scalars)
        self.elem_type = elem_type

    @property
    def is_array(self) -> bool:
        return self.dims is not None


class TempPool:
    """Stack-discipline allocator for short-lived slots."""

    def __init__(self):
        self.top = 0
        self.high = 0

    def alloc(self, count: int) -> int:
        start = self.top
        self.top += count
        self.high = max(self.high, self.top)
        return start

    def free(self, start: int):
        self.top = start


class FunctionInfo:
    def __init__(self, node: FunctionDefinition):
        self.node = node
        self.name = node.name
        self.params = node.parameters
        self.symbols: Dict[str, Symbol] = {}
        self.local_size = 0
        self.temps = TempPool()
        self.labels = set()
        self.return_type = None   # computed lazily

        count = len(self.params)
        for i, param in enumerate(self.params):
            # Frame: [arg0 .. argN-1] [return address] [saved BP] <- BP, locals at BP+1..
            # so argument i is at PUSHI_EFF -(1 + N - i).
            self.symbols[param] = Symbol(param, 'param', -(1 + count - i))

    @property
    def label(self) -> str:
        return f"fn_{self.name}"

    @property
    def frame_size(self) -> int:
        return self.local_size + self.temps.high


class CodeGenerator:
    """Generates UW assembly from a UWScript AST."""

    def __init__(self, source_name: Optional[str] = None, target: str = 'uw'):
        if target not in TARGETS:
            raise UWScriptError(f"Unknown target '{target}' (use one of: {', '.join(TARGETS)})")
        self.source_name = source_name
        self.target = target
        self.loop_depth = 0
        self.string_block = 1
        self.out: list = []
        self.main_code: list = []
        self.function_code: list = []
        self.label_counter = 0

        # strings[0] is reserved: string id 0 terminates menu lists
        self.strings: list = [None]
        self.string_ids: Dict[tuple, int] = {}

        self.globals: Dict[str, Symbol] = {}
        self.global_size = 0
        self.functions: Dict[str, FunctionInfo] = {}
        self.main_labels = set()
        self.scope: Optional[FunctionInfo] = None

        self.main_temps = TempPool()
        self.main_temp_slots: Dict[int, HiddenSlot] = {}
        self.snapshot_slots: List[HiddenSlot] = []
        self.warnings: List[str] = []

        # Game globals (play_name, npc_attitude, ...) are predefined variables
        self.game_globals: Dict[str, Symbol] = {
            name: Symbol(name, 'game', GAME_GLOBAL_ADDRESSES[name], vtype=vtype)
            for name, vtype, _ in GAME_GLOBALS}
        self.used_game_globals = set()
        self.used_functions: Dict[int, tuple] = {}   # CALLI id -> (import name, return type)

    # -- entry point --------------------------------------------------------

    def generate(self, ast: Program, string_block: int = 1) -> str:
        self.string_block = string_block
        self._collect(ast)

        self.out = self.main_code
        self.scope = None
        self._emit("START")
        for stmt in ast.children:
            if not isinstance(stmt, FunctionDefinition):
                self._gen_statement(stmt)
        self._emit("EXIT_OP")

        for info in self.functions.values():
            self._gen_function(info)

        self._layout_hidden_slots()
        return self._format_code()

    # -- pass 1: symbols, labels, types -------------------------------------

    def _collect(self, ast: Program):
        main_statements = []
        for stmt in ast.children:
            if isinstance(stmt, FunctionDefinition):
                if stmt.name in BUILTINS:
                    raise UWScriptError(f"'{stmt.name}' is a built-in function and cannot be redefined", stmt.line)
                if stmt.name in self.game_globals:
                    raise UWScriptError(f"'{stmt.name}' is a game global and cannot be a function name", stmt.line)
                if stmt.name in self.functions:
                    raise UWScriptError(f"Function '{stmt.name}' is already defined", stmt.line)
                self.functions[stmt.name] = FunctionInfo(stmt)
            else:
                main_statements.append(stmt)

        self._collect_labels(main_statements, self.main_labels)
        for info in self.functions.values():
            self._collect_labels(info.node.body, info.labels)

        # Declarations are collected twice: the second round sees the
        # parameter types inferred from the call sites.
        for _ in range(2):
            for info in self.functions.values():
                info.return_type = None
            self.scope = None
            self._collect_declarations(main_statements)
            for info in self.functions.values():
                self.scope = info
                self._collect_declarations(info.node.body)
            self._infer_parameter_types(ast)
        self.scope = None

        if GLOBALS_BASE + self.global_size > MAX_MEMORY_SLOTS:
            raise UWScriptError(f"Global variables need {self.global_size} memory slots, "
                                f"but only {MAX_MEMORY_SLOTS - GLOBALS_BASE} are available")

    def _collect_labels(self, statements, labels: set):
        for stmt in self._walk_statements(statements):
            if isinstance(stmt, LabelStatement):
                if stmt.name in labels:
                    raise UWScriptError(f"Label '{stmt.name}' is defined more than once", stmt.line)
                labels.add(stmt.name)

    def _walk_statements(self, statements):
        for stmt in statements:
            yield stmt
            if isinstance(stmt, IfStatement):
                yield from self._walk_statements(stmt.true_branch)
                yield from self._walk_statements(stmt.false_branch)
            elif isinstance(stmt, WhileStatement):
                yield from self._walk_statements(stmt.body)

    def _collect_declarations(self, statements):
        for stmt in self._walk_statements(statements):
            if isinstance(stmt, VariableDeclaration):
                self._declare(stmt.name, stmt.children[0] if stmt.children else None, stmt)
            elif isinstance(stmt, (AskStatement, MenuStatement, FilterMenuStatement)) and stmt.variable:
                vtype = 'string' if isinstance(stmt, AskStatement) else 'int'
                if stmt.variable in self.game_globals:
                    continue
                # Like an assignment, these write an existing global from inside a function
                if self.scope and stmt.variable not in self.scope.symbols and stmt.variable in self.globals:
                    if vtype == 'string':
                        self.globals[stmt.variable].vtype = 'string'
                    continue
                self._declare(stmt.variable, None, stmt, vtype=vtype)

    def _declare(self, name: str, init, stmt, vtype: Optional[str] = None):
        if name in BUILTINS or name in self.functions:
            raise UWScriptError(f"'{name}' is a function name and cannot be used as a variable", stmt.line)
        if name in self.game_globals:
            raise UWScriptError(f"'{name}' is a game global; assign it without 'let'", stmt.line)
        table = self.scope.symbols if self.scope else self.globals

        if isinstance(init, ArrayLiteral):
            dims, leaves = self._array_shape(init)
            elem_type = 'string' if all(self._expr_type(leaf) == 'string' for leaf in leaves) else 'int'
            existing = table.get(name)
            if existing is not None:
                if existing.kind == 'param':
                    raise UWScriptError(f"Parameter '{name}' cannot be redeclared as an array", stmt.line)
                if existing.dims != dims:
                    raise UWScriptError(f"'{name}' is already declared with a different size", stmt.line)
                existing.elem_type = elem_type
                return
            table[name] = Symbol(name, self._new_kind(), self._allocate(len(leaves)),
                                 size=len(leaves), dims=dims, elem_type=elem_type)
            return

        if vtype is None:
            vtype = self._expr_type(init)
        existing = table.get(name)
        if existing is not None:
            if existing.is_array:
                raise UWScriptError(f"'{name}' is already declared as an array", stmt.line)
            if vtype == 'string' or isinstance(stmt, AskStatement):
                existing.vtype = vtype
            return
        table[name] = Symbol(name, self._new_kind(), self._allocate(1), vtype=vtype)

    def _new_kind(self) -> str:
        return 'local' if self.scope else 'global'

    def _allocate(self, size: int) -> int:
        if self.scope:
            offset = 1 + self.scope.local_size   # BP + 0 holds the saved frame pointer
            self.scope.local_size += size
        else:
            offset = self.global_size
            self.global_size += size
        return offset

    def _array_shape(self, node: ArrayLiteral):
        """Return (dims, leaves) of a (possibly nested) array literal."""
        if not node.elements:
            raise UWScriptError("Arrays must have at least one element", node.line)
        nested = [isinstance(e, ArrayLiteral) for e in node.elements]
        if all(nested):
            shapes = [self._array_shape(e) for e in node.elements]
            inner = shapes[0][0]
            if any(s[0] != inner for s in shapes):
                raise UWScriptError("All rows of a nested array must have the same size", node.line)
            return [len(node.elements)] + inner, [leaf for s in shapes for leaf in s[1]]
        if any(nested):
            raise UWScriptError("Array elements must be all values or all arrays", node.line)
        return [len(node.elements)], list(node.elements)

    def _infer_parameter_types(self, ast: Program):
        """A parameter is a string if any call passes a string to it."""
        def visit(node, scope):
            if node is None or not isinstance(node, ASTNode):
                return
            if isinstance(node, FunctionCall):
                info = self.functions.get(node.name)
                if info and len(node.arguments) == len(info.params):
                    saved, self.scope = self.scope, scope
                    for param, arg in zip(info.params, node.arguments):
                        if self._expr_type(arg) == 'string':
                            info.symbols[param].vtype = 'string'
                    self.scope = saved
            for child in self._child_nodes(node):
                visit(child, scope)

        for stmt in ast.children:
            if isinstance(stmt, FunctionDefinition):
                for body_stmt in stmt.body:
                    visit(body_stmt, self.functions[stmt.name])
            else:
                visit(stmt, None)

    @staticmethod
    def _child_nodes(node):
        children = list(node.children)
        for attr in ('left', 'right', 'operand', 'array', 'index', 'condition', 'target'):
            value = getattr(node, attr, None)
            if isinstance(value, ASTNode):
                children.append(value)
        for attr in ('arguments', 'elements', 'items', 'flags', 'true_branch', 'false_branch', 'body'):
            children.extend(getattr(node, attr, None) or [])
        return children

    # -- symbol lookup and types --------------------------------------------

    def _lookup(self, name: str) -> Optional[Symbol]:
        if self.scope and name in self.scope.symbols:
            return self.scope.symbols[name]
        if name in self.globals:
            return self.globals[name]
        return self.game_globals.get(name)

    def _require(self, name: str, node) -> Symbol:
        sym = self._lookup(name)
        if sym is None:
            if name in self.functions or name in BUILTINS:
                raise UWScriptError(f"'{name}' is a function; call it with parentheses", node.line)
            raise UWScriptError(f"Variable '{name}' is not defined (declare it with 'let')", node.line)
        return sym

    def _expr_type(self, node) -> str:
        if isinstance(node, Literal):
            return 'string' if node.token.type == TokenType.STRING else 'int'
        if isinstance(node, Identifier):
            sym = self._lookup(node.name)
            return sym.vtype if sym and not sym.is_array else 'int'
        if isinstance(node, ArrayAccess):
            base = node
            depth = 0
            while isinstance(base, ArrayAccess):
                base = base.array
                depth += 1
            if isinstance(base, Identifier):
                sym = self._lookup(base.name)
                if sym and sym.is_array and depth == len(sym.dims):
                    return sym.elem_type
            return 'int'
        if isinstance(node, BinaryOperation) and node.token.value == '+':
            return 'string' if self._is_concat(node) else 'int'
        if isinstance(node, FunctionCall) and node.name in self.functions:
            return self._function_return_type(self.functions[node.name])
        if isinstance(node, FunctionCall) and node.name in BUILTINS:
            overloads = [b for b in BUILTINS[node.name] if b.min_args <= len(node.arguments) <= b.max_args]
            return 'string' if overloads and overloads[0].returns == 'string' else 'int'
        return 'int'

    def _function_return_type(self, info: FunctionInfo) -> str:
        if info.return_type is None:
            info.return_type = 'int'  # guards against recursion
            saved, self.scope = self.scope, info
            for stmt in self._walk_statements(info.node.body):
                if isinstance(stmt, ReturnStatement) and stmt.children \
                        and self._expr_type(stmt.children[0]) == 'string':
                    info.return_type = 'string'
            self.scope = saved
        return info.return_type

    def _concat_parts(self, node) -> list:
        if isinstance(node, BinaryOperation) and node.token.value == '+' and not node.parenthesized:
            return self._concat_parts(node.left) + self._concat_parts(node.right)
        return [node]

    def _is_concat(self, node) -> bool:
        if not (isinstance(node, BinaryOperation) and node.token.value == '+'):
            return False
        parts = self._concat_parts(node) if not node.parenthesized else \
            self._concat_parts(node.left) + self._concat_parts(node.right)
        return any(self._expr_type(p) == 'string' for p in parts)

    # -- locations ----------------------------------------------------------

    def _loc(self, sym: Symbol) -> Loc:
        if sym.kind == 'global':
            return Loc(False, GLOBALS_BASE + sym.offset)
        if sym.kind == 'game':
            self.used_game_globals.add(sym.name)
            return Loc(False, sym.offset)
        return Loc(True, sym.offset)

    def _alloc_temps(self, count: int) -> int:
        pool = self.scope.temps if self.scope else self.main_temps
        return pool.alloc(count)

    def _free_temps(self, start: int):
        pool = self.scope.temps if self.scope else self.main_temps
        pool.free(start)

    def _temp_loc(self, index: int) -> Loc:
        if self.scope:
            return Loc(True, 1 + self.scope.local_size + index)
        slot = self.main_temp_slots.get(index)
        if slot is None:
            slot = self.main_temp_slots[index] = HiddenSlot('temp', index)
        return Loc(False, slot)

    def _new_snapshot_slot(self) -> Loc:
        slot = HiddenSlot('snapshot', len(self.snapshot_slots))
        self.snapshot_slots.append(slot)
        return Loc(False, slot)

    def _emit_addr(self, loc: Loc):
        self._emit("PUSHI_EFF" if loc.frame else "PUSHI", loc.value)

    def _subst_ref(self, loc: Loc, vtype: str) -> SubstRef:
        kind = 'S' if vtype == 'string' else 'I'
        return SubstRef('S' if loc.frame else 'G', kind, loc.value)

    # -- strings ------------------------------------------------------------

    def _intern(self, parts: list) -> int:
        merged = []
        for part in parts:
            if isinstance(part, str) and not isinstance(part, SubstRef):
                if merged and type(merged[-1]) is str:
                    merged[-1] += part
                    continue
            merged.append(part)
        key = tuple(merged)
        if key not in self.string_ids:
            self.string_ids[key] = len(self.strings)
            self.strings.append(key)
        return self.string_ids[key]

    def _render_string(self, key) -> str:
        if key is None:
            return ""
        return ''.join(part.render() if isinstance(part, SubstRef) else part for part in key)

    @property
    def string_literals(self) -> List[str]:
        return [self._render_string(key) for key in self.strings]

    # -- emit helpers -------------------------------------------------------

    def _emit(self, op: str, arg=None):
        self.out.append(('op', op, arg))

    def _emit_label(self, name: str):
        self.out.append(('label', name))

    def _emit_comment(self, text: str):
        self.out.append(('comment', text))

    def _new_label(self, hint: str) -> str:
        self.label_counter += 1
        return f"L{self.label_counter}_{hint}"

    # -- statements ---------------------------------------------------------

    def _gen_statement(self, node):
        if isinstance(node, VariableDeclaration):
            sym = self._require(node.name, node)
            if not node.children:
                return  # a saved global keeps its value
            init = node.children[0]
            if isinstance(init, ArrayLiteral):
                self._gen_array_init(sym, init)
            else:
                self._emit_addr(self._loc(sym))
                self._gen_expr(init, freeze=self._uses_target(init, node.name, element=False))
                self._emit("STO")

        elif isinstance(node, Assignment):
            self._gen_assignment(node)

        elif isinstance(node, IfStatement):
            else_label = self._new_label("else")
            end_label = self._new_label("endif")
            self._gen_expr(node.condition)
            self._emit("BEQ", else_label if node.false_branch else end_label)
            for stmt in node.true_branch:
                self._gen_statement(stmt)
            if node.false_branch:
                self._emit("JMP", end_label)
                self._emit_label(else_label)
                for stmt in node.false_branch:
                    self._gen_statement(stmt)
            self._emit_label(end_label)

        elif isinstance(node, WhileStatement):
            start_label = self._new_label("while")
            end_label = self._new_label("endwhile")
            self._emit_label(start_label)
            self._gen_expr(node.condition)
            self._emit("BEQ", end_label)
            self.loop_depth += 1
            for stmt in node.body:
                self._gen_statement(stmt)
            self.loop_depth -= 1
            self._emit("JMP", start_label)
            self._emit_label(end_label)

        elif isinstance(node, FunctionCall):
            self._gen_call(node, want_value=False)

        elif isinstance(node, ReturnStatement):
            if node.children:
                self._gen_expr(node.children[0])
            else:
                self._emit("PUSHI", 0)
            self._emit_return()

        elif isinstance(node, SayStatement):
            self._gen_expr(node.children[0], immediate=True)
            self._emit("SAY_OP")

        elif isinstance(node, AskStatement):
            self._use_function(BABL_ASK, 'babl_ask', 'int')
            self._emit("PUSHI", 0)
            self._emit("CALLI", BABL_ASK)
            self._emit("POP")
            if node.variable:
                self._store_result(node.variable, node)

        elif isinstance(node, MenuStatement):
            self._gen_menu(node)

        elif isinstance(node, FilterMenuStatement):
            self._gen_filtermenu(node)

        elif isinstance(node, GotoStatement):
            labels = self.scope.labels if self.scope else self.main_labels
            if node.label not in labels:
                where = f"function '{self.scope.name}'" if self.scope else "the main program"
                raise UWScriptError(f"Label '{node.label}' is not defined in {where}", node.line)
            self._emit("JMP", self._user_label(node.label))

        elif isinstance(node, LabelStatement):
            self._emit_label(self._user_label(node.name))

        elif isinstance(node, ExitStatement):
            self._emit("EXIT_OP")

        elif isinstance(node, FunctionDefinition):
            raise UWScriptError("Functions can only be defined at the top level of a program", node.line)

        else:
            raise UWScriptError(f"Unsupported statement {type(node).__name__}", node.line)

    def _user_label(self, name: str) -> str:
        # '.' cannot appear in identifiers, so labels of different scopes never clash
        return f"{self.scope.label}.{name}" if self.scope else f"lbl_{name}"

    def _store_result(self, name: str, node):
        """Store the result register in a variable."""
        self._emit_addr(self._loc(self._require(name, node)))
        self._emit("PUSH_REG")
        self._emit("STO")

    def _emit_return(self):
        self._emit("SAVE_REG")
        self._emit("BPTOSP")
        self._emit("POPBP")
        self._emit("RET")

    def _gen_array_init(self, sym: Symbol, init: ArrayLiteral):
        _, leaves = self._array_shape(init)
        base = self._loc(sym)
        for i, leaf in enumerate(leaves):
            self._emit_addr(base.plus(i))
            self._gen_expr(leaf)
            self._emit("STO")

    def _gen_assignment(self, node: Assignment):
        value = node.children[0]
        op = node.operator
        target = node.target

        if isinstance(value, ArrayLiteral):
            raise UWScriptError("Array literals can only be used with 'let'", node.line)

        if isinstance(target, Identifier):
            sym = self._require(target.name, target)
            if sym.is_array:
                raise UWScriptError(f"Cannot assign to array '{sym.name}' directly; assign its elements",
                                    node.line)
            loc = self._loc(sym)
            self._emit_addr(loc)
            if op == '=':
                self._gen_expr(value, freeze=self._uses_target(value, target.name, element=False))
            elif op == '+=' and (sym.vtype == 'string' or self._expr_type(value) == 'string'):
                self._gen_expr(self._append_node(node, target, value), freeze=True)
            else:
                self._emit_addr(loc)
                self._emit("FETCHM")
                self._gen_expr(value)
                self._emit(COMPOUND_OPS[op])
            self._emit("STO")
            return

        # Array element
        base = target
        while isinstance(base, ArrayAccess):
            base = base.array
        base_name = base.name if isinstance(base, Identifier) else None

        if op == '=':
            self._gen_target_address(target)
            self._gen_expr(value, freeze=self._uses_target(value, base_name, element=True))
            self._emit("STO")
            return

        if op == '+=' and (self._expr_type(target) == 'string' or self._expr_type(value) == 'string'):
            self._gen_target_address(target)
            self._gen_expr(self._append_node(node, target, value), freeze=True)
            self._emit("STO")
            return

        temp = self._alloc_temps(1)
        temp_loc = self._temp_loc(temp)
        self._emit_addr(temp_loc)
        self._gen_target_address(target)
        self._emit("STO")
        self._emit_addr(temp_loc)
        self._emit("FETCHM")
        self._emit_addr(temp_loc)
        self._emit("FETCHM")
        self._emit("FETCHM")
        self._gen_expr(value)
        self._emit(COMPOUND_OPS[op])
        self._emit("STO")
        self._free_temps(temp)

    def _gen_target_address(self, target: ArrayAccess):
        if not self._gen_element_address(target):
            raise UWScriptError("Cannot assign to a whole row of an array; index all dimensions", target.line)

    @staticmethod
    def _append_node(node, target, value) -> BinaryOperation:
        concat = BinaryOperation(Token(TokenType.OPERATOR, '+', node.token.line, node.token.column))
        concat.left = target
        concat.right = value
        return concat

    def _uses_target(self, value, name, element: bool) -> bool:
        """True if a string join assigned to variable `name` (or one of its
        elements) reads that same target (s = s + "x")."""
        if name is None or not (isinstance(value, BinaryOperation) and self._is_concat(value)):
            return False
        for operand in self._concat_parts(value.left) + self._concat_parts(value.right):
            base = operand
            while isinstance(base, ArrayAccess):
                base = base.array
            if isinstance(base, Identifier) and base.name == name \
                    and isinstance(operand, ArrayAccess) == element:
                return True
        return False

    def _gen_menu(self, node: MenuStatement):
        count = len(node.items)
        block = self._alloc_temps(count + 1)
        for i, item in enumerate(node.items):
            self._emit_addr(self._temp_loc(block + i))
            self._gen_expr(item, immediate=True)
            self._emit("STO")
        self._emit_addr(self._temp_loc(block + count))
        self._emit("PUSHI", 0)
        self._emit("STO")

        self._emit_addr(self._temp_loc(block))
        self._emit("PUSHI", 1)
        self._use_function(BABL_MENU, 'babl_menu', 'int')
        self._emit("CALLI", BABL_MENU)
        self._emit("POP")
        self._emit("POP")
        self._free_temps(block)
        if node.variable:
            self._store_result(node.variable, node)

    def _gen_filtermenu(self, node: FilterMenuStatement):
        count = len(node.items)
        strings = self._alloc_temps(count + 1)
        flags = self._alloc_temps(count)
        for i, (item, flag) in enumerate(zip(node.items, node.flags)):
            self._emit_addr(self._temp_loc(strings + i))
            self._gen_expr(item, immediate=True)
            self._emit("STO")
            self._emit_addr(self._temp_loc(flags + i))
            self._gen_bool(flag)
            self._emit("STO")
        self._emit_addr(self._temp_loc(strings + count))
        self._emit("PUSHI", 0)
        self._emit("STO")

        # babl_fmenu(strings, flags): pushed last argument first
        self._emit_addr(self._temp_loc(flags))
        self._emit_addr(self._temp_loc(strings))
        self._emit("PUSHI", 2)
        self._use_function(BABL_FMENU, 'babl_fmenu', 'int')
        self._emit("CALLI", BABL_FMENU)
        self._emit("POP")
        self._emit("POP")
        self._emit("POP")
        self._free_temps(strings)
        if node.variable:
            self._store_result(node.variable, node)

    # -- functions ----------------------------------------------------------

    def _gen_function(self, info: FunctionInfo):
        self.scope = info
        body = []
        self.out = body
        for stmt in info.node.body:
            self._gen_statement(stmt)
        if not info.node.body or not isinstance(info.node.body[-1], ReturnStatement):
            self._emit("PUSHI", 0)
            self._emit_return()

        self.out = self.function_code
        self._emit_comment(f"function {info.name}({', '.join(info.params)})")
        self._emit_label(info.label)
        self._emit("PUSHBP")
        self._emit("SPTOBP")
        if info.frame_size:
            self._emit("PUSHI", info.frame_size)
            self._emit("ADDSP")
        self.function_code.extend(body)
        self.scope = None

    def _select_builtin(self, node: FunctionCall) -> Builtin:
        """The overload of a built-in function that matches the argument count"""
        count = len(node.arguments)
        overloads = BUILTINS[node.name]
        for builtin in overloads:
            if builtin.min_args <= count <= builtin.max_args:
                return builtin
        expected = ' or '.join(str(b.min_args) if b.min_args == b.max_args else f"{b.min_args} to {b.max_args}"
                               for b in overloads)
        raise UWScriptError(f"Function '{node.name}' expects {expected} argument(s), got {count}", node.line)

    def _use_function(self, func_id: int, name: str, returns: str):
        """Record an imported function for the conversation's import table"""
        self.used_functions[func_id] = (name, returns)

    def _gen_call(self, node: FunctionCall, want_value: bool):
        if node.name in BUILTINS:
            self._gen_builtin_call(node, self._select_builtin(node), want_value)
            return

        info = self.functions.get(node.name)
        if info is None:
            raise UWScriptError(f"Function '{node.name}' is not defined", node.line)
        if len(node.arguments) != len(info.params):
            raise UWScriptError(f"Function '{node.name}' expects {len(info.params)} argument(s), "
                                f"got {len(node.arguments)}", node.line)
        for arg in node.arguments:
            self._check_not_array_literal(arg)
            self._gen_expr(arg)
        self._emit("CALL", info.label)
        for _ in node.arguments:
            self._emit("POP")
        if want_value:
            self._emit("PUSH_REG")

    def _gen_builtin_call(self, node: FunctionCall, builtin: Builtin, want_value: bool):
        count = len(node.arguments)
        if builtin.order == 'console' and self.target != 'console':
            raise UWScriptError(f"'{node.name}' is a fantasy console function and does not exist in Ultima "
                                f"Underworld (compile with --target console)", node.line)
        if want_value and builtin.returns == 'void':
            raise UWScriptError(f"'{node.name}' does not return a value", node.line)
        self._use_function(builtin.id, builtin.import_name, builtin.returns)

        # Every argument is passed by reference (a pointer to its value)
        block = self._alloc_temps(count)
        pointers = []
        for i, arg in enumerate(node.arguments):
            self._check_not_array_literal(arg)
            sym = self._lookup(arg.name) if isinstance(arg, Identifier) else None
            if sym is not None and not sym.is_array:
                pointers.append(self._loc(sym))
            elif sym is not None and builtin.order == 'engine':
                pointers.append(self._loc(sym))  # engine functions take arrays directly
            else:
                loc = self._temp_loc(block + i)
                self._emit_addr(loc)
                self._gen_expr(arg)
                self._emit("STO")
                pointers.append(loc)

        if builtin.order == 'engine':
            order = list(builtin.engine_args) if builtin.engine_args else list(range(count))
            for i in reversed(order):
                self._emit_addr(pointers[i])
        else:
            for loc in pointers:
                self._emit_addr(loc)

        self._emit("PUSHI", count)
        self._emit("CALLI", builtin.id)
        for _ in range(count + 1):
            self._emit("POP")
        self._free_temps(block)
        if want_value:
            self._emit("PUSH_REG")

    @staticmethod
    def _check_not_array_literal(node):
        if isinstance(node, ArrayLiteral):
            raise UWScriptError("Array literals can only be used with 'let'", node.line)

    # -- expressions --------------------------------------------------------

    def _gen_expr(self, node, immediate: bool = False, freeze: bool = False):
        """Push the value of an expression.

        `immediate` is set when the value is displayed right away (say and
        menu options), so string templates may refer to variables directly
        instead of snapshotting them.
        """
        if isinstance(node, Literal):
            if node.token.type == TokenType.STRING:
                self._emit("PUSHI", self._intern([node.value]))
            elif isinstance(node.value, bool):
                self._emit("PUSHI", 1 if node.value else 0)
            else:
                self._emit("PUSHI", node.value)

        elif isinstance(node, Identifier):
            sym = self._require(node.name, node)
            self._emit_addr(self._loc(sym))
            if not sym.is_array:
                self._emit("FETCHM")

        elif isinstance(node, ArrayAccess):
            if self._gen_element_address(node):
                self._emit("FETCHM")

        elif isinstance(node, FunctionCall):
            self._gen_call(node, want_value=True)

        elif isinstance(node, UnaryOperation):
            self._gen_expr(node.operand)
            self._emit("OPNEG" if node.op == '-' else "OPNOT")

        elif isinstance(node, BinaryOperation):
            self._gen_binary(node, immediate, freeze)

        elif isinstance(node, ArrayLiteral):
            raise UWScriptError("Array literals can only be used with 'let'", node.line)

        else:
            raise UWScriptError(f"Unsupported expression {type(node).__name__}", node.line)

    def _gen_binary(self, node: BinaryOperation, immediate: bool, freeze: bool = False):
        op = node.token.value

        if op == '+' and self._is_concat(node):
            self._gen_concat(node, immediate, freeze)
            return

        if op in ('and', 'or'):
            self._gen_bool(node.left)
            self._gen_bool(node.right)
            self._emit("OPAND" if op == 'and' else "OPOR")
            return

        if op in ('==', '!=') and self._expr_type(node.left) == 'string' \
                and self._expr_type(node.right) == 'string':
            call = FunctionCall(node.token)
            call.name = 'compare'
            call.arguments = [node.left, node.right]
            self._gen_call(call, want_value=True)
            if op == '!=':
                self._emit("OPNOT")
            return

        for side in (node.left, node.right):
            if self._expr_type(side) == 'string':
                raise UWScriptError(f"Operator '{op}' cannot be used with a string "
                                    f"(use parentheses for arithmetic inside text: \"n=\" + (x - 1))", node.line)
        self._gen_expr(node.left)
        self._gen_expr(node.right)
        if op in ARITHMETIC_OPS:
            self._emit(ARITHMETIC_OPS[op])
        elif op in COMPARISON_OPS:
            self._emit(COMPARISON_OPS[op])
        else:
            raise UWScriptError(f"Unsupported operator '{op}'", node.line)

    def _is_boolean(self, node) -> bool:
        if isinstance(node, Literal):
            return isinstance(node.value, bool) or node.value in (0, 1)
        if isinstance(node, UnaryOperation):
            return node.op == 'not'
        if isinstance(node, BinaryOperation):
            return node.token.value in COMPARISON_OPS or node.token.value in ('and', 'or')
        return False

    def _gen_bool(self, node):
        """Push 0 or 1."""
        self._gen_expr(node)
        if not self._is_boolean(node):
            self._emit("PUSHI", 0)
            self._emit("TSTNE")

    def _gen_concat(self, node: BinaryOperation, immediate: bool, freeze: bool = False):
        """Build a string template with text substitutions and push its id.

        Values that are not plain variables are evaluated into hidden global
        slots. Outside of say/menu every value is copied (snapshotted), so a
        stored string keeps showing the values from when it was built.
        """
        parts = []
        operands = self._concat_parts(node.left) + self._concat_parts(node.right) \
            if node.parenthesized else self._concat_parts(node)
        for operand in operands:
            if isinstance(operand, Literal):
                if operand.token.type == TokenType.STRING:
                    parts.append(operand.value)
                elif isinstance(operand.value, bool):
                    parts.append('1' if operand.value else '0')
                else:
                    parts.append(str(operand.value))
                continue

            vtype = self._expr_type(operand)
            sym = self._lookup(operand.name) if isinstance(operand, Identifier) else None
            if immediate and sym is not None and not sym.is_array:
                parts.append(self._subst_ref(self._loc(sym), sym.vtype))
                continue

            slot = self._new_snapshot_slot()
            self._emit_addr(slot)
            self._gen_expr(operand)
            self._emit("STO")
            parts.append(self._subst_ref(slot, vtype))
            if self.scope and isinstance(operand, FunctionCall) and operand.name == self.scope.name \
                    and vtype == 'string':
                freeze = True   # a recursive call returns this same template

        string_id = self._intern(parts)
        if not freeze or immediate:
            self._emit("PUSHI", string_id)
            return

        # The template would refer to itself the next time this line runs.
        if self.target != 'console':
            may_repeat = self.loop_depth > 0 or self.scope is not None or bool(self.main_labels)
            if may_repeat:
                raise UWScriptError(
                    "A string built from itself (s += \"x\", s = s + ..., or a recursive join) only works "
                    "once in Ultima Underworld, but this line can run again (it is in a loop, a function or "
                    "a program with labels). Build the text in one expression, or compile with --target "
                    "console", node.line)
            self._emit("PUSHI", string_id)
            return

        # The fantasy console VM can expand the template into a new string now.
        temp = self._alloc_temps(1)
        temp_loc = self._temp_loc(temp)
        self._emit_addr(temp_loc)
        self._emit("PUSHI", string_id)
        self._emit("STO")
        self._emit_addr(temp_loc)
        self._emit("PUSHI", 1)
        self._use_function(FREEZE_STRING, 'freeze_string', 'int')
        self._emit("CALLI", FREEZE_STRING)
        self._emit("POP")
        self._emit("POP")
        self._free_temps(temp)
        self._emit("PUSH_REG")

    def _gen_element_address(self, node: ArrayAccess) -> bool:
        """Push the address of an array element.

        Returns False when the address is a whole row of a multi-dimensional
        array (the value is then the row's address, not an element).
        """
        indices = []
        base = node
        while isinstance(base, ArrayAccess):
            indices.insert(0, base.index)
            base = base.array
        if not isinstance(base, Identifier) or base.parenthesized:
            raise UWScriptError("Only variables can be indexed", node.line)
        sym = self._require(base.name, base)

        if not sym.is_array:
            # The variable holds the address of an array (e.g. an array parameter)
            if len(indices) != 1:
                raise UWScriptError(f"'{sym.name}' is not a declared array; only one index is allowed",
                                    node.line)
            self._emit_addr(self._loc(sym))
            self._emit("FETCHM")
            self._gen_expr(indices[0])
            self._emit("OPADD")
            return True

        dims = sym.dims
        if len(indices) > len(dims):
            raise UWScriptError(f"Too many indices for '{sym.name}' ({len(dims)} dimension(s))", node.line)
        strides = [1] * len(dims)
        for k in range(len(dims) - 2, -1, -1):
            strides[k] = strides[k + 1] * dims[k + 1]

        constant = 0
        dynamic = []
        for k, index in enumerate(indices):
            if isinstance(index, Literal) and isinstance(index.value, int) and not isinstance(index.value, bool):
                if index.value >= dims[k]:
                    raise UWScriptError(f"Index {index.value} is out of bounds for '{sym.name}' "
                                        f"(size {dims[k]})", node.line)
                constant += index.value * strides[k]
            elif isinstance(index, UnaryOperation) and index.op == '-' and isinstance(index.operand, Literal):
                raise UWScriptError(f"Negative index for '{sym.name}'", node.line)
            else:
                dynamic.append((index, strides[k]))

        self._emit_addr(self._loc(sym).plus(constant))
        for index, stride in dynamic:
            self._gen_expr(index)
            if stride != 1:
                self._emit("PUSHI", stride)
                self._emit("OPMUL")
            self._emit("OPADD")
        return len(indices) == len(dims)

    # -- output -------------------------------------------------------------

    def _layout_hidden_slots(self):
        temp_base = GLOBALS_BASE + self.global_size
        for index, slot in self.main_temp_slots.items():
            slot.addr = temp_base + index
        snapshot_base = temp_base + self.main_temps.high
        for slot in self.snapshot_slots:
            slot.addr = snapshot_base + slot.index
        self.memory_end = snapshot_base + len(self.snapshot_slots)
        if self.memory_end > MAX_MEMORY_SLOTS:
            raise UWScriptError(f"The program needs {self.memory_end - GLOBALS_BASE} global memory slots, "
                                f"but only {MAX_MEMORY_SLOTS - GLOBALS_BASE} are available")

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')

    def _describe_symbol(self, sym: Symbol) -> str:
        if sym.is_array:
            shape = 'x'.join(str(d) for d in sym.dims)
            kind = f"array[{shape}] of {sym.elem_type}"
        else:
            kind = sym.vtype
        if sym.kind == 'global':
            return f"{GLOBALS_BASE + sym.offset} ({kind})"
        if sym.kind == 'game':
            return f"{sym.offset} (game global, {kind})"
        return f"{sym.offset} ({sym.kind}, {kind})"

    def _format_code(self) -> str:
        lines = ["; UWScript compiled to Ultima Underworld conversation assembly"]
        if self.source_name:
            lines.append(f"; Source: {self.source_name}")
        lines += [
            f"; String Block: {self.string_block}",
            f"; Memory Slots: {self.memory_end}",
            f"; Target: {'Ultima Underworld' if self.target == 'uw' else 'fantasy console'}",
            f"; Globals: game globals at 0-{len(GAME_GLOBALS) - 1}; {self.global_size} variable slot(s) and "
            f"{self.memory_end - GLOBALS_BASE - self.global_size} hidden slot(s) from {GLOBALS_BASE}",
            ";",
            "; Imported Functions/Variables:",
        ]
        index = 0
        for func_id in sorted(self.used_functions):
            name, returns = self.used_functions[func_id]
            lines.append(f"; Import {index}: Function {name}, ID: {func_id}, Returns: {returns}")
            index += 1
        for name in sorted(self.used_game_globals, key=GAME_GLOBAL_ADDRESSES.get):
            lines.append(f"; Import {index}: Variable {name}, Addr: 0x{GAME_GLOBAL_ADDRESSES[name]:04X}")
            index += 1
        lines += [";", "; Strings:"]
        for i, text in enumerate(self.string_literals):
            note = "  (reserved: menu terminator)" if i == 0 else ""
            lines.append(f'; {i}: "{self._escape(text)}"{note}')

        lines += [";", "; Global variables:"]
        for name, sym in self.globals.items():
            lines.append(f";   {name} -> {self._describe_symbol(sym)}")

        if self.functions:
            lines += [";", "; Functions (frame-relative offsets):"]
            for info in self.functions.values():
                lines.append(f";   {info.name}({', '.join(info.params)}): {info.frame_size} frame slot(s)")
                for name, sym in info.symbols.items():
                    lines.append(f";     {name} -> {self._describe_symbol(sym)}")
        lines.append("")

        for entry in self.main_code + self.function_code:
            if entry[0] == 'label':
                lines.append(f"{entry[1]}:")
            elif entry[0] == 'comment':
                lines.append("")
                lines.append(f"; {entry[1]}")
            else:
                _, op, arg = entry
                if arg is None:
                    lines.append(op)
                elif isinstance(arg, str):
                    lines.append(f"{op} {arg}")
                else:
                    lines.append(f"{op} {int(arg)}")
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API and command line
# ---------------------------------------------------------------------------

def generate_strings_file(strings: List[str], block_id: int) -> str:
    """Generate a UW-style string block file (the format of strings.pak dumps)."""
    output = ["STRINGS.PAK: 1 string blocks.", "", f"block: {block_id:04x}; {len(strings)} strings."]
    for i, text in enumerate(strings):
        output.append(f"{i}: {CodeGenerator._escape(text)}")
    output.append("")
    return "\n".join(output)


def compile_uwscript(source: str, block_id: int = 1, debug: bool = False,
                     source_name: Optional[str] = None, target: str = 'uw') -> Dict[str, str]:
    """Compile UWScript source code.

    `target` is 'uw' (default: only what the original game supports) or
    'console' (also the fantasy console functions).
    Returns a dict with the "assembly" and "strings" file contents and a
    list of warnings. Raises UWScriptError on errors.
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens, debug=debug).parse()
    generator = CodeGenerator(source_name, target)
    assembly = generator.generate(ast, block_id)
    return {
        "assembly": assembly,
        "strings": generate_strings_file(generator.string_literals, block_id),
        "warnings": list(dict.fromkeys(generator.warnings)),
    }


def default_output_paths(input_path: str, output: Optional[str] = None, strings: Optional[str] = None):
    """program.uws -> program.asm and program_strings.txt (next to the output)."""
    stem = os.path.splitext(input_path)[0]
    if output is None:
        output = stem + ".asm"
    if strings is None:
        base = stem if output == '-' else os.path.splitext(output)[0]
        strings = base + "_strings.txt"
    return output, strings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile UWScript (.uws) to Ultima Underworld conversation assembly.")
    parser.add_argument("input", help="UWScript source file (.uws)")
    parser.add_argument("-o", "--output", help="assembly output file (default: <input>.asm, '-' for stdout)")
    parser.add_argument("-s", "--strings", help="string block output file (default: <output>_strings.txt)")
    parser.add_argument("-b", "--block", type=int, default=1, help="string block id (default: 1)")
    parser.add_argument("-t", "--target", choices=TARGETS, default='uw',
                        help="'uw' (default): only what Ultima Underworld supports; "
                             "'console': also the fantasy console functions")
    parser.add_argument("-v", "--verbose", action="store_true", help="print the written files")
    parser.add_argument("--debug", action="store_true", help="print parser debug output and tracebacks")
    args = parser.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"Error reading {args.input}: {e}", file=sys.stderr)
        return 1

    output, strings = default_output_paths(args.input, args.output, args.strings)
    try:
        result = compile_uwscript(source, args.block, debug=args.debug,
                                  source_name=os.path.basename(args.input), target=args.target)
    except UWScriptError as e:
        print(f"{args.input}: error: {e}", file=sys.stderr)
        if args.debug:
            raise
        return 1

    for warning in result["warnings"]:
        print(f"{args.input}: warning: {warning}", file=sys.stderr)

    if output == '-':
        sys.stdout.write(result["assembly"])
    else:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result["assembly"])
    with open(strings, "w", encoding="utf-8") as f:
        f.write(result["strings"])

    if args.verbose:
        if output != '-':
            print(f"Assembly written to {output}")
        print(f"Strings written to {strings}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
