# Pull Request Guidelines - ValidaHub

## 📋 PR Configuration Checklist

Use this checklist when creating or reviewing PRs to ensure professional standards.

### 1. **Reviewers** 👥
- [ ] Add at least 1 human reviewer (even if it's yourself from another account)
- [ ] Bot reviewers are supplementary, not primary
- [ ] If still WIP → **Convert to Draft PR**

### 2. **Assignees** 👤
- [ ] **Always assign yourself** - prevents orphaned PRs
- [ ] Add co-authors if pair programming

### 3. **Labels** 🏷️

#### Type Labels (required - pick one)
- `type:feat` - New feature
- `type:fix` - Bug fix
- `type:chore` - Maintenance/refactor
- `type:docs` - Documentation only
- `type:test` - Test improvements
- `type:perf` - Performance improvements
- `type:ci` - CI/CD changes

#### Area Labels (required - pick relevant)
- `area:domain` - Domain layer changes
- `area:application` - Application/use cases
- `area:infra` - Infrastructure/adapters
- `area:rules` - Rule engine/YAML
- `area:jobs` - Job processing
- `area:api` - API endpoints
- `area:web` - Frontend changes

#### Size Labels (required - pick one)
- `size:XS` - ≤50 lines
- `size:S` - ≤150 lines
- `size:M` - ≤400 lines (soft limit)
- `size:L` - >400 lines (needs `size:override` justification)

#### Risk Labels (required - pick one)
- `risk:low` - Isolated changes, good test coverage
- `risk:medium` - Crosses boundaries, needs careful review
- `risk:high` - Critical path, security, or data model changes

#### Breaking Change Label
- `breaking:true` - API/contract breaking changes
- `breaking:false` - Backward compatible (default)

#### Status Labels
- `needs:review` - Ready for review
- `needs:changes` - Changes requested
- `needs:rebase` - Conflicts to resolve
- `blocked` - Waiting on dependency

### 4. **Projects** 📊
- [ ] Link to **ValidaHub Board**
- [ ] Move to **"In Review"** column
- [ ] Update when status changes

### 5. **Milestone** 🎯
- [ ] Assign to current sprint (e.g., "Sprint 1")
- [ ] Helps with sprint retrospectives
- [ ] Tracks velocity

### 6. **Development/Issues** 🔗

Use keywords in PR body to auto-close issues:

```markdown
## Related Issues
Closes #12  - Implements IdempotencyKey validation
Relates to #15 - Part of security epic
Addresses #23 - Fixes test failures
```

Keywords that auto-close:
- `Closes #XX`
- `Fixes #XX`
- `Resolves #XX`

Keywords that link without closing:
- `Relates to #XX`
- `Addresses #XX`
- `Part of #XX`

### 7. **Notifications** 🔔
- [ ] Keep notifications ON until merged
- [ ] Customize if needed (Settings → Notifications)
- [ ] Respond to comments within 24h

## 📝 PR Template

Create `.github/pull_request_template.md`:

```markdown
## Description
Brief description of changes and why they're needed.

## Type of Change
- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🧹 Code refactor
- [ ] ⚡ Performance improvement
- [ ] ✅ Test improvement

## Related Issues
Closes #(issue number)

## Testing
- [ ] Unit tests pass locally
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Security tests pass

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing unit tests pass locally
- [ ] I have updated the documentation (if needed)
- [ ] My changes generate no new warnings
- [ ] I have checked my code for security issues

## Screenshots (if applicable)
Add screenshots for UI changes

## Performance Impact
Describe any performance implications

## Rollback Plan
How to rollback if this causes issues in production
```

## 🎨 Label Creation Script

Run this to create all labels at once:

```bash
# Create type labels (blue)
gh label create "type:feat" --description "New feature" --color "0052CC"
gh label create "type:fix" --description "Bug fix" --color "0052CC"
gh label create "type:chore" --description "Maintenance" --color "0052CC"
gh label create "type:docs" --description "Documentation" --color "0052CC"
gh label create "type:test" --description "Test improvements" --color "0052CC"
gh label create "type:perf" --description "Performance" --color "0052CC"
gh label create "type:ci" --description "CI/CD" --color "0052CC"

# Create area labels (green)
gh label create "area:domain" --description "Domain layer" --color "0E8A16"
gh label create "area:application" --description "Application layer" --color "0E8A16"
gh label create "area:infra" --description "Infrastructure" --color "0E8A16"
gh label create "area:rules" --description "Rule engine" --color "0E8A16"
gh label create "area:jobs" --description "Job processing" --color "0E8A16"
gh label create "area:api" --description "API endpoints" --color "0E8A16"
gh label create "area:web" --description "Frontend" --color "0E8A16"

# Create size labels (purple)
gh label create "size:XS" --description "≤50 lines" --color "5319E7"
gh label create "size:S" --description "≤150 lines" --color "5319E7"
gh label create "size:M" --description "≤400 lines" --color "5319E7"
gh label create "size:L" --description ">400 lines" --color "5319E7"
gh label create "size:override" --description "Size limit override justified" --color "5319E7"

# Create risk labels (orange/red)
gh label create "risk:low" --description "Low risk changes" --color "FEF2C0"
gh label create "risk:medium" --description "Medium risk changes" --color "F9D0C4"
gh label create "risk:high" --description "High risk changes" --color "E11D48"

# Create breaking change labels
gh label create "breaking:true" --description "Breaking changes" --color "E11D48"
gh label create "breaking:false" --description "Backward compatible" --color "0E8A16"

# Create status labels (yellow)
gh label create "needs:review" --description "Ready for review" --color "FBCA04"
gh label create "needs:changes" --description "Changes requested" --color "FBCA04"
gh label create "needs:rebase" --description "Needs rebase" --color "FBCA04"
gh label create "blocked" --description "Blocked by dependency" --color "B60205"
```

## 🚀 Quick PR Setup for Current PR #1

```bash
# Add labels using GitHub CLI
gh pr edit 1 --add-label "type:feat,area:domain,size:L,risk:medium,breaking:false"

# Add yourself as assignee
gh pr edit 1 --add-assignee "@me"

# Add to project (replace PROJECT_ID with actual ID)
gh pr edit 1 --add-project "ValidaHub Board"

# Set milestone
gh pr edit 1 --milestone "Sprint 1"
```

## 📊 Example Well-Configured PR

```
PR #1: feat(domain): establish DDD foundation with multi-tenant value objects

Reviewers: @john-reviewer, @dependabot (bot)
Assignees: @your-username
Labels: type:feat, area:domain, size:L, risk:medium, breaking:false
Projects: ValidaHub Board (In Review)
Milestone: Sprint 1

Closes #5 - Implement core value objects
Relates to #3 - Security epic
Part of #1 - MVP foundation
```

## 🔄 PR Lifecycle

1. **Draft** → Work in progress
2. **Ready for Review** → Remove draft status, add `needs:review`
3. **In Review** → Reviewers actively reviewing
4. **Changes Requested** → Add `needs:changes`, address feedback
5. **Approved** → Ready to merge
6. **Merged** → Auto-close linked issues

## 📈 Metrics to Track

- **Lead Time**: Draft → Merged
- **Review Time**: Ready → First Review
- **Rework Rate**: Changes Requested / Total PRs
- **Size Distribution**: Track if PRs are getting too large
- **Orphan Rate**: PRs without assignees

---

**Last Updated**: 2024-08-29  
**Maintainer**: ValidaHub Team