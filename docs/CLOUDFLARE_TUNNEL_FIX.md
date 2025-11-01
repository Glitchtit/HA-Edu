# Cloudflare Tunnel Access Button Fix

## Issue

When clicking the "Access" button to open a Home Assistant instance through a Cloudflare tunnel, the interface would briefly flash open and then redirect back to the index page. This issue only occurred when accessing the portal through a Cloudflare tunnel; local access worked correctly.

## Root Cause

The Access button was using `rel="noopener noreferrer"` which has two effects:
1. `noopener` - Prevents the new page from accessing `window.opener` (security feature)
2. `noreferrer` - Strips the Referer HTTP header from requests

The proxy routing mechanism relies on the Referer header to determine which Home Assistant instance to route requests to. When the Referer header is missing, the proxy cannot determine the correct target instance, causing routing failures.

### Technical Details

From `app.py` (proxy_fallback function):
```python
# Strategy 1: Try to extract port from referer URL (e.g., http://domain/proxy/8123/)
referer = request.headers.get('Referer', '')
if not referer:
    referer = request.headers.get('Origin', '')

if referer:
    port_match = re.search(r'/proxy/(\d+)', referer)
    if port_match:
        port = int(port_match.group(1))
```

Without the Referer header, the proxy has to fall back to:
1. Session cookies (if available)
2. Single-instance mode (only works with one instance)
3. Error state (with multiple instances and no referer/session)

## Solution

Changed the Access button from:
```html
<a href="/proxy/{{ instance.port }}/" target="_blank" rel="noopener noreferrer">Access</a>
```

To:
```html
<a href="/proxy/{{ instance.port }}/" target="_blank" rel="noopener">Access</a>
```

This change:
- ✅ Keeps `rel="noopener"` for security (prevents window.opener access)
- ✅ Removes `rel="noreferrer"` to preserve Referer header
- ✅ Allows Cloudflare tunnel routing to work correctly
- ✅ Maintains security by preventing opener manipulation

## Security Considerations

### What is `rel="noopener"`?

When you open a link with `target="_blank"`, the new page can access the original page through `window.opener`. This can be a security risk as the new page could potentially:
- Change the original page's location (phishing attacks)
- Access properties of the original page (if same-origin)

The `rel="noopener"` attribute prevents this by ensuring `window.opener` is null in the new page.

### What is `rel="noreferrer"`?

The `rel="noreferrer"` attribute prevents the browser from sending the Referer header to the new page. This is sometimes used for:
- Privacy (hiding where users came from)
- Preventing referrer leakage to third parties

### Why Remove `noreferrer`?

In this application:
1. **We own both sides**: The portal and the Home Assistant instances are both part of our system
2. **Routing requirement**: The proxy needs the Referer to route requests correctly
3. **No privacy concern**: We're not leaking referrer to external sites
4. **Security maintained**: `rel="noopener"` still prevents window.opener access

## Impact

This fix allows the Access button to work correctly when the portal is accessed through:
- ✅ Cloudflare tunnels
- ✅ Reverse proxies
- ✅ Direct access (local network)
- ✅ Any scenario where proxy routing relies on Referer header

## Testing

Updated `test_access_button.py` to verify:
1. Access button has `target="_blank"` ✓
2. Access button has `rel="noopener"` ✓
3. Access button does NOT have `noreferrer` ✓

## Related Files

- `templates/index.html` - Access button implementation
- `test_access_button.py` - Test validation
- `app.py` - Proxy routing logic (proxy_fallback function)
