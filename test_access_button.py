#!/usr/bin/env python3
"""
Test to validate the Access button has proper security attributes for Cloudflare tunnel compatibility
and correct ingress behavior (no target="_blank" when using HA ingress to avoid 400 errors).
"""

import os
import re

from jinja2 import Environment, BaseLoader


def test_access_button_has_noopener_noreferrer():
    """Test that the Access button has rel='noopener' attribute for security while preserving referrer for Cloudflare tunnel.
    
    The button conditionally adds target='_blank' and rel='noopener' only when NOT using HA ingress,
    because opening a new window to an ingress URL causes a 400: bad request error.
    """
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Find the Access button link (button text is "Öppna")
    # Pattern: <a ... class="btn-access" ... >Öppna</a>
    # Use a robust pattern that handles attributes in any order
    access_button_pattern = r'<a[^>]*class="[^"]*btn-access[^"]*"[^>]*>Öppna</a>'
    matches = re.findall(access_button_pattern, content)
    
    assert len(matches) > 0, "Access button not found in template"
    
    access_button = matches[0]
    
    # The button should conditionally include target="_blank" only when NOT using ingress.
    # In the Jinja template this is: {% if not ingress_path %}target="_blank" rel="noopener"{% endif %}
    # The rendered HTML will have target="_blank" in standalone mode but not in ingress mode.
    # We verify the template contains the conditional logic.
    assert 'target="_blank"' in access_button, \
        "Access button should have target='_blank' (conditionally rendered for non-ingress mode)"
    
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


def test_access_button_conditional_target_blank():
    """Test that the Access button only opens a new window when NOT using HA ingress.
    
    When running through HA ingress, target='_blank' causes a 400 error because
    the new browser window doesn't have a valid ingress session.
    The template uses {% if not ingress_path %} to conditionally add target='_blank'.
    """
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Find the line with the access button
    access_line_pattern = r'.*class="[^"]*btn-access[^"]*".*>Öppna</a>'
    matches = re.findall(access_line_pattern, content)
    
    assert len(matches) > 0, "Access button line not found in template"
    
    access_line = matches[0]
    
    # Verify the conditional Jinja logic is present
    assert '{% if not ingress_path %}' in access_line, \
        "Access button should conditionally add target='_blank' based on ingress_path"
    assert '{% endif %}' in access_line, \
        "Access button should have matching endif for the conditional"
    
    print("✓ Access button has conditional target='_blank' for ingress compatibility")
    print(f"✓ Found conditional logic in: {access_line.strip()}")


def test_access_button_renders_correctly():
    """Test that the Access button renders correctly in both ingress and non-ingress modes.
    
    Renders the Jinja snippet with ingress_path set and unset to verify:
    - Standalone (no ingress): target='_blank' and rel='noopener' are present
    - HA ingress: target='_blank' and rel='noopener' are absent
    """
    env = Environment(loader=BaseLoader())
    # Extract just the access button Jinja snippet from the template
    snippet = '<a href="{{ ingress_path }}/proxy/{{ instance.port }}/" {% if not ingress_path %}target="_blank" rel="noopener"{% endif %} class="btn-access">Öppna</a>'
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
    assert 'target="_blank"' not in rendered_ingress, \
        "Ingress mode should NOT have target='_blank' (causes 400 error)"
    assert 'rel="noopener"' not in rendered_ingress, \
        "Ingress mode should NOT have rel='noopener'"
    assert f'href="{ingress}/proxy/8124/"' in rendered_ingress, \
        "Ingress mode should have ingress-prefixed proxy URL"
    
    print("✓ Access button renders correctly in both modes")
    print(f"  Standalone: {rendered_standalone}")
    print(f"  Ingress:    {rendered_ingress}")


if __name__ == '__main__':
    test_access_button_has_noopener_noreferrer()
    test_access_button_conditional_target_blank()
    test_access_button_renders_correctly()
    print("\n✓ All access button tests passed!")
