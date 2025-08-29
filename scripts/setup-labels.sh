#!/bin/bash
# Setup GitHub labels for ValidaHub project

echo "🏷️  Creating GitHub labels for ValidaHub..."

# Type labels (blue)
echo "Creating type labels..."
gh label create "type:feat" --description "New feature" --color "0052CC" 2>/dev/null || echo "  type:feat already exists"
gh label create "type:fix" --description "Bug fix" --color "0052CC" 2>/dev/null || echo "  type:fix already exists"
gh label create "type:chore" --description "Maintenance" --color "0052CC" 2>/dev/null || echo "  type:chore already exists"
gh label create "type:docs" --description "Documentation" --color "0052CC" 2>/dev/null || echo "  type:docs already exists"
gh label create "type:test" --description "Test improvements" --color "0052CC" 2>/dev/null || echo "  type:test already exists"
gh label create "type:perf" --description "Performance" --color "0052CC" 2>/dev/null || echo "  type:perf already exists"
gh label create "type:ci" --description "CI/CD" --color "0052CC" 2>/dev/null || echo "  type:ci already exists"
gh label create "type:refactor" --description "Code refactoring" --color "0052CC" 2>/dev/null || echo "  type:refactor already exists"

# Area labels (green)
echo "Creating area labels..."
gh label create "area:domain" --description "Domain layer" --color "0E8A16" 2>/dev/null || echo "  area:domain already exists"
gh label create "area:application" --description "Application layer" --color "0E8A16" 2>/dev/null || echo "  area:application already exists"
gh label create "area:infra" --description "Infrastructure" --color "0E8A16" 2>/dev/null || echo "  area:infra already exists"
gh label create "area:rules" --description "Rule engine" --color "0E8A16" 2>/dev/null || echo "  area:rules already exists"
gh label create "area:jobs" --description "Job processing" --color "0E8A16" 2>/dev/null || echo "  area:jobs already exists"
gh label create "area:api" --description "API endpoints" --color "0E8A16" 2>/dev/null || echo "  area:api already exists"
gh label create "area:web" --description "Frontend" --color "0E8A16" 2>/dev/null || echo "  area:web already exists"
gh label create "area:security" --description "Security" --color "0E8A16" 2>/dev/null || echo "  area:security already exists"
gh label create "area:compliance" --description "LGPD compliance" --color "0E8A16" 2>/dev/null || echo "  area:compliance already exists"

# Size labels (purple)
echo "Creating size labels..."
gh label create "size:XS" --description "≤50 lines" --color "5319E7" 2>/dev/null || echo "  size:XS already exists"
gh label create "size:S" --description "≤150 lines" --color "5319E7" 2>/dev/null || echo "  size:S already exists"
gh label create "size:M" --description "≤400 lines" --color "5319E7" 2>/dev/null || echo "  size:M already exists"
gh label create "size:L" --description ">400 lines" --color "5319E7" 2>/dev/null || echo "  size:L already exists"
gh label create "size:override" --description "Size limit override justified" --color "5319E7" 2>/dev/null || echo "  size:override already exists"

# Risk labels (orange/red gradient)
echo "Creating risk labels..."
gh label create "risk:low" --description "Low risk changes" --color "FEF2C0" 2>/dev/null || echo "  risk:low already exists"
gh label create "risk:medium" --description "Medium risk changes" --color "F9D0C4" 2>/dev/null || echo "  risk:medium already exists"
gh label create "risk:high" --description "High risk changes" --color "E11D48" 2>/dev/null || echo "  risk:high already exists"

# Breaking change labels
echo "Creating breaking change labels..."
gh label create "breaking:true" --description "Breaking changes" --color "E11D48" 2>/dev/null || echo "  breaking:true already exists"
gh label create "breaking:false" --description "Backward compatible" --color "0E8A16" 2>/dev/null || echo "  breaking:false already exists"

# Status labels (yellow)
echo "Creating status labels..."
gh label create "needs:review" --description "Ready for review" --color "FBCA04" 2>/dev/null || echo "  needs:review already exists"
gh label create "needs:changes" --description "Changes requested" --color "FBCA04" 2>/dev/null || echo "  needs:changes already exists"
gh label create "needs:rebase" --description "Needs rebase" --color "FBCA04" 2>/dev/null || echo "  needs:rebase already exists"
gh label create "blocked" --description "Blocked by dependency" --color "B60205" 2>/dev/null || echo "  blocked already exists"
gh label create "WIP" --description "Work in progress" --color "C5DEF5" 2>/dev/null || echo "  WIP already exists"

# Priority labels (red gradient)
echo "Creating priority labels..."
gh label create "priority:critical" --description "Critical priority" --color "B60205" 2>/dev/null || echo "  priority:critical already exists"
gh label create "priority:high" --description "High priority" --color "D93F0B" 2>/dev/null || echo "  priority:high already exists"
gh label create "priority:medium" --description "Medium priority" --color "FBCA04" 2>/dev/null || echo "  priority:medium already exists"
gh label create "priority:low" --description "Low priority" --color "BFD4F2" 2>/dev/null || echo "  priority:low already exists"

echo "✅ Label setup complete!"
echo ""
echo "📝 To apply labels to PR #1, run:"
echo "gh pr edit 1 --add-label \"type:feat,area:domain,size:L,risk:medium,breaking:false\""