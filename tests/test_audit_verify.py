import hashlib
from tasks_ai.audit import generate_audit, verify_audit


def test_md5_hashing_consistency(tmp_path):
    """Test that hashing files produces consistent MD5 hashes."""
    test_file = tmp_path / "test.txt"
    content = b"test content"
    test_file.write_bytes(content)

    expected_hash = hashlib.md5(content).hexdigest()

    with open(test_file, "rb") as f:
        actual_hash = hashlib.md5(f.read()).hexdigest()

    assert actual_hash == expected_hash


def test_generate_and_verify_audit(tmp_path):
    """Test full audit generation and verification cycle."""
    patch_file = tmp_path / "test.patch"
    audit_file = tmp_path / "test.audit"
    patch_content = b"diff --git a/file b/file"
    patch_file.write_bytes(patch_content)

    # Generate audit
    generate_audit("192", str(patch_file), str(audit_file))

    assert audit_file.exists()

    # Verify audit
    assert verify_audit(str(patch_file), str(audit_file))

    # Tamper with patch and verify should fail
    with open(patch_file, "wb") as f:
        f.write(b"tampered content")

    assert not verify_audit(str(patch_file), str(audit_file))
