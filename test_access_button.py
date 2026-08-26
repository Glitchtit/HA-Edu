#!/usr/bin/env python3
"""
Test to validate the Access button has proper security attributes for Cloudflare tunnel compatibility
"""

import os
import re


def test_access_button_has_noopener_noreferrer():
    """Test that the Access button has rel='noopener' attribute for security while preserving referrer for Cloudflare tunnel"""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Find the Access button link
    # Pattern: <a ... class="btn-access" ... >Access</a>
    # Use a robust pattern that handles attributes in any order
    access_button_pattern = r'<a[^>]*class="[^"]*btn-access[^"]*"[^>]*>Öppna</a>'
    matches = re.findall(access_button_pattern, content)
    
    assert len(matches) > 0, "Access button not found in template"
    
    access_button = matches[0]
    
    # Check that it has target="_blank"
    assert 'target="_blank"' in access_button, "Access button should have target='_blank'"
    
    # Check that it has rel="noopener" (but NOT noreferrer)
    # noopener provides security by preventing window.opener access
    # noreferrer is NOT used because it breaks Cloudflare tunnel routing (proxy needs Referer header)
    assert 'rel="noopener"' in access_button, \
        "Access button should have rel='noopener' for security"
    
    # Ensure noreferrer is NOT present (it breaks Cloudflare tunnel)
    assert 'noreferrer' not in access_button, \
        "Access button should NOT have 'noreferrer' as it breaks Cloudflare tunnel routing"
    
    print("✓ Access button has proper security attributes")
    print(f"✓ Found: {access_button}")
    return True


if __name__ == '__main__':
    test_access_button_has_noopener_noreferrer()
    print("\n✓ All access button tests passed!")
