# Authentication Login Error Fix

## Problem

When attempting to log in to a Home Assistant instance through the HA-Edu portal proxy, users encountered a "500 Internal Server Error" with the message "Server got itself in trouble" when submitting the login form.

## Root Cause

The proxy was sending two non-standard HTTP headers to the Home Assistant backend:
- `X-Forwarded-Prefix: /proxy/{port}`
- `X-Ingress-Path: /proxy/{port}`

These headers are specific to the Home Assistant Supervisor/Add-on ecosystem and are not recognized by standalone Home Assistant core instances. When Home Assistant's authentication system received these headers, it attempted to process them (likely for URL construction or redirect handling) and crashed with an unhandled exception, resulting in a 500 error.

## Solution

Removed the `X-Forwarded-Prefix` and `X-Ingress-Path` headers from the proxy's forwarded requests. The proxy now only sends the standard reverse proxy headers that Home Assistant core expects:

- `X-Forwarded-For`: Client's IP address
- `X-Forwarded-Proto`: Protocol (http/https)
- `X-Forwarded-Host`: Original host header

## Technical Details

### Headers Behavior

| Header | Purpose | Used By | Status |
|--------|---------|---------|--------|
| `X-Forwarded-For` | Client IP identification | HA Core | ✅ Kept |
| `X-Forwarded-Proto` | Protocol detection | HA Core | ✅ Kept |
| `X-Forwarded-Host` | Original hostname | HA Core | ✅ Kept |
| `X-Forwarded-Prefix` | URL path prefix | HA Supervisor | ❌ Removed |
| `X-Ingress-Path` | Ingress path | HA Supervisor | ❌ Removed |

### Why These Headers Caused Issues

Home Assistant Supervisor add-ons use `X-Ingress-Path` to handle URL rewriting when add-ons are accessed through the Supervisor's ingress proxy. When this header is present, Home Assistant's authentication flow attempts to construct redirect URLs using this path prefix. However, in standalone installations (like HA-Edu instances), this logic is not needed and caused crashes during the OAuth2/login flow.

## Testing

A new test file `test_auth_login_fix.py` was created to verify:
1. The problematic headers are not sent
2. The required headers are still sent correctly
3. Authentication POST requests work properly
4. Other endpoints remain unaffected

## Configuration

The Home Assistant instances created by HA-Edu are configured in `master_configuration.yaml` to trust X-Forwarded headers:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.17.0.0/16    # Docker bridge network
    - 192.168.50.0/24  # LAN network
```

This configuration allows Home Assistant to properly handle the remaining X-Forwarded headers from the proxy.

## References

- [Home Assistant Reverse Proxy Documentation](https://www.home-assistant.io/integrations/http/#reverse-proxies)
- [RFC 7239 - Forwarded HTTP Extension](https://tools.ietf.org/html/rfc7239)
- [Home Assistant Supervisor Ingress](https://developers.home-assistant.io/docs/add-ons/presentation#ingress)
