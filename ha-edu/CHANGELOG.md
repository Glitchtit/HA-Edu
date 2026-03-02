# Changelog

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
