#!/usr/bin/env python3
"""
Test for the onboarding check fix - ensures both auth files are checked
"""

import sys
import os
import json
import types
from unittest.mock import patch

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class FakeExecResult:
    def __init__(self, exit_code=0, output=b''):
        self.exit_code = exit_code
        self.output = output


class FakeContainer:
    def __init__(self, has_auth=True, has_provider=True):
        self.has_auth = has_auth
        self.has_provider = has_provider
        self.started = False
        self.removed = False
        
    def start(self):
        self.started = True
        
    def wait(self):
        return 0
        
    def logs(self):
        # The command checks both files with &&
        # Only returns "exists" if both files are present
        if self.has_auth and self.has_provider:
            return b'exists'
        else:
            return b'missing'
            
    def remove(self):
        self.removed = True


class FakeContainers:
    def __init__(self, container):
        self.container = container
        
    def create(self, *args, **kwargs):
        # Verify the command checks for both files
        if 'command' in kwargs:
            command = kwargs['command']
            if isinstance(command, list) and len(command) > 2:
                shell_cmd = command[-1]
                # The fix should check both files
                assert '/config/.storage/auth' in shell_cmd, "Command should check auth file"
                assert '/config/.storage/auth_provider.homeassistant' in shell_cmd, "Command should check auth_provider file"
                assert '&&' in shell_cmd, "Command should use && to check both files"
        return self.container


class FakeImages:
    def get(self, name):
        return object()


class FakeDockerClient:
    def __init__(self, container):
        self.containers = FakeContainers(container)
        self.images = FakeImages()


def test_onboarding_complete_with_both_files():
    """Test that onboarding is considered complete when both files exist"""
    print("\nTesting onboarding check with both files present...")
    
    _initial_client = types.SimpleNamespace(containers=None, images=None)
    with patch('docker.from_env', return_value=_initial_client):
        import app
        
    fake_container = FakeContainer(has_auth=True, has_provider=True)
    fake_client = FakeDockerClient(fake_container)
    
    original_client = app.client
    app.client = fake_client
    
    try:
        result = app.check_instance_onboarding_complete('test-volume')
        assert result == True, "Onboarding should be complete when both files exist"
        print("✓ Onboarding correctly identified as complete")
        return True
    finally:
        app.client = original_client


def test_onboarding_incomplete_missing_auth():
    """Test that onboarding is incomplete when auth file is missing"""
    print("\nTesting onboarding check with auth file missing...")
    
    _initial_client = types.SimpleNamespace(containers=None, images=None)
    with patch('docker.from_env', return_value=_initial_client):
        import app
        
    fake_container = FakeContainer(has_auth=False, has_provider=True)
    fake_client = FakeDockerClient(fake_container)
    
    original_client = app.client
    app.client = fake_client
    
    try:
        result = app.check_instance_onboarding_complete('test-volume')
        assert result == False, "Onboarding should be incomplete when auth file is missing"
        print("✓ Onboarding correctly identified as incomplete (missing auth)")
        return True
    finally:
        app.client = original_client


def test_onboarding_incomplete_missing_provider():
    """Test that onboarding is incomplete when auth_provider file is missing"""
    print("\nTesting onboarding check with auth_provider file missing...")
    
    _initial_client = types.SimpleNamespace(containers=None, images=None)
    with patch('docker.from_env', return_value=_initial_client):
        import app
        
    fake_container = FakeContainer(has_auth=True, has_provider=False)
    fake_client = FakeDockerClient(fake_container)
    
    original_client = app.client
    app.client = fake_client
    
    try:
        result = app.check_instance_onboarding_complete('test-volume')
        assert result == False, "Onboarding should be incomplete when auth_provider file is missing"
        print("✓ Onboarding correctly identified as incomplete (missing auth_provider)")
        return True
    finally:
        app.client = original_client


def test_onboarding_incomplete_missing_both():
    """Test that onboarding is incomplete when both files are missing"""
    print("\nTesting onboarding check with both files missing...")
    
    _initial_client = types.SimpleNamespace(containers=None, images=None)
    with patch('docker.from_env', return_value=_initial_client):
        import app
        
    fake_container = FakeContainer(has_auth=False, has_provider=False)
    fake_client = FakeDockerClient(fake_container)
    
    original_client = app.client
    app.client = fake_client
    
    try:
        result = app.check_instance_onboarding_complete('test-volume')
        assert result == False, "Onboarding should be incomplete when both files are missing"
        print("✓ Onboarding correctly identified as incomplete (missing both files)")
        return True
    finally:
        app.client = original_client


def main():
    """Run all tests"""
    print("=" * 70)
    print("Onboarding Check Fix Tests")
    print("=" * 70)
    print("\nVerifying that check_instance_onboarding_complete checks both files:")
    print("  1. /config/.storage/auth")
    print("  2. /config/.storage/auth_provider.homeassistant")
    
    tests = [
        test_onboarding_complete_with_both_files,
        test_onboarding_incomplete_missing_auth,
        test_onboarding_incomplete_missing_provider,
        test_onboarding_incomplete_missing_both,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 70)
    
    return all(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
