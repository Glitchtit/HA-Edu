#!/usr/bin/env python3
"""
Test master configuration functionality
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_master_config_exists():
    """Test that master configuration file exists"""
    print("Testing master configuration file...")
    master_config_path = os.path.join(os.path.dirname(__file__), 'master_configuration.yaml')
    if os.path.exists(master_config_path):
        print(f"✓ Master configuration exists: {master_config_path}")
        return True
    else:
        print(f"✗ Master configuration not found: {master_config_path}")
        return False

def test_master_config_content():
    """Test that master configuration has required content"""
    print("\nTesting master configuration content...")
    master_config_path = os.path.join(os.path.dirname(__file__), 'master_configuration.yaml')
    
    if not os.path.exists(master_config_path):
        print("✗ Master configuration file not found")
        return False
    
    with open(master_config_path, 'r') as f:
        content = f.read()
    
    # Check for required demo components
    checks = [
        ('demo:', 'Demo mode enabled'),
        ('light:', 'Lights section'),
        ('Demo Light 1', 'Light 1'),
        ('Demo Light 2', 'Light 2'),
        ('Demo Light 3', 'Light 3'),
        ('Demo Light 4', 'Light 4'),
        ('Demo Light 5', 'Light 5'),
        ('weather:', 'Weather section'),
        ('Demo Weather', 'Weather entity'),
        ('climate:', 'Climate section'),
        ('Demo Thermostat', 'Thermostat entity'),
        ('device_tracker:', 'Device tracker section'),
        ('demo_tracker_1', 'Device tracker 1'),
        ('demo_tracker_2', 'Device tracker 2'),
        ('camera:', 'Camera section'),
        ('Demo Camera', 'Camera entity'),
        ('input_button:', 'Input button section'),
        ('demo_button_1:', 'Button 1'),
        ('demo_button_2:', 'Button 2')
    ]
    
    for check, desc in checks:
        if check in content:
            print(f"✓ Found: {desc}")
        else:
            print(f"✗ Missing: {desc}")
            return False
    
    return True

def test_master_config_in_dockerfile():
    """Test that Dockerfile includes master configuration"""
    print("\nTesting Dockerfile includes master configuration...")
    dockerfile_path = os.path.join(os.path.dirname(__file__), 'Dockerfile')
    
    if not os.path.exists(dockerfile_path):
        print("✗ Dockerfile not found")
        return False
    
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    if 'master_configuration.yaml' in content:
        print("✓ Master configuration copied in Dockerfile")
        return True
    else:
        print("✗ Master configuration not copied in Dockerfile")
        return False

def test_app_has_master_config_path():
    """Test that app.py has MASTER_CONFIG_PATH"""
    print("\nTesting app.py has MASTER_CONFIG_PATH...")
    try:
        import app
        
        if hasattr(app, 'MASTER_CONFIG_PATH'):
            print(f"✓ MASTER_CONFIG_PATH exists: {app.MASTER_CONFIG_PATH}")
            return True
        else:
            print("✗ MASTER_CONFIG_PATH not found in app.py")
            return False
    except Exception as e:
        print(f"✗ Error importing app: {e}")
        return False

def test_copy_function_exists():
    """Test that copy_master_config_to_volume function exists"""
    print("\nTesting copy_master_config_to_volume function...")
    try:
        import app
        
        if hasattr(app, 'copy_master_config_to_volume'):
            print("✓ copy_master_config_to_volume function exists")
            return True
        else:
            print("✗ copy_master_config_to_volume function not found")
            return False
    except Exception as e:
        print(f"✗ Error importing app: {e}")
        return False

def test_create_instance_uses_master_config():
    """Test that create_instance calls copy_master_config_to_volume"""
    print("\nTesting create_instance uses master configuration...")
    
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Look for the copy function call in create_instance
    if 'copy_master_config_to_volume' in content and 'def create_instance' in content:
        # Check if the function is called after the instance creation section
        create_func_start = content.find('def create_instance')
        next_func_start = content.find('\n@app.route', create_func_start + 1)
        create_func_content = content[create_func_start:next_func_start]
        
        if 'copy_master_config_to_volume' in create_func_content:
            print("✓ create_instance calls copy_master_config_to_volume")
            return True
        else:
            print("✗ create_instance does not call copy_master_config_to_volume")
            return False
    else:
        print("✗ Required functions not found in app.py")
        return False

def test_reset_instance_uses_master_config():
    """Test that reset_instance calls copy_master_config_to_volume"""
    print("\nTesting reset_instance uses master configuration...")
    
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Look for the copy function call in reset_instance
    if 'copy_master_config_to_volume' in content and 'def reset_instance' in content:
        # Check if the function is called after the reset section
        reset_func_start = content.find('def reset_instance')
        next_func_start = content.find('\n@app.route', reset_func_start + 1)
        reset_func_content = content[reset_func_start:next_func_start]
        
        if 'copy_master_config_to_volume' in reset_func_content:
            print("✓ reset_instance calls copy_master_config_to_volume")
            return True
        else:
            print("✗ reset_instance does not call copy_master_config_to_volume")
            return False
    else:
        print("✗ Required functions not found in app.py")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Master Configuration Tests")
    print("=" * 60)
    
    tests = [
        test_master_config_exists,
        test_master_config_content,
        test_master_config_in_dockerfile,
        test_app_has_master_config_path,
        test_copy_function_exists,
        test_create_instance_uses_master_config,
        test_reset_instance_uses_master_config
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All master configuration tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
