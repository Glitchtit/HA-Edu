#!/usr/bin/env python3
"""
Test to verify that the Dockerfile includes all necessary application files.
This test ensures that the ModuleNotFoundError for interaction_logger is fixed.
"""

import os
import re


def test_dockerfile_includes_interaction_logger():
    """Verify that Dockerfile copies interaction_logger.py"""
    dockerfile_path = os.path.join(os.path.dirname(__file__), 'Dockerfile')
    
    with open(dockerfile_path, 'r') as f:
        dockerfile_content = f.read()
    
    # Check that interaction_logger.py is copied
    assert 'COPY interaction_logger.py' in dockerfile_content, \
        "Dockerfile must include 'COPY interaction_logger.py' instruction"
    
    print("✓ Dockerfile includes interaction_logger.py")
    return True


def test_app_imports_interaction_logger():
    """Verify that app.py imports interaction_logger"""
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    
    with open(app_path, 'r') as f:
        app_content = f.read()
    
    # Check that app.py imports interaction_logger
    assert 'from interaction_logger import interaction_logger' in app_content or \
           'import interaction_logger' in app_content, \
        "app.py must import interaction_logger"
    
    print("✓ app.py imports interaction_logger")
    return True


def test_interaction_logger_file_exists():
    """Verify that interaction_logger.py exists in the repository"""
    logger_path = os.path.join(os.path.dirname(__file__), 'interaction_logger.py')
    
    assert os.path.exists(logger_path), \
        "interaction_logger.py must exist in the repository"
    
    print("✓ interaction_logger.py exists in repository")
    return True


if __name__ == '__main__':
    print("Testing Dockerfile fix for interaction_logger module...")
    print()
    
    all_passed = True
    
    try:
        test_interaction_logger_file_exists()
    except AssertionError as e:
        print(f"✗ {e}")
        all_passed = False
    
    try:
        test_app_imports_interaction_logger()
    except AssertionError as e:
        print(f"✗ {e}")
        all_passed = False
    
    try:
        test_dockerfile_includes_interaction_logger()
    except AssertionError as e:
        print(f"✗ {e}")
        all_passed = False
    
    print()
    if all_passed:
        print("All tests passed! ✓")
        exit(0)
    else:
        print("Some tests failed! ✗")
        exit(1)
