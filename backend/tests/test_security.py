"""Unit tests for password hashing and code generation."""

from app.core.security import generate_code, hash_password, verify_password


def test_hash_is_salted_and_verifies():
    h1 = hash_password("s3cretpw!")
    h2 = hash_password("s3cretpw!")
    assert h1 != h2  # random salt per hash
    assert verify_password("s3cretpw!", h1)
    assert verify_password("s3cretpw!", h2)


def test_verify_rejects_wrong_password():
    h = hash_password("s3cretpw!")
    assert verify_password("not-it", h) is False


def test_verify_with_no_hash_is_false():
    # The dummy-hash path: unknown user -> always False, but still does work.
    assert verify_password("anything", None) is False


def test_generate_code_is_zero_padded_numeric():
    for _ in range(100):
        code = generate_code(4)
        assert len(code) == 4
        assert code.isdigit()


def test_generate_code_respects_length():
    assert len(generate_code(6)) == 6
