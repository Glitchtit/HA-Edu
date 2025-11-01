"""Test to verify teacher account password is correctly base64-encoded for Home Assistant compatibility."""
import json
import io
import contextlib
import types
import sys
import base64

from unittest.mock import patch

import pytest
import bcrypt


_initial_client = types.SimpleNamespace(containers=None, images=None)
with patch('docker.from_env', return_value=_initial_client):
    import app

from test_teacher_account_creation import (
    FakeContainer,
    FakeDockerClient,
    sample_storage
)


def test_password_can_be_validated_like_home_assistant(sample_storage):
    """Test that stored password can be validated using Home Assistant's method."""
    fake_container = FakeContainer(sample_storage.root)
    fake_client = FakeDockerClient(fake_container)

    original_client = app.client
    app.client = fake_client

    teacher_password = 'test_teacher_pass123'

    try:
        success, message = app.create_teacher_account('volume', 'teacher', teacher_password)
    finally:
        app.client = original_client

    assert success, message
    assert message == 'Teacher account created successfully'

    # Load the created provider data
    updated_provider = json.loads(sample_storage.provider_path.read_text())

    # Find the teacher's provider entry
    teacher_entry = None
    for user in updated_provider['data']['users']:
        if user.get('username') == 'teacher':
            teacher_entry = user
            break

    assert teacher_entry is not None, "Teacher entry not found in provider data"

    # Simulate Home Assistant's validate_login method
    # This is what Home Assistant does when checking a password:
    # 1. base64.b64decode the stored password
    # 2. bcrypt.checkpw to verify the password

    stored_password = teacher_entry['password']

    # Step 1: Base64 decode (this should not fail)
    try:
        user_hash = base64.b64decode(stored_password)
    except Exception as e:
        pytest.fail(f"Failed to base64 decode password: {e}")

    # Step 2: Verify the password with bcrypt
    # This simulates what Home Assistant does during login
    is_valid = bcrypt.checkpw(teacher_password.encode(), user_hash)

    assert is_valid, "Password validation failed - teacher would not be able to login"


def test_password_format_matches_home_assistant_expectations(sample_storage):
    """Test that password format exactly matches Home Assistant's storage format."""
    fake_container = FakeContainer(sample_storage.root)
    fake_client = FakeDockerClient(fake_container)

    original_client = app.client
    app.client = fake_client

    try:
        success, message = app.create_teacher_account('volume', 'admin', 'adminpass')
    finally:
        app.client = original_client

    assert success, message

    # Load the created provider data
    updated_provider = json.loads(sample_storage.provider_path.read_text())

    # Find the admin's provider entry
    admin_entry = None
    for user in updated_provider['data']['users']:
        if user.get('username') == 'admin':
            admin_entry = user
            break

    assert admin_entry is not None, "Admin entry not found in provider data"

    stored_password = admin_entry['password']

    # Verify it's base64-encoded (base64 strings typically end with = or == padding or are valid base64)
    try:
        decoded = base64.b64decode(stored_password)
    except Exception as e:
        pytest.fail(f"Password is not valid base64: {e}")

    # Verify the decoded value is a bcrypt hash (starts with $2a$, $2b$, or $2y$)
    assert decoded.startswith(b'$2'), f"Decoded password does not start with $2 (bcrypt marker): {decoded[:10]}"

    # Verify bcrypt version and rounds are present
    parts = decoded.split(b'$')
    assert len(parts) >= 4, f"Bcrypt hash has incorrect format: {decoded}"
    assert parts[1] in [b'2a', b'2b', b'2y'], f"Unknown bcrypt version: {parts[1]}"
    assert parts[2].isdigit(), f"Bcrypt rounds is not a number: {parts[2]}"


def test_wrong_password_fails_validation(sample_storage):
    """Test that wrong password fails validation (negative test)."""
    fake_container = FakeContainer(sample_storage.root)
    fake_client = FakeDockerClient(fake_container)

    original_client = app.client
    app.client = fake_client

    correct_password = 'correct_password123'
    wrong_password = 'wrong_password123'

    try:
        success, message = app.create_teacher_account('volume', 'teacher', correct_password)
    finally:
        app.client = original_client

    assert success, message

    # Load the created provider data
    updated_provider = json.loads(sample_storage.provider_path.read_text())

    # Find the teacher's provider entry
    teacher_entry = None
    for user in updated_provider['data']['users']:
        if user.get('username') == 'teacher':
            teacher_entry = user
            break

    assert teacher_entry is not None

    stored_password = teacher_entry['password']
    user_hash = base64.b64decode(stored_password)

    # Verify wrong password fails
    is_valid = bcrypt.checkpw(wrong_password.encode(), user_hash)
    assert not is_valid, "Wrong password should not validate successfully"
