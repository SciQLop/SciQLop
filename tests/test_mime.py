from SciQLop.mime import encode, decode


def test_can_encode_and_decode():
    assert decode(encode(["a", "b"])) == ["a", "b"]
