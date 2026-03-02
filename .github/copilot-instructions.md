# Copilot Instructions for HA-Edu

## Version and Changelog Management

Every pull request that changes application code **must** include a version bump and a changelog entry. Follow these rules:

### Version Number

- The version is defined in `ha-edu/config.yaml` in the `version` field.
- Use [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
  - **PATCH** – bug fixes, small tweaks, documentation corrections.
  - **MINOR** – new features, non-breaking improvements.
  - **MAJOR** – breaking changes.
- Increment the version **once** per pull request, choosing the highest applicable level (e.g., if a PR contains both a bug fix and a new feature, bump MINOR).

### Changelog

- The changelog lives in `ha-edu/CHANGELOG.md`.
- Add a new section at the **top** (below the `# Changelog` heading) for the new version.
- Use the format:

```markdown
## <new version>

- Concise description of each change (one bullet per logical change)
```

### Checklist

Before marking a PR as ready:

1. Bump the `version` field in `ha-edu/config.yaml`.
2. Add a matching section in `ha-edu/CHANGELOG.md`.
3. Make sure the version in both files is identical.

## Project Layout

The repository contains two parallel deployments that must stay in sync:

| Path | Purpose |
|------|---------|
| Root (`app.py`, `templates/`, …) | Standalone Docker deployment |
| `ha-edu/` | Home Assistant add-on package |

When editing templates, Python code, or configuration that exists in **both** locations, apply the same change to both copies.
