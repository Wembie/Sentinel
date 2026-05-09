# Release Scripts

These scripts keep `VERSION` and the static release manifests in sync.

## Commands

```bash
python scripts/release/bump_version.py {major}.{minor}.{patch}
python scripts/release/bump_version.py 1.0.0
python scripts/release/bump_version.py patch
python scripts/release/bump_version.py minor --commit
python scripts/release/sync_version.py
python scripts/release/sync_version.py --check
```

## What Each Script Does

- `bump_version.py`: updates `VERSION`, then syncs all static manifests.
- `sync_version.py`: syncs the current `VERSION` value into the static manifests.

## Suggested Flow

1. Bump the version with `python scripts/release/bump_version.py <version-or-bump>`.
2. Review the changes.
3. Commit and push.
4. Let CI/CD validate with `python scripts/release/sync_version.py --check`.
