# Release Process - ValidaHub

## 📋 Overview

ValidaHub follows Semantic Versioning (SemVer) with automated changelog generation and GitHub Releases integration.

## 🔢 Versioning Strategy

### Semantic Versioning (MAJOR.MINOR.PATCH)

- **MAJOR** (1.0.0): Breaking API changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

### Pre-release Versions

```
0.1.0-alpha.1  → Alpha testing
0.1.0-beta.1   → Beta testing
0.1.0-rc.1     → Release candidate
```

### Version Bumping Rules

Based on conventional commits since last release:

| Commit Type | Version Bump | Example |
|------------|--------------|---------|
| `fix:` | PATCH | 0.1.0 → 0.1.1 |
| `feat:` | MINOR | 0.1.0 → 0.2.0 |
| `BREAKING CHANGE:` or `!` | MAJOR | 0.1.0 → 1.0.0 |
| `chore:`, `docs:`, `style:` | No bump | 0.1.0 → 0.1.0 |

## 🚀 Release Types

### 1. **Development Release** (auto on merge to main)
- Triggered automatically
- Creates pre-release (alpha/beta)
- Deploys to staging

### 2. **Production Release** (manual trigger)
- Requires approval
- Creates stable release
- Deploys to production
- Sends notifications

### 3. **Hotfix Release** (expedited)
- Direct to main branch
- Immediate patch version
- Fast-track deployment

## 📝 Changelog Generation

### Automatic Sections

Commits are grouped by type:

```markdown
## [0.2.0] - 2024-08-29

### ✨ Features
- feat(domain): add job retry capability (#45)
- feat(api): implement webhook support (#48)

### 🐛 Bug Fixes
- fix(api): handle null tenant_id in logs (#52)
- fix(domain): correct state transition validation (#53)

### 💥 Breaking Changes
- feat(api)!: remove deprecated v1 endpoints (#50)

### 🔧 Maintenance
- chore(deps): update dependencies (#54)
- refactor(domain): simplify job aggregate (#55)
```

### Commit Grouping

```yaml
Features: feat
Bug Fixes: fix
Breaking Changes: feat!, fix!, refactor!
Performance: perf
Documentation: docs
Maintenance: chore, build, ci
Security: security (custom type)
```

## 🤖 Release Automation

### Release Workflow (.github/workflows/release.yml)

```yaml
name: Release

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      release_type:
        description: 'Release type'
        required: true
        default: 'patch'
        type: choice
        options:
          - patch
          - minor
          - major
          - prerelease

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm install -g semantic-release @semantic-release/changelog @semantic-release/git

      - name: Get next version
        id: version
        run: |
          NEXT_VERSION=$(npx semantic-release --dry-run | grep 'The next release version is' | sed -E 's/.*([0-9]+\.[0-9]+\.[0-9]+).*/\1/')
          echo "version=$NEXT_VERSION" >> $GITHUB_OUTPUT

      - name: Generate changelog
        run: |
          npx conventional-changelog -p angular -i CHANGELOG.md -s

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: v${{ steps.version.outputs.version }}
          name: Release v${{ steps.version.outputs.version }}
          body_path: CHANGELOG.md
          draft: false
          prerelease: ${{ contains(steps.version.outputs.version, '-') }}
          generate_release_notes: true

      - name: Update version files
        run: |
          # Update pyproject.toml
          sed -i "s/version = \".*\"/version = \"${{ steps.version.outputs.version }}\"/" pyproject.toml
          
          # Update package.json if exists
          if [ -f package.json ]; then
            npm version ${{ steps.version.outputs.version }} --no-git-tag-version
          fi

      - name: Commit version bump
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .
          git commit -m "chore(release): v${{ steps.version.outputs.version }} [skip ci]"
          git push

      - name: Docker build and push
        run: |
          docker build -t validahub:${{ steps.version.outputs.version }} .
          docker tag validahub:${{ steps.version.outputs.version }} validahub:latest
          # docker push validahub:${{ steps.version.outputs.version }}
```

## 📦 Release Checklist

### Pre-Release

- [ ] All CI checks passing
- [ ] No critical or high priority bugs open
- [ ] Documentation updated
- [ ] Migration scripts tested
- [ ] Performance benchmarks acceptable
- [ ] Security scan completed

### Release Steps

1. **Prepare Release Branch**
```bash
git checkout -b release/v0.2.0
git push origin release/v0.2.0
```

2. **Run Release Checks**
```bash
make release-check
# Runs: tests, security scan, license check, changelog preview
```

3. **Create Release PR**
```bash
gh pr create \
  --title "chore(release): prepare v0.2.0" \
  --body "Release v0.2.0 with new features and fixes" \
  --label "release,priority:high"
```

4. **Trigger Release**
```bash
# Manual trigger via GitHub Actions
gh workflow run release.yml -f release_type=minor

# Or via git tag
git tag v0.2.0
git push origin v0.2.0
```

### Post-Release

- [ ] Verify deployment successful
- [ ] Smoke tests passing
- [ ] Monitor error rates
- [ ] Update status page
- [ ] Send release notes to stakeholders
- [ ] Create next milestone

## 🏷️ Git Tag Convention

```bash
# Production releases
v1.0.0
v1.1.0
v1.1.1

# Pre-releases
v1.0.0-alpha.1
v1.0.0-beta.1
v1.0.0-rc.1

# Feature previews
v1.0.0-feat.webhooks.1
```

## 📊 Release Notes Template

```markdown
# Release v0.2.0

## 🎯 Highlights
- Major feature: Job retry capability
- Performance: 30% faster CSV processing
- Security: Enhanced input validation

## ✨ What's New
- Job retry mechanism with exponential backoff (#45)
- Webhook support for real-time notifications (#48)
- Bulk job submission endpoint (#49)

## 🐛 Bug Fixes
- Fixed tenant isolation in job queries (#52)
- Resolved state transition validation errors (#53)

## 💥 Breaking Changes
- Removed deprecated v1 API endpoints (#50)
- Changed authentication header format (#51)

## 📈 Performance Improvements
- Optimized database queries for job listing
- Reduced memory usage in CSV processing

## 🔒 Security Updates
- Updated dependencies to patch CVE-2024-XXXX
- Enhanced LGPD compliance checks

## 📚 Documentation
- Added API migration guide
- Updated webhook integration examples

## 🙏 Contributors
Thanks to @user1, @user2 for their contributions!

## 📦 Dependencies
- Updated FastAPI to 0.100.0
- Updated SQLAlchemy to 2.0.0

## 🔄 Migration Notes
Users upgrading from v0.1.x should:
1. Update API endpoints from /v1 to /v2
2. Modify authentication headers
3. Run migration script: `python scripts/migrate_0.2.0.py`

---

Full changelog: [v0.1.0...v0.2.0](https://github.com/org/validahub/compare/v0.1.0...v0.2.0)
```

## 🔄 Rollback Process

### Quick Rollback

```bash
# Revert to previous version
git revert <release-commit>
git tag v0.2.1
git push origin v0.2.1

# Or via GitHub UI
# Go to Releases → Previous Release → Deploy
```

### Database Rollback

```bash
# Always have reversible migrations
alembic downgrade -1
```

## 📈 Release Metrics

Track for each release:

- **Lead Time**: Last commit → Production
- **Deployment Frequency**: Releases per week
- **MTTR**: Mean time to recovery
- **Change Failure Rate**: Rollbacks / Releases
- **Adoption Rate**: Users on latest version

## 🛠️ Tools Configuration

### .releaserc.json (Semantic Release)

```json
{
  "branches": ["main"],
  "plugins": [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    ["@semantic-release/changelog", {
      "changelogFile": "CHANGELOG.md"
    }],
    ["@semantic-release/git", {
      "assets": ["CHANGELOG.md", "pyproject.toml"],
      "message": "chore(release): ${nextRelease.version} [skip ci]"
    }],
    "@semantic-release/github"
  ]
}
```

### Makefile targets

```makefile
release-check:
	@echo "🔍 Running release checks..."
	@make test
	@make security-scan
	@make license-check
	@echo "✅ Ready for release!"

changelog-preview:
	@npx conventional-changelog -p angular -u

version-bump-patch:
	@npm version patch --no-git-tag-version

version-bump-minor:
	@npm version minor --no-git-tag-version

version-bump-major:
	@npm version major --no-git-tag-version
```

## 🚨 Emergency Release Process

For critical security fixes:

1. Create hotfix branch from main
2. Apply fix with `fix!:` commit
3. Skip staging, deploy direct to production
4. Backport to development branches

```bash
# Hotfix workflow
git checkout -b hotfix/security-fix main
# ... apply fixes ...
git commit -m "fix!: critical security vulnerability in auth"
git push origin hotfix/security-fix

# Fast-track merge
gh pr create --label "hotfix,priority:critical"
gh pr merge --admin --merge
```

---

**Last Updated**: 2024-08-29  
**Maintainer**: ValidaHub Team  
**Next Release**: v0.1.0-alpha.1 (MVP)