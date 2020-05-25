#!/usr/bin/env python3
import math
import operator
import random
import re
import socket
import sys
from ast import literal_eval
from collections import deque
from typing import Optional


class ApplicationException(Exception):
    pass


CALC_STACK = deque()

OUTPUT_MODES = {
    'hex': hex,
    'dec': lambda x: str(x),
    'bin': bin,
    'oct': oct
}
CURRENT_OUTPUT_MODIFIER = OUTPUT_MODES['dec']

IS_SHOW_STACK_VERTICAL = False
MACROS = {}
VARIABLES = {}
VARIABLE_PATTERN = re.compile(r'^(\w+)=$')
DUPN_PATTERN = re.compile(r'^dup(\d+)$')
IS_OUTPUT_TO_TERMINAL = True


class Colors:
    RESET = '\033[0m'
    LIGHT_MAGENTA = '\033[95m'
    LIGHT_GREEN = '\033[92m'
    LIGHT_RED = '\033[91m'
    LIGHT_YELLOW = '\033[93m'
    LIGHT_CYAN = '\033[36m'


def get_color(color: str) -> str:
    return color if IS_OUTPUT_TO_TERMINAL else ''


def alert_message(msg: str):
    print(f'{get_color(Colors.LIGHT_RED)}{msg}{get_color(Colors.RESET)}', file=sys.stderr)


def set_current_output_modifier(mode: str):
    global CURRENT_OUTPUT_MODIFIER
    CURRENT_OUTPUT_MODIFIER = OUTPUT_MODES[mode]


def get_stack_representation() -> str:
    separator = ' ' if not IS_SHOW_STACK_VERTICAL else '\n'
    stack = f"{separator.join([CURRENT_OUTPUT_MODIFIER(x) for x in CALC_STACK])}"
    return f'{get_color(Colors.LIGHT_MAGENTA)}{stack}{get_color(Colors.RESET)}' if stack else ''


def build_line_prefix() -> str:
    color_reset = get_color(Colors.RESET)
    variables = ''
    if VARIABLES:
        yellow = get_color(Colors.LIGHT_YELLOW)
        variables = f"{yellow}[{', '.join([f'{x}={y}' for x, y in VARIABLES.items()])}]{color_reset}"
    raw_macros = ', '.join([f'{x}: {" ".join(y)}' for x, y in MACROS.items()])
    macros = f"{get_color(Colors.LIGHT_GREEN)}[{raw_macros}]{color_reset}" if MACROS else ''
    color_cyan = get_color(Colors.LIGHT_CYAN)
    return ' '.join(x for x in [variables, macros, get_stack_representation(), f'{color_cyan}>{color_reset} '] if x)


def get_repeat_commands(user_input: list, index_of_action_to_repeat: int) -> list:
    # check if number of repeat times is in stack and is integer
    if len(CALC_STACK) < 1:
        raise ApplicationException('Integer number of repeats is required')
    if index_of_action_to_repeat >= len(user_input):
        raise ApplicationException('Action to repeat is required after "repeat" command')
    repeats = CALC_STACK[-1]
    if repeats is None or repeats < 1 or int(repeats) != repeats:
        raise ApplicationException('Number of repeats should be a positive integer')
    action = user_input[index_of_action_to_repeat]
    return [action] * repeats


def set_macro_command(macro_input: list):
    if macro_input[0] in ACTIONS:
        raise ApplicationException(f'"{macro_input[0]}" is an internal command. Please choose another name')
    if not macro_input[0].isalpha():
        raise ApplicationException('Macro name should contain only ASCII alphabet characters')
    if 'macro' in macro_input[1:]:
        raise ApplicationException("You can't define macro inside a macro, this can possibly lead to endless loops")
    MACROS[macro_input[0]] = macro_input[1:]


def set_variable(variable_name: str):
    if variable_name in ACTIONS:
        raise ApplicationException(f'"{variable_name}" is an internal command. Please choose another name')
    if len(CALC_STACK) < 1:
        raise ApplicationException('No value to save as a variable')
    VARIABLES[variable_name] = CALC_STACK.pop()


def main_loop(args: Optional[str] = None):
    while True:
        raw_input = input(build_line_prefix()) if not args else args
        user_inputs = raw_input.strip().split(' ')
        i = 0
        while i < len(user_inputs):
            user_input = user_inputs[i]
            if user_input in VARIABLES:
                user_input = str(VARIABLES[user_input])
            i += 1
            try:
                if user_input == 'repeat':
                    repeated_commands = get_repeat_commands(user_inputs, i)
                    CALC_STACK.pop()
                    user_inputs = user_inputs[:i-1] + repeated_commands + user_inputs[i+1:]
                    i -= 1
                elif user_input == 'macro':
                    set_macro_command(user_inputs[i:])
                    break
                elif user_input in MACROS:
                    user_inputs = user_inputs[:i-1] + MACROS[user_input] + user_inputs[i:]
                    i -= 1
                elif VARIABLE_PATTERN.match(user_input):
                    # yeah, it's not python 3.8 to use the walrus operator :)
                    set_variable(VARIABLE_PATTERN.match(user_input)[1])
                elif DUPN_PATTERN.match(user_input):
                    duplicate_n_items_in_stack(int(DUPN_PATTERN.match(user_input)[1]))
                elif user_input in ACTIONS:
                    add_result_to_stack_if_not_none(ACTIONS[user_input]())
                else:
                    process_input_as_number(user_input)
            except ApplicationException as e:
                alert_message(str(e))
                break
            except ZeroDivisionError:
                alert_message('Zero division error')
                break
            except ValueError:
                alert_message('This operation is not possible with provided data')
                break
            except Exception as e:
                alert_message('This operation is not possible with provided data')
                break
        if args:
            print(get_stack_representation())
            break


def process_input_as_number(user_input: str):
    if user_input.startswith(('0b', '0x')):
        try:
            user_input = str(literal_eval(user_input)) # it's save as it evaluates only python literals, not expressions
        except SyntaxError:
            raise ApplicationException("Can't understand the input")
    try:
        res = int(user_input)
    except ValueError:
        try:
            res = float(user_input)
        except ValueError:
            raise ApplicationException("Can't understand the input")
    CALC_STACK.append(res)


def two_args_factory(action_function):
    def result():
        if len(CALC_STACK) > 1:
            right_arg = CALC_STACK.pop()
            left_arg = CALC_STACK.pop()
            return action_function(left_arg, right_arg)
        raise ApplicationException('This operation requires two arguments')
    return result


def one_arg_factory(action_function):
    def result():
        if len(CALC_STACK) > 0:
            arg = CALC_STACK.pop()
            return action_function(arg)
        raise ApplicationException('This operation requires one argument')
    return result

# stack functions


def add_result_to_stack_if_not_none(raw_res):
    if raw_res is not None:
        CALC_STACK.append(int(raw_res) if math.floor(raw_res) == raw_res else raw_res)


def clear_stack():
    CALC_STACK.clear()


def duplicate_stack():
    duplicate_n_items_in_stack(1)


def duplicate_n_items_in_stack(n: int):
    if len(CALC_STACK) < n:
        raise ApplicationException(f'There should be at least {n} value(s) in stack to duplicate')
    if n < 1:
        raise ApplicationException('Number of items to duplicate should be > 0')
    values_to_dup = [CALC_STACK.pop() for _ in range(n)] * 2
    CALC_STACK.extend(reversed(values_to_dup))


def roll_stack(n: int):
    CALC_STACK.rotate(n)


def roll_stack_down(n: int):
    CALC_STACK.rotate(n * -1)


def swap_top_two_items_in_stack(arg1, arg2):
    CALC_STACK.append(arg2)
    CALC_STACK.append(arg1)


def drop_n_items_from_stack(n: int):
    for i in range(n):
        CALC_STACK.pop()


def push_stack_depth():
    CALC_STACK.append(len(CALC_STACK))


def pick_nth_item(n: int):
    if n > len(CALC_STACK):
        return
    n -= 1
    item = CALC_STACK[n]
    del CALC_STACK[n]
    CALC_STACK.append(item)


def switch_stack_display():
    global IS_SHOW_STACK_VERTICAL
    IS_SHOW_STACK_VERTICAL = not IS_SHOW_STACK_VERTICAL

# end of stack functions


def clear_variables():
    global VARIABLES
    VARIABLES = {}


def clear_macros():
    global MACROS
    MACROS = {}


def clear_all():
    clear_stack()
    clear_variables()
    clear_macros()


def help_command():
    info = '''\
USAGE:

  rpn                          Launch in interactive mode
  rpn [expression]             Evaluate a one-line expression

EXAMPLES

  rpn 1 2 + 3 + 4 + 5 +              => 15
  rpn pi cos                         => -1.0
  rpn                                => interactive mode

ARITHMETIC OPERATORS

  +          Add
  -          Subtract
  *          Multiply
  /          Divide
  cla        Clear the stack and variables
  clr        Clear the stack
  clv        Clear the variables
  clm        Clear the macros
  !          Boolean NOT
  !=         Not equal to
  %          Modulus
  ++         Increment
  --         Decrement

Bitwise Operators

  &          Bitwise AND
  |          Bitwise OR
  ^          Bitwise XOR
  ~          Bitwise NOT
  <<         Bitwise shift left
  >>         Bitwise shift right

Boolean Operators

  &&         Boolean AND
  ||         Boolean OR
  ^^         Boolean XOR

Comparison Operators

  <          Less than
  <=         Less than or equal to
  ==         Equal to
  >          Greater than
  >=         Greater than or equal to

Trigonometric Functions

  acos       Arc Cosine
  asin       Arc Sine
  atan       Arc Tangent
  cos        Cosine
  cosh       Hyperbolic Cosine
  sin        Sine
  sinh       Hyperbolic Sine
  tanh       Hyperbolic tangent

Numeric Utilities

  ceil       Ceiling
  floor      Floor
  round      Round
  ip         Integer part
  fp         Floating part
  sign       Push -1, 0, or 0 depending on the sign
  abs        Absolute value
  max        Max
  min        Min

Display Modes

  hex        Switch display mode to hexadecimal
  dec        Switch display mode to decimal (default)
  bin        Switch display mode to binary
  oct        Switch display mode to octal

Constants

  e          Push e
  pi         Push Pi
  rand       Generate a random number

Mathematic Functions

  exp        Exponentiation
  fact       Factorial
  sqrt       Square Root
  ln         Natural Logarithm
  log        Logarithm
  pow        Raise a number to a power

Networking

  hnl        Host to network long
  hns        Host to network short
  nhl        Network to host long
  nhs        Network to host short

Stack Manipulation

  pick       Pick the -n'th item from the stack
  repeat     Repeat an operation n times, e.g. '3 repeat +'
  depth      Push the current stack depth
  drop       Drops the top item from the stack
  dropn      Drops n items from the stack
  dup        Duplicates the top stack item
  dupn       Duplicates the top n stack items in order
  roll       Roll the stack upwards by n
  rolld      Roll the stack downwards by n
  stack      Toggles stack display from horizontal to vertical
  swap       Swap the top 2 stack items

Macros and Variables

  macro      Defines a macro, e.g. 'macro kib 1024 *'
  x=         Assigns a variable, e.g. '1024 x='

Other

  help       Print the help message
  exit       Exit the calculator
'''
    print(info)


ACTIONS = {
    '+': two_args_factory(operator.add),
    '-': two_args_factory(operator.sub),
    '*': two_args_factory(operator.mul),
    '/': two_args_factory(operator.truediv),
    'cla': clear_all,
    'clr': clear_stack,
    'clv': clear_variables,
    'clm': clear_macros,
    '!': one_arg_factory(lambda x: not bool(x)),
    '!=': two_args_factory(operator.ne),
    '%': two_args_factory(operator.mod),
    '++': one_arg_factory(lambda x: x + 1),
    '--': one_arg_factory(lambda x: x - 1),

    '&': two_args_factory(operator.and_),
    '|': two_args_factory(operator.or_),
    '^': two_args_factory(operator.xor),
    '~': one_arg_factory(operator.not_),
    '<<': two_args_factory(operator.lshift),
    '>>': two_args_factory(operator.rshift),

    '&&': two_args_factory(lambda x, y: bool(x) and bool(y)),
    '||': two_args_factory(lambda x, y: bool(x) or bool(y)),
    '^^': two_args_factory(lambda x, y: bool(x) ^ bool(y)),

    '<': two_args_factory(operator.lt),
    '<=': two_args_factory(operator.le),
    '==': two_args_factory(operator.eq),
    '>': two_args_factory(operator.gt),
    '>=': two_args_factory(operator.ge),

    'acos': one_arg_factory(math.acos),
    'asin': one_arg_factory(math.asin),
    'atan': one_arg_factory(math.atan),
    'cos': one_arg_factory(math.cos),
    'cosh': one_arg_factory(math.cosh),
    'sin': one_arg_factory(math.sin),
    'sinh': one_arg_factory(math.sinh),
    'tanh': one_arg_factory(math.tanh),

    'ceil': one_arg_factory(math.ceil),
    'floor': one_arg_factory(math.floor),
    'round': one_arg_factory(round),
    'ip': one_arg_factory(lambda x: int(math.modf(x)[1])),
    'fp': one_arg_factory(lambda x: math.modf(x)[0]),
    'sign': one_arg_factory(lambda x: -1 if x < 0 else 0),
    'abs': one_arg_factory(abs),
    'max': two_args_factory(max),
    'min': two_args_factory(min),

    'hex': lambda: set_current_output_modifier('hex'),
    'dec': lambda: set_current_output_modifier('dec'),
    'bin': lambda: set_current_output_modifier('bin'),
    'oct': lambda: set_current_output_modifier('oct'),

    'e': lambda: math.e,
    'pi': lambda: math.pi,
    'rand': lambda: random.random(),

    'exp': one_arg_factory(math.exp),
    'fact': one_arg_factory(math.factorial),
    'sqrt': one_arg_factory(math.sqrt),
    'ln': one_arg_factory(math.log),
    'log': two_args_factory(math.log),
    'pow': two_args_factory(operator.pow),

    'hnl': one_arg_factory(socket.htonl),
    'hns': one_arg_factory(socket.htons),
    'nhl': one_arg_factory(socket.ntohl),
    'nhs': one_arg_factory(socket.ntohs),

    'pick': one_arg_factory(pick_nth_item),
    'repeat': lambda: None,
    'depth': push_stack_depth,
    'drop': lambda: drop_n_items_from_stack(1),
    'dropn': one_arg_factory(drop_n_items_from_stack),
    'dup': duplicate_stack,
    'dupn': one_arg_factory(duplicate_n_items_in_stack),
    'roll': one_arg_factory(roll_stack),
    'rolld': one_arg_factory(roll_stack_down),
    'stack': switch_stack_display ,
    'swap': two_args_factory(swap_top_two_items_in_stack),

    'macro': lambda: None,  # macro and repeat are implemented separately in the main loop
    'x=': lambda: None,

    'help': help_command,
    'exit': lambda: exit(),
}


if __name__ == '__main__':
    cmd_args = sys.argv[1:] if len(sys.argv) > 1 else []
    piped_args = [x.strip() for x in sys.stdin] if not sys.stdin.isatty() else []
    args = ' '.join(cmd_args + piped_args) if cmd_args or piped_args else None
    IS_OUTPUT_TO_TERMINAL = sys.stdout.isatty()
    if IS_OUTPUT_TO_TERMINAL or args:
        main_loop(args)
