from SciQLop.backend.common import insort, pipeline, Maybe, Thunk, Something, Nothing, lift
from functools import partial


def test_insort():
    l = [1, 3, 5, 7, 9]
    insort(l, 4)
    assert l == [1, 3, 4, 5, 7, 9]
    insort(l, 0)
    assert l == [0, 1, 3, 4, 5, 7, 9]
    insort(l, 10)
    assert l == [0, 1, 3, 4, 5, 7, 9, 10]
    insort(l, 10)
    assert l == [0, 1, 3, 4, 5, 7, 9, 10, 10]
    insort(l, 0)
    assert l == [0, 0, 1, 3, 4, 5, 7, 9, 10, 10]


def test_pipeline():
    def add(x, y):
        return x + y

    def multiply(x, y):
        return x * y

    def subtract(x, y):
        return x - y

    p = pipeline(add, partial(multiply, 2), lambda x: subtract(x, 2))
    assert p(1, 2) == Something(4)
    assert p(3, 4) == Something(12)
    assert p(1,Nothing()) == Nothing()


def test_thunk():
    def add(x, y):
        return x + y

    def multiply(x, y):
        return x * y

    def subtract(x, y):
        return x - y

    t = Thunk(add, 1, 2)
    assert t() == 3
    t = Thunk(multiply, 2, 3)
    assert t() == 6
    t = Thunk(subtract, 5, 2)
    assert t() == 3

def test_lift():
    def add(x, y):
        return x + y

    def multiply(x, y):
        return x * y

    def subtract(x, y):
        return x - y

    lifted_add = lift(add)
    lifted_multiply = lift(multiply)
    lifted_subtract = lift(subtract)

    assert lifted_add(1, 2) == Something(3)
    assert lifted_multiply(2, 3) == Something(6)
    assert lifted_subtract(5, 2) == Something(3)
    assert lifted_add(1, Nothing()) == Nothing()
    assert lifted_add(1, None) == Nothing()


