from SciQLop.core.unique_names import make_simple_incr_name


def test_simple_incr_name():
    assert make_simple_incr_name("test") == "test0"
    assert make_simple_incr_name("test") == "test1"
    assert make_simple_incr_name("test") == "test2"
    assert make_simple_incr_name("test", sep="_") == "test_3"
    assert make_simple_incr_name("another_test") == "another_test0"