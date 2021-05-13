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

## No, but really. How

A metaclass (type inheriting from `type`) can return any mapping-like object from its `__prepare__` method, which will be used while executing the class body to access names within the class scope. For normal classes, this will be a `dict`. So in the following example, variable access is converted into dictionary access:

```py
class C:
    a = 1 # Adds `a` to the namespace
    a + 1 # Fetches `a` from the namespace
    b + 1 # NameError! `b` is not in the namespace
```

In the example, you notice that trying to access variables that aren't defined anywhere will raise a `NameError`. However, this is only the default behavior of the namespace! You can choose to ignore undefined variables totally when using a custom namespace, as long as you define the `__getitem__` and `__setitem__` methods used for reading & writing to the namespace. In fact, if the namespace is a subclass of `dict`, you can define a handy method `__missing__` that is called specifically when an unbound name is trying to be accessed!

In this module, the custom namespace (aptly named `NameSpace`) behaves exactly as `dict` does, except when unbound value are accessed. (Note: the code is full of jank and inconsistency. Don't be surprised if what I say slightly misrepresents its hackiness.) In those cases, it returns a `Variable` object.

The `Variable` class defines a whole ton of operator overloads, including arithmetic (`__add__`, for `+`) and comparison (`__eq__`, for `==`) operators. These overloads all have the same behavior; they simply build an AST from their behavior. In short, `a + b` evaluates to something like `BinOp(Variable("a"), Variable("b"), "__add__")`. Here, `BinOp` refers specifically to a binary operator. `Variable` also defines unary operators (`-`, `+` , `~`), and function call syntax `f(a, b, c, ...)`, which evaluate to `UnaryOp` and `Call` objects, respectively. That is to say, these expressions describe the program that wrote them. These AST objects all derive from `Value`, which is their base class and which defines most of these operators.

The `Value` class additionally defines a `__bool__` method. This method is called whenever an expression is evaluated for its "truthiness", e.g. in the condition of an `if` block or in the argument of `not x`. One specific scenario that calls `Variable.__bool__` is an assertion. Whenever `assert x` is executed, `x` is checked for truthiness, and if it is falsey, an `AssertionError` is raised. This module abuses this fact; whenever `__bool__` is called, the corresponding `Value` object is appended to a list of assertions in the encompassing class. The method then returns `True`, to make sure no errors are raised (we don't care about that behavior here).

One catch of using `__bool__` is that it can be called in a variety of contexts. We only want to consider the `assert` context, but unfortunately we have to deal with other ones too. One specific case that might come up is something like `a == b == c`, or operator chaining. In python, this is syntactic sugar for `(a == b) and (b == c)`. Since our `Value` objects return other `Value` objects when compared using `==`, and not booleans, this will call `__bool__` on the result of `a == b`. And we don't want that! It's totally possible that in the context of a constraint, we don't want to assert that a equals b. How do we avoid this?

The solution used here is to abuse the heck out of `inspect` and stack frames. Python runs on stack frames, and the `inspect` module lets you traverse down the stack to your caller. Messing around with it is, of course, dangerous, and can break programs. However, I have no dignity and have already demonstrated that I don't care about the sanctity of Python programs. The `__bool__` method will traverse to the previous stack frame (by getting the current frame via `inspect.getcurrentframe()` and diving down by accessing the `f_back` attribute of the resulting frame object). It then checks the last bytecode instruction executed by the Python interpreter in that stack frame (using the `f_lasti` and `f_code` attributes). If that instruction *isn't* `POP_JUMP_IF_TRUE`, which corresponds with an assertion plus a few other things we don't care about right now, the code raises a warning, helpfully instructing the user to stop doing bad things. (An eagle-eyed reader might notice that this is totally implementation-dependent, and not guaranteed to work in later python versions. To that I say, well, you're probably using a compatible version of `cpython`, so it's fiiiine. If you're for some reason trying to make this code work with PyPy or MicroPython or Jython or whatever, you probably have bigger issues.)

Once all the assertions have been collected, the program traverses the AST of each assertion and converts it to a z3 expression, using the class’s `__annotations__` to build the types. Because I’m lazy and have no standards, I do this by recursively evaluating operands, then calling `eval()` on the resulting strings of operators, something like this:

```py
def traverse(node):
    if isinstance(node, Variable):
        return str(node)
    if isinstance(node, BinOp):
        return eval(
            f"{traverse(node.left)} {node.op} {traverse(node.right)}"
        )
    # etc.
```

These constraints are then added to a `z3.Solver` instance, and the computation is handed off to `z3`. It does well enough for most use cases, especially considering this code only exposes a minute surface of its API (and is already full of hacky glue). 

Finally, the resulting class has a few extra methods that can be used to access the results from `z3`:

* The class’s `__repr__` returns a string of the solution model
* The class defines `__getattr__`, so any attribute access will fall back to accessing one of the variables in the solution
* The class defines `__iter__`, returning an empty iterator. It also has the side-effect of dumping every value into the globals of the scope it’s called in, once again by traversing down a stack frame. This allows you to access the variables directly without having to use the class as a proxy.

Overall, this project bullies Python a lot. I don’t usually condone bullying, but this is something I can get behind :>

## License

GPLv3, see LICENSE

## Contributing

If you feel the need?
