from easy_z3 import Solver

class _(Solver):
    a: int
    b: int
    c: int

    assert (a > 0) & (b > 0) & (c > 0)
    assert a ** 3 + b ** 3 == c ** 3

print("extra lazy", _) # pretty print the model

print("wow so verbose", _.a, _.b, _.c) # access results directly

()=_ # dump variables into globals
print("mmmm clean", a, b, c)