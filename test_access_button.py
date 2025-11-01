#!/usr/bin/env python3
"""
Test to validate the Access button has proper security attributes for Cloudflare tunnel compatibility
"""

import os
import re


def test_access_button_has_noopener_noreferrer():
    """Test that the Access button has rel='noopener noreferrer' attribute"""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Find the Access button link
    # Pattern: <a href="/proxy/{{ instance.port }}/" ... class="btn-access">Access</a>
    access_button_pattern = r'<a\s+[^>]*class="btn-access"[^>]*>Access</a>'
    matches = re.findall(access_button_pattern, content)
    
    assert len(matches) > 0, "Access button not found in template"
    
    access_button = matches[0]
    
    # Check that it has target="_blank"
    assert 'target="_blank"' in access_button, "Access button should have target='_blank'"
    
    # Check that it has rel="noopener noreferrer"
    assert 'rel="noopener noreferrer"' in access_button, \
        "Access button should have rel='noopener noreferrer' for security and Cloudflare tunnel compatibility"
    
    print("✓ Access button has proper security attributes")
    print(f"✓ Found: {access_button}")
    return True


if __name__ == '__main__':
    test_access_button_has_noopener_noreferrer()
    print("\n✓ All access button tests passed!")
