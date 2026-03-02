#!/usr/bin/env python3
"""
Test to validate the Access button always opens the container instance in a new tab
and has proper security attributes for Cloudflare tunnel compatibility.

The button uses an onclick handler (openInstance) to open the student HA instance
directly at its host port, bypassing the ingress/proxy path. This prevents the HA
frontend's client-side routing from escaping the student instance and landing on
the main Home Assistant dashboard. The href still points to the proxy URL as a
no-JS fallback, and target="_blank" plus rel="noopener" are always present.
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


def test_access_button_has_onclick_handler():
    """Test that the Access button has an onclick handler to open the instance directly.
    
    The onclick handler calls openInstance(event, port) which opens the student HA
    at its direct host port (e.g., http://hostname:8126/), bypassing the proxy.
    This prevents HA frontend JS from escaping the student instance context.
    """
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Find the Access button link
    access_button_pattern = r'<a[^>]*class="[^"]*btn-access[^"]*"[^>]*>Öppna</a>'
    matches = re.findall(access_button_pattern, content)
    
    assert len(matches) > 0, "Access button not found in template"
    
    access_button = matches[0]
    
    # Check that onclick handler is present with openInstance call
    assert 'onclick="openInstance(event,' in access_button, \
        "Access button should have onclick='openInstance(event, ...)' handler"
    
    print("✓ Access button has onclick handler for direct port access")
    print(f"✓ Found: {access_button}")


def test_open_instance_function_exists():
    """Test that the openInstance JavaScript function is defined in the template."""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    assert 'function openInstance(event, port)' in content, \
        "openInstance function should be defined in the template"
    assert "window.location.protocol + '//' + window.location.hostname" in content, \
        "openInstance should use window.location.hostname for direct access"
    
    print("✓ openInstance JavaScript function is defined")


def test_access_button_renders_correctly():
    """Test that the Access button renders correctly in both ingress and non-ingress modes.
    
    In both modes, target='_blank', rel='noopener', and the onclick handler should
    be present. The href points to the proxy URL as a no-JS fallback.
    """
    env = Environment(loader=BaseLoader())
    snippet = '<a href="{{ ingress_path }}/proxy/{{ instance.port }}/" onclick="openInstance(event, {{ instance.port }})" target="_blank" rel="noopener" class="btn-access">Öppna</a>'
    template = env.from_string(snippet)
    
    # Test standalone mode (no ingress_path)
    rendered_standalone = template.render(ingress_path='', instance={'port': 8124})
    assert 'target="_blank"' in rendered_standalone, \
        "Standalone mode should have target='_blank'"
    assert 'rel="noopener"' in rendered_standalone, \
        "Standalone mode should have rel='noopener'"
    assert 'href="/proxy/8124/"' in rendered_standalone, \
        "Standalone mode should have proxy URL as fallback href"
    assert 'onclick="openInstance(event, 8124)"' in rendered_standalone, \
        "Standalone mode should have onclick handler with correct port"
    
    # Test ingress mode (ingress_path set)
    ingress = '/api/hassio_ingress/abc123'
    rendered_ingress = template.render(ingress_path=ingress, instance={'port': 8124})
    assert 'target="_blank"' in rendered_ingress, \
        "Ingress mode should have target='_blank' to open instance in new tab"
    assert 'rel="noopener"' in rendered_ingress, \
        "Ingress mode should have rel='noopener'"
    assert f'href="{ingress}/proxy/8124/"' in rendered_ingress, \
        "Ingress mode should have ingress-prefixed proxy URL as fallback href"
    assert 'onclick="openInstance(event, 8124)"' in rendered_ingress, \
        "Ingress mode should have onclick handler with correct port"
    
    print("✓ Access button renders correctly in both modes")
    print(f"  Standalone: {rendered_standalone}")
    print(f"  Ingress:    {rendered_ingress}")


if __name__ == '__main__':
    test_access_button_has_noopener()
    test_access_button_always_opens_new_tab()
    test_access_button_has_onclick_handler()
    test_open_instance_function_exists()
    test_access_button_renders_correctly()
    print("\n✓ All access button tests passed!")
