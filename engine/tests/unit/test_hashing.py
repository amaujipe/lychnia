import hashlib
import os

from lychnia.orchestrator.hashing import hash_file, hash_text


def test_small_file_is_full_sha256(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"hello")
    assert hash_file(p) == "sha256:" + hashlib.sha256(b"hello").hexdigest()
    assert hash_text("hello") == hash_file(p)


def test_large_mode_uses_size_mtime_and_edges(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(os.urandom(4096))
    h1 = hash_file(p, large_threshold=1024)
    assert h1.startswith("large:")
    assert hash_file(p, large_threshold=1024) == h1
    # a change in the middle of a huge file is invisible by design; a change at the edge is not
    data = bytearray(p.read_bytes())
    data[0] ^= 0xFF
    p.write_bytes(bytes(data))
    assert hash_file(p, large_threshold=1024) != h1


def test_large_mode_changes_with_size(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(b"x" * 3000)
    h1 = hash_file(p, large_threshold=1024)
    p.write_bytes(b"x" * 3001)
    assert hash_file(p, large_threshold=1024) != h1
