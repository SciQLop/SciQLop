from SciQLop.backend.common import insort


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
