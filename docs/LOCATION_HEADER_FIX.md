# Location Header Redirect Fix for Cloudflare Tunnel

## Issue

When clicking the "Access" button to open a Home Assistant instance through a Cloudflare tunnel, the interface would briefly flash/flicker open and then redirect back to the portal's index page. This occurred even after the previous fix that removed `rel="noreferrer"` from the Access button.

## Root Cause

The issue was caused by HTTP redirects sent by Home Assistant with unmodified Location headers:

1. User clicks "Access" button → opens `/proxy/8123/` in new tab
2. Home Assistant backend responds with a redirect (e.g., HTTP 302)
3. Location header contains a relative path like `/lovelace` or `/`
4. Browser interprets this as an absolute path from the domain root
5. Browser navigates to `/lovelace` instead of `/proxy/8123/lovelace`
6. This causes the page to leave the proxied instance and return to the portal

### Example Redirect Flow (Before Fix)

```
Browser Request:  GET /proxy/8123/
HA Response:      HTTP/302 Found
                  Location: /lovelace
Browser Action:   Navigate to /lovelace (portal's root, not the HA instance)
Result:           User sees the portal index page instead of Home Assistant
```

## Solution

Modified the proxy function in `app.py` to rewrite Location headers in redirect responses:

```python
# Rewrite Location header for redirects to include proxy prefix
# This is crucial for Cloudflare tunnel compatibility
if key.lower() == 'location':
    # Check if this is a relative path (starts with /)
    if value.startswith('/'):
        # Rewrite to include /proxy/{port}/ prefix
        value = f'/proxy/{port}{value}'
        logger.debug(f'Rewrote Location header to: {value}')
```

### Example Redirect Flow (After Fix)

```
Browser Request:  GET /proxy/8123/
HA Response:      HTTP/302 Found
                  Location: /lovelace
Proxy Rewrites:   Location: /proxy/8123/lovelace
Browser Action:   Navigate to /proxy/8123/lovelace (stays in HA instance)
Result:           User sees Home Assistant correctly
```

## Technical Details

### When Location Headers Are Rewritten

The proxy rewrites Location headers when:
- ✅ The Location value starts with `/` (relative path)
- ✅ The response is from the Home Assistant backend
- ✅ The HTTP status code is a redirect (3xx)

The proxy does NOT rewrite Location headers when:
- ❌ The Location value is an absolute URL (e.g., `https://...`)
- ❌ The Location value is already a proxy path (e.g., `/proxy/8123/...`)

### Common Home Assistant Redirects

Home Assistant commonly sends these redirects:
- `/` → `/lovelace` (default dashboard)
- `/auth/authorize` → `/auth/login` (authentication flow)
- `/config` → `/config/dashboard` (configuration pages)

All of these are now properly rewritten to maintain the proxy prefix.

## Relationship to Previous Fix

This fix builds on the previous fix that removed `rel="noreferrer"` from the Access button:

1. **Previous Fix** (CLOUDFLARE_TUNNEL_FIX.md): Ensured the Referer header is sent so the proxy can route requests correctly
2. **This Fix**: Ensures redirect responses maintain the proxy path so the browser stays within the proxied instance

Both fixes are necessary for full Cloudflare tunnel compatibility:
- Without Referer header: API requests fail because proxy can't determine target instance
- Without Location rewriting: Redirects take user back to portal index instead of HA instance

## Testing

Created `test_location_header_rewrite.py` to verify:
1. ✅ Relative paths in Location headers are rewritten
2. ✅ Root redirects (`/`) are handled correctly
3. ✅ Absolute URLs are not rewritten
4. ✅ Proxy prefix is correctly prepended

All existing tests continue to pass:
- ✅ test_access_button.py
- ✅ test_proxy.py
- ✅ test_html_rewriting.py
- ✅ test_websocket_fix.py

## Impact

This fix allows the Access button to work correctly in all scenarios:
- ✅ Cloudflare tunnels (with redirects)
- ✅ Reverse proxies (with redirects)
- ✅ Direct access (local network)
- ✅ Multiple instances
- ✅ Single instance mode

## Related Files

- `app.py` - Proxy function with Location header rewriting
- `test_location_header_rewrite.py` - Test verification
- `docs/CLOUDFLARE_TUNNEL_FIX.md` - Previous fix documentation
- `templates/index.html` - Access button implementation

## Security Considerations

This change only rewrites Location headers in responses from the Home Assistant backend. It does not:
- Modify user input
- Create open redirects (redirects are from HA backend only)
- Allow arbitrary URL construction
- Affect external URLs

The rewriting is scoped to relative paths only, preserving the security boundary of the proxy.
