# Releasing

## Version Conventions

Follow [Semantic Versioning](https://semver.org/). Use conventional commits to signal intent:

- `feat:` commits warrant a **minor** version bump (0.X.0)
- `fix:` commits warrant a **patch** version bump (0.0.X)
- Breaking changes warrant a **major** version bump (X.0.0)

## Quick Release

```bash
# 1. Update version in pyproject.toml
#    Edit: version = "X.Y.Z"

# 2. Sync lockfile
uv lock

# 3. Commit the version bump
git add pyproject.toml uv.lock
git commit -m "chore: bump version to X.Y.Z"

# 4. Tag the release
git tag vX.Y.Z

# 5. Push commit and tag
git push --tags
```

## CI Pipeline

Pushing a tag matching `v*` triggers the `Publish to PyPI` workflow, which runs three sequential jobs:

1. **build** - Runs `uv build` to produce source and wheel distributions.
2. **publish** - Publishes artifacts to PyPI using OIDC trusted publisher (no API token required).
3. **release** - Creates a GitHub Release with auto-generated release notes derived from merged commits.

The `publish` job requires the `pypi` GitHub environment to be configured with a trusted publisher on PyPI.
