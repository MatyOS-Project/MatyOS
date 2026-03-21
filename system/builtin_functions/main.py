import math as _math
from utils.constants import TRUE, FALSE, OR, AND, INTEGER, REAL, STRING, BOOLEAN, FLOAT, REALISTIC

_builtin_input = input

_delta_for_floats = 1 / 1e8


class BuiltinFunctions:
    @staticmethod
    def print(*items):
        print(*items)

    @staticmethod
    def len(s):
        return len(str(s))

    @staticmethod
    def upper(s):
        return str(s).upper()

    @staticmethod
    def lower(s):
        return str(s).lower()

    @staticmethod
    def trim(s):
        return str(s).strip()

    @staticmethod
    def str(v):
        return str(v)

    @staticmethod
    def int(v):
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot convert '{v}' to integer")

    @staticmethod
    def float(v):
        try:
            return float(v)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot convert '{v}' to float")

    @staticmethod
    def abs(n):
        return abs(n)

    @staticmethod
    def max(a, b):
        return max(a, b)

    @staticmethod
    def min(a, b):
        return min(a, b)

    @staticmethod
    def sqrt(n):
        return _math.sqrt(n)

    @staticmethod
    def pow(base, exp):
        return base ** exp

    @staticmethod
    def mod(a, b):
        return a % b

    @staticmethod
    def type_of(v):
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, int):
            return "integer"
        if isinstance(v, float):
            return "float"
        if isinstance(v, str):
            if v in ("TRUE", "FALSE", "REALISTIC"):
                return "boolean"
            return "string"
        return "unknown"

    @staticmethod
    def is_integer(v):
        try:
            return TRUE if isinstance(v, int) and not isinstance(v, bool) else FALSE
        except Exception:
            return FALSE

    @staticmethod
    def is_string(v):
        return TRUE if isinstance(v, str) and v not in ("TRUE", "FALSE", "REALISTIC") else FALSE

    @staticmethod
    def input(prompt=""):
        return _builtin_input(str(prompt))


_builtin_functions = BuiltinFunctions()


def is_system_function(name):
    if hasattr(_builtin_functions, name):
        return True
    else:
        return False


def call_system_function(name, *args, **kwargs):
    func = getattr(_builtin_functions, name)
    return func(*args, *kwargs)


def evaluate_bool_expression(left, op, right):
    if op not in (OR, AND):
        raise ValueError('op not in or, and')
    if op is OR:
        return realistic_or(left, right)
    else:
        return realistic_and(left, right)


def not_bool(bool_val):
    if bool_val not in (TRUE, FALSE):
        raise ValueError("value error")

    if bool_val is TRUE:
        return FALSE
    return TRUE


def is_val_of_type(val, base_type):
    if base_type not in (INTEGER, FLOAT, REAL, STRING, BOOLEAN):
        raise ValueError('base_type must be int, float, real, str, or bool type')

    if val is None:
        return True

    if base_type == INTEGER:
        try:
            return isinstance(int(val), int) and str(val).count('.') == 0
        except Exception:
            return False
    elif base_type in (FLOAT, REAL):
        try:
            return isinstance(float(val), float)
        except Exception:
            return False
    elif base_type == STRING:
        return isinstance(val, str)
    elif base_type == BOOLEAN:
        try:
            if isinstance(val, str):
                return val.upper() in ("TRUE", "FALSE", "REALISTIC")
            return val in (TRUE, FALSE, REALISTIC)
        except Exception:
            return False
    return False


def not_equal(left, right):
    try:
        flag = left != right
        if flag is True:
            return TRUE
        return FALSE
    except Exception as e:
        return TRUE


def bool_or(left, right):
    try:
        return evaluate_bool_expression(left, OR, right)
    except Exception as e:
        return FALSE


def bool_and(left, right):
    try:
        return evaluate_bool_expression(left, AND, right)
    except Exception as e:
        return FALSE


def bool_greater_than(left, right):
    try:
        flag = int(left) > int(right) or (float(left) - float(right) > _delta_for_floats)
        if flag is True:
            return TRUE
        return FALSE
    except Exception as e:
        return FALSE


def bool_greater_than_or_equal(left, right):
    try:
        flag = int(left) >= int(right) and (float(left) - float(right) > -_delta_for_floats)
        if flag is True:
            return TRUE
        return FALSE
    except Exception as e:
        return FALSE


def bool_less_than(left, right):
    try:
        flag = int(left) < int(right) or (float(left) - float(right) < -_delta_for_floats)
        if flag is True:
            return TRUE
        return FALSE
    except Exception as e:
        return FALSE


def bool_less_than_or_equal(left, right):
    try:
        flag = int(left) <= int(right) and (float(left) - float(right) < _delta_for_floats)
        if flag is True:
            return TRUE
        return FALSE
    except Exception as e:
        return FALSE


def bool_is_equal(left, right):
    """Enhanced equality for realistic values"""
    try:
        # Handle realistic comparisons
        if isinstance(left, str) and left == REALISTIC:
            return realistic_equal(left, right)
        if isinstance(right, str) and right == REALISTIC:
            return realistic_equal(left, right)
        
        # Normal comparison
        flag = left == right
        if flag is True:
            return TRUE
        return FALSE
    except Exception as e:
        return REALISTIC  # When uncertain, return realistic

def realistic_not(bool_val):
    """NOT operation for three-valued logic"""
    if bool_val == TRUE:
        return FALSE
    elif bool_val == FALSE:
        return TRUE
    elif bool_val == REALISTIC:
        return REALISTIC  # NOT realistic = realistic
    else:
        raise ValueError("Invalid boolean value for NOT operation")

def realistic_or(left, right):
    """OR operation for three-valued logic"""
    # Truth table for realistic OR:
    # TRUE OR anything = TRUE
    # FALSE OR FALSE = FALSE
    # FALSE OR REALISTIC = REALISTIC
    # FALSE OR TRUE = TRUE
    # REALISTIC OR REALISTIC = REALISTIC
    
    if left == TRUE or right == TRUE:
        return TRUE
    elif left == FALSE and right == FALSE:
        return FALSE
    elif left == REALISTIC or right == REALISTIC:
        return REALISTIC
    else:
        raise ValueError("Invalid boolean values for OR operation")

def realistic_and(left, right):
    """AND operation for three-valued logic"""
    # Truth table for realistic AND:
    # FALSE AND anything = FALSE
    # TRUE AND TRUE = TRUE
    # TRUE AND REALISTIC = REALISTIC
    # TRUE AND FALSE = FALSE
    # REALISTIC AND REALISTIC = REALISTIC
    
    if left == FALSE or right == FALSE:
        return FALSE
    elif left == TRUE and right == TRUE:
        return TRUE
    elif left == REALISTIC or right == REALISTIC:
        return REALISTIC
    else:
        raise ValueError("Invalid boolean values for AND operation")

def realistic_equal(left, right):
    """Equality comparison with realistic values"""
    if left == right:
        return TRUE
    elif left == REALISTIC or right == REALISTIC:
        return REALISTIC  # Uncertain equality
    else:
        return FALSE

def realistic_not_equal(left, right):
    """Not equal comparison with realistic values"""
    equality_result = realistic_equal(left, right)
    return realistic_not(equality_result)
def bool_not_equal(left, right):
    """Enhanced not equal for realistic values"""
    try:
        equality_result = bool_is_equal(left, right)
        if equality_result == REALISTIC:
            return REALISTIC
        return realistic_not(equality_result)
    except Exception as e:
        return REALISTIC