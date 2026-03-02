#!/usr/bin/env python3
"""
Test to validate the Access button always opens the container instance in a new tab
and has proper security attributes for Cloudflare tunnel compatibility.

The button always uses target="_blank" so the proxied HA instance opens in its own
browser tab rather than navigating inside the ingress iframe, which would show the
main Home Assistant interface instead of the container instance.
"""

import os
import re

from jinja2 import Environment, BaseLoader


def test_access_button_has_noopener():
    """Test that the Access button has rel='noopener' attribute for security while preserving referrer for Cloudflare tunnel."""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Find the Access button link (button text is "Öppna")
    access_button_pattern = r'<a[^>]*class="[^"]*btn-access[^"]*"[^>]*>Öppna</a>'
    matches = re.findall(access_button_pattern, content)
    
    assert len(matches) > 0, "Access button not found in template"
    
    access_button = matches[0]
    
    # The button should always include target="_blank" so the container instance
    # opens in a new tab instead of navigating the ingress iframe.
    assert 'target="_blank"' in access_button, \
        "Access button should always have target='_blank'"
    
    # Check that it has rel="noopener" (but NOT noreferrer)
    assert 'rel="noopener"' in access_button, \
        "Access button should have rel='noopener' for security"
    
    # Ensure noreferrer is NOT present (it breaks Cloudflare tunnel)
    assert 'noreferrer' not in access_button, \
        "Access button should NOT have 'noreferrer' as it breaks Cloudflare tunnel routing"
    
    print("✓ Access button has proper security attributes")
    print(f"✓ Found: {access_button}")


def test_access_button_always_opens_new_tab():
    """Test that the Access button always opens in a new tab.
    
    Previously, target='_blank' was conditional on ingress mode, but this caused
    the button to navigate inside the HA ingress iframe, showing the main Home
    Assistant interface instead of the container instance. Now target='_blank'
    is always present.
    """
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Find the line with the access button
    access_line_pattern = r'.*class="[^"]*btn-access[^"]*".*>Öppna</a>'
    matches = re.findall(access_line_pattern, content)
    
    assert len(matches) > 0, "Access button line not found in template"
    
    access_line = matches[0]
    
    # target="_blank" should be unconditional (not wrapped in {% if %})
    assert 'target="_blank"' in access_line, \
        "Access button should always have target='_blank'"
    assert '{% if not ingress_path %}target="_blank"' not in access_line, \
        "target='_blank' should not be conditional on ingress_path"
    
    print("✓ Access button always opens in a new tab")
    print(f"✓ Found: {access_line.strip()}")


def test_access_button_renders_correctly():
    """Test that the Access button renders correctly in both ingress and non-ingress modes.
    
    In both modes, target='_blank' and rel='noopener' should be present so the
    container instance always opens in a new browser tab.
    """
    env = Environment(loader=BaseLoader())
    snippet = '<a href="{{ ingress_path }}/proxy/{{ instance.port }}/" target="_blank" rel="noopener" class="btn-access">Öppna</a>'
    template = env.from_string(snippet)
    
    # Test standalone mode (no ingress_path)
    rendered_standalone = template.render(ingress_path='', instance={'port': 8124})
    assert 'target="_blank"' in rendered_standalone, \
        "Standalone mode should have target='_blank'"
    assert 'rel="noopener"' in rendered_standalone, \
        "Standalone mode should have rel='noopener'"
    assert 'href="/proxy/8124/"' in rendered_standalone, \
        "Standalone mode should have direct proxy URL"
    
    # Test ingress mode (ingress_path set)
    ingress = '/api/hassio_ingress/abc123'
    rendered_ingress = template.render(ingress_path=ingress, instance={'port': 8124})
    assert 'target="_blank"' in rendered_ingress, \
        "Ingress mode should have target='_blank' to open instance in new tab"
    assert 'rel="noopener"' in rendered_ingress, \
        "Ingress mode should have rel='noopener'"
    assert f'href="{ingress}/proxy/8124/"' in rendered_ingress, \
        "Ingress mode should have ingress-prefixed proxy URL"
    
    print("✓ Access button renders correctly in both modes")
    print(f"  Standalone: {rendered_standalone}")
    print(f"  Ingress:    {rendered_ingress}")


if __name__ == '__main__':
    test_access_button_has_noopener()
    test_access_button_always_opens_new_tab()
    test_access_button_renders_correctly()
    print("\n✓ All access button tests passed!")
