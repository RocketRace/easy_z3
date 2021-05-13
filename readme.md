# z3 made unreasonably easy

Have you ever thought, "I really need a constraint solver right now" and
remembered that the python wrapper for z3 (which is already very easy to use)
is not easy enough to use? No? That's fine, I made this anyway.

## Usage

```py

from easy_z3 import Solver

# solver instances are defined as classes 
class MySolver(Solver):
    # 4 kinds of declarations are supported right now
    n: int # integers
    x: float # reals
    b: bool # bools
    f: {(int, int), float} # functions

    # constraints are assertions in the class body
    assert n > 0
    # arithmetic and function call syntax just works (tm)
    assert f(n, n + 1) == -2 * x
    # &, |, ^ and ~ operate on booleans
    assert ~b & (f(n ** 2, 0) < x) ^ (n < 5)
    # x >> y and y << x are short for "x implies y"
    assert b >> (n == 2)

# z3 then finds a model satisfying the contraints
# (or crashes and burns if none exist)
# so easy! many wow

print(MySolver) # convenience measure for extra lazy

print(MySolver.n, MySolver.x) # directly address results

()=MySolver # magic syntax to dump results into the current scope
print(n, x, b) # such easy
```

## Why

Purely to make linters angry

## How

Metaclasses defining custom namespaces and special syntax, `inspect` to traverse stack frames and mess with globals, and plenty of glue to patch together some reasonable API to z3.

## License

GPLv3, see LICENSE
