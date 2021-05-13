"""
This file is licensed under GPLv3. See the LICENSE file for more information.

See example.py for example usage.

See readme.md for more detailed documentation.
"""
from __future__ import annotations

import dis
import inspect
import warnings
import weakref
from typing import Any

import z3

__all__ = "Solver",

# implemented by object, not reversible
# (a == b) <-> (b == a)
COMPARISON_OPS = {
    "__eq__": "==",
    "__ne__": "!=",
    "__lt__": "<",
    "__le__": "<=",
    "__gt__": ">",
    "__ge__": ">=",
}
# by default not implemented, reversible
# (a + b) <-> a.__add__(b) <-> b.__radd__(a)
REVERSIBLE_BIN_OPS = {
    "__add__": "+",
    "__sub__": "-",
    "__mul__": "*",
    "__truediv__": "/",
    "__floordiv__": "//",
    # "__matmul__": "@",
    "__pow__": "**",
    "__mod__": "%",
    # These are interpreted as logical operators!
    "__and__": "&", # x and y
    "__or__": "|", # x or y
    "__xor__": "^", # x xor y
    "__rshift__": ">>", # x implies y
    "__lshift__": "<<", # y implies x
}

BIN_OPS = COMPARISON_OPS | REVERSIBLE_BIN_OPS

UNARY_OPS = {
    "__pos__": "+",
    "__neg__": "-",
    # These are interpreted as logical operators!
    "__invert__": "~", # not x
}

class ValueMeta(type):
    def __init__(cls, name: str, bases: tuple[type, ...], ns: dict[str, Any]):
        for attr in BIN_OPS:
            # default value needs to be used to ensure the right value of attr is used
            def bin_op(left: Value, right: Any, op: str=attr) -> Binop:
                # left ns needs to be chosen since right arg can be anything
                return Binop(left, right, op, ns=left.ns)
            setattr(cls, attr, bin_op)
        for attr in REVERSIBLE_BIN_OPS:
            def rbin_op(left: Value, right: Any, op: str=attr) -> Binop:
                # left ns needs to be chosen since right arg can be anything
                return Binop(right, left, op, ns=left.ns)
            setattr(cls, attr.replace("__", "__r", 1), rbin_op)          
        for attr in UNARY_OPS:
            def un_op(arg: Value, op: str=attr) -> Unop:
                return Unop(arg, op, ns=arg.ns)
            setattr(cls, attr, un_op)

class Value(metaclass=ValueMeta):
    def __init__(self, *, ns: weakref.ref[Namespace]):
        self.ns = ns
    def __bool__(self):
        frame = inspect.currentframe().f_back
        last_op = frame.f_code.co_code[frame.f_lasti]
        if dis.opname[last_op] != "POP_JUMP_IF_TRUE":
            warnings.warn("`__bool__` called on expression outside of assertion!\nUse `~` instead of `not`, `&` instead of `and`, `|` instead of `or`\nChained comparison operators (e.g. `x == y == z`) are also not supported.")
        self.ns().assertion(self)
        return True

class Unop(Value):
    def __repr__(self):
        return f"({UNARY_OPS[self.op]}{self.arg})"
    def __init__(self, arg: Value, op: str, **kwargs):
        self.arg = arg
        self.op = op
        super().__init__(**kwargs)

class Binop(Value):
    def __repr__(self):
        return f"({self.left} {BIN_OPS[self.op]} {self.right})"
    def __init__(self, left: Value, right: Value, op: str, **kwargs):
        self.op = op
        self.left = left
        self.right = right
        super().__init__(**kwargs)

class Call(Value):
    def __repr__(self):
        return f"({self.fn}({', '.join(map(repr, self.args))}))"
    def __init__(self, fn: Variable, *args: Value, **kwargs):
        self.fn = fn
        self.args = args
        super().__init__(**kwargs)

class Variable(Value):
    def __repr__(self):
        return self.var
    def __init__(self, var: str, **kwargs):
        self.var = var
        super().__init__(**kwargs)
    def __call__(self, *args: Value):
        return Call(self, *args, ns=self.ns)

class Namespace(dict):
    def __init__(self, *args, **kwds):
        self.assertions: list[Value] = []
        super().__init__(self, *args, **kwds)
    def __getitem__(self, key: str):
        try:
            x = super().__getitem__(key)
        except KeyError:
            if key in ("__name__", "__annotations__"):
                raise KeyError
            if key in globals():
                return globals()[key]
            try:
                import builtins
                return getattr(builtins, key)
            except AttributeError:
                return Variable(key, ns=weakref.ref(self))
        else:
            return x
    def assertion(self, value: Value):
        self.assertions.append(value)

class SolverMeta(type):
    @classmethod
    def __prepare__(cls, name: str, bases: tuple[type, ...]) -> Namespace:
        return Namespace()
    def __init__(cls, name: str, bases: tuple[type, ...], ns: Namespace):
        sorts = {bool: z3.BoolSort(), int: z3.IntSort(), float: z3.RealSort()}
        vars = {}
        try:
            for var, ann in cls.__annotations__.items():
                if isinstance(ann, str):
                    ann = eval(ann)
                if ann is bool:
                    vars[var] = z3.Bool(var)
                elif ann is int:
                    vars[var] = z3.Int(var)
                elif ann is float:
                    vars[var] = z3.Real(var)
                elif isinstance(ann, dict):
                    in_sort, out_sort = next(iter(ann.items()))
                    out_sort = sorts[out_sort]
                    if isinstance(in_sort, tuple):
                        in_sort = (sorts[x] for x in in_sort)
                        vars[var] = z3.Function(var, *in_sort, out_sort)
                    else:
                        in_sort = sorts[in_sort]
                        vars[var] = z3.Function(var, in_sort, out_sort)
        except:
            pass
        solver = z3.Solver()
        for term in ns.assertions:
            solver.add(traverse(term, vars))
        assert solver.check(), "Unsatisfiable constraints!"
        cls.__model = solver.model()
        cls.__vars = vars

    def __repr__(self):
        return repr(self.__model)
    
    def __iter__(self):
        g = inspect.currentframe().f_back.f_globals
        for x in self.__vars:
            g[x] = getattr(self, x)
        return iter(()for()in())

    def __getattr__(cls, attr):
        try:
            x = cls.__model[cls.__vars[attr]]
            if isinstance(x, z3.FuncInterp):
                pass
            else:
                if x.sort() == z3.BoolSort():
                    return bool(x)
                if x.sort() == z3.IntSort():
                    return x.as_long()
                if x.sort() == z3.RealSort():
                    if isinstance(x, z3.RatNumRef):
                        return float(x.as_fraction())
                    return float(x.approx().as_fraction())
            return x
        except Exception as e:
            raise AttributeError from e
    
def traverse(value: Value, vars: dict[str, Any]):
    if isinstance(value, Variable):
        return vars[value.var]
    elif isinstance(value, Unop):
        if value.op == "__invert__":
            return z3.Not(traverse(value.arg, vars))
        else:
            return eval(
                f"{UNARY_OPS[value.op]} (__arg)",
                {"__arg": traverse(value.arg, vars)}
            )
    elif isinstance(value, Binop):
        if value.op == "__and__":
            return z3.And(traverse(value.left, vars), traverse(value.right, vars))
        elif value.op == "__or__":
            return z3.Or(traverse(value.left, vars), traverse(value.right, vars))
        elif value.op == "__xor__":
            return z3.Xor(traverse(value.left, vars), traverse(value.right, vars))
        # don't mistake these two by accident
        elif value.op == "__rshift__":
            return z3.Implies(traverse(value.left, vars), traverse(value.right, vars))
        elif value.op == "__lshift__":
            return z3.Implies(traverse(value.right, vars), traverse(value.left, vars))
        else:
            return eval(
                f"(__left) {BIN_OPS[value.op]} (__right)",
                {
                    "__left": traverse(value.left, vars),
                    "__right": traverse(value.right, vars),
                }
            )
    elif isinstance(value, Call):
        return traverse(value.fn, vars)(*(traverse(arg, vars) for arg in value.args))
    else:
        return value

class Solver(metaclass=SolverMeta):
    pass
