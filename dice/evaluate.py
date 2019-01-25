"""
Safe math evaluator for Dice cog by PhasecoreX

Thanks to jfs here:
https://stackoverflow.com/questions/2371436/evaluating-a-mathematical-expression-in-a-string#9558001
Thanks to Daniel for safe_add and safe_mult here:
https://github.com/danthedeckie/simpleeval
"""
import ast
import operator as op

MAX_STRING_LENGTH = 100000


def safe_add(first, second):
    """Safely add two numbers (check resulting length)"""
    if len(str(first)) + len(str(second)) > MAX_STRING_LENGTH:
        raise KeyError
    return first + second


def safe_mult(first, second):
    """Safely multiply two numbers (check resulting length)"""
    if second * len(str(first)) > MAX_STRING_LENGTH:
        raise KeyError
    if first * len(str(second)) > MAX_STRING_LENGTH:
        raise KeyError
    return first * second


# supported operators
OPERATORS = {
    ast.Add: safe_add,
    ast.Sub: op.sub,
    ast.Mult: safe_mult,
    ast.Div: op.truediv,
    ast.USub: op.neg,
}


def eval_expr(expr):
    """Evaluate math problems safely"""
    return eval_(ast.parse(expr, mode="eval").body)


def eval_(node):
    """Do the evaluation."""
    if isinstance(node, ast.Num):  # <number>
        return node.n
    if isinstance(node, ast.BinOp):  # <left> <operator> <right>
        return OPERATORS[type(node.op)](eval_(node.left), eval_(node.right))
    if isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
        return OPERATORS[type(node.op)](eval_(node.operand))
    raise TypeError(node)
