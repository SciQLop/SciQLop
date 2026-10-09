from SciQLop.core.unique_names import make_simple_incr_name, claim_name, release_name


def test_simple_incr_name():
    assert make_simple_incr_name("test") == "test0"
    assert make_simple_incr_name("test") == "test1"
    assert make_simple_incr_name("test") == "test2"
    assert make_simple_incr_name("test", sep="_") == "test_3"
    assert make_simple_incr_name("another_test") == "another_test0"

def test_claim_name_keeps_a_free_name():
    assert claim_name("claim_free") == "claim_free"
    release_name("claim_free")


def test_claim_name_suffixes_a_taken_name():
    assert claim_name("claim_taken") == "claim_taken"
    assert claim_name("claim_taken") == "claim_taken_1"
    assert claim_name("claim_taken") == "claim_taken_2"
    for n in ("claim_taken", "claim_taken_1", "claim_taken_2"):
        release_name(n)
