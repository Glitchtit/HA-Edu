# Changelog

## 1.4.0

- Remove the forced password-change prompt that appeared on first login with the default admin account; Home Assistant Ingress now handles authentication so the separate credential setup is no longer needed

## 1.3.1

- Remove the login/register overlay and logout button when running inside Home Assistant Ingress, since the Supervisor already authenticates users before forwarding requests
- Relax ingress auto-auth to no longer require the Bearer header; the presence of `SUPERVISOR_TOKEN` and `X-Ingress-Path` is sufficient proof the request was authenticated by the Supervisor

## 1.3.0

- Auto-authenticate users arriving through Home Assistant Ingress by reading the `Authorization: Bearer` token that the Supervisor injects, removing the need for a separate login step
- Enable `auth_api` in the add-on manifest so the Supervisor validates users before forwarding requests

## 1.2.1

- Make the add-on sidebar panel visible to non-admin Home Assistant users by setting `panel_admin: false`

## 1.2.0

- Overhaul dark mode support: extend CSS custom property overrides for the full neutral palette so buttons, badges, info boxes, and form controls remain readable when the browser prefers a dark color scheme
- Replace hardcoded hex color inline styles in modals with reusable CSS utility classes (`info-box`, `success-box`, `caution-box`, `danger-text`, `teacher-badge-box`) that adapt to both light and dark mode
- Add dark mode variants for status badges, error/success messages, teacher-access badges, and lock buttons
- Fix footer using hardcoded `rgba(0,0,0,0.9)` color that was invisible in dark mode
- Apply the same fixes to the proxy error page

## 1.1.2

- Fix "Öppna" button redirecting to the main Home Assistant dashboard (`/home/overview`) instead of showing the student instance. The button now opens the student HA directly at its host port, bypassing the ingress proxy so that the HA frontend's client-side routing stays within the student instance.

## 1.1.1

- Fix proxy 400 Bad Request error by not forwarding `X-Forwarded-*` and `X-Ingress-Path` headers to downstream Home Assistant instances (HA rejects these from untrusted proxies)

## 1.1.0

- Fix "Öppna" button to always open the container instance in a new tab instead of navigating inside the ingress iframe (which showed the main Home Assistant interface)
- Add AI rules (`.github/copilot-instructions.md`) so GitHub agents automatically bump the version number and update the changelog on every pull request

## 1.0.0

- Initial release as a Home Assistant add-on
- Ingress support – accessible from the HA sidebar as "HA-Edu"
- Manage student Home Assistant instances from within Home Assistant OS
- Full feature parity with the standalone Docker deployment
