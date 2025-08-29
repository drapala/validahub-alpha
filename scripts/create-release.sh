#!/bin/bash
# Create a new release for ValidaHub

set -e

echo "🚀 ValidaHub Release Creator"
echo "=========================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed${NC}"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Get current version from pyproject.toml
CURRENT_VERSION=$(python3 -c "import toml; print(toml.load('pyproject.toml')['project']['version'])" 2>/dev/null || echo "0.0.0")
echo -e "📦 Current version: ${YELLOW}$CURRENT_VERSION${NC}"

# Prompt for release type
echo ""
echo "Select release type:"
echo "1) patch   - Bug fixes (0.0.x)"
echo "2) minor   - New features (0.x.0)"
echo "3) major   - Breaking changes (x.0.0)"
echo "4) alpha   - Alpha release (0.0.0-alpha.x)"
echo "5) beta    - Beta release (0.0.0-beta.x)"
echo "6) rc      - Release candidate (0.0.0-rc.x)"
echo "7) custom  - Enter custom version"

read -p "Enter choice [1-7]: " choice

# Calculate next version
IFS='.' read -r major minor patch <<< "${CURRENT_VERSION%-*}"

case $choice in
    1)
        RELEASE_TYPE="patch"
        NEXT_VERSION="${major}.${minor}.$((patch + 1))"
        ;;
    2)
        RELEASE_TYPE="minor"
        NEXT_VERSION="${major}.$((minor + 1)).0"
        ;;
    3)
        RELEASE_TYPE="major"
        NEXT_VERSION="$((major + 1)).0.0"
        ;;
    4)
        RELEASE_TYPE="alpha"
        TIMESTAMP=$(date +%Y%m%d%H%M%S)
        NEXT_VERSION="${major}.${minor}.${patch}-alpha.${TIMESTAMP}"
        ;;
    5)
        RELEASE_TYPE="beta"
        TIMESTAMP=$(date +%Y%m%d%H%M%S)
        NEXT_VERSION="${major}.${minor}.${patch}-beta.${TIMESTAMP}"
        ;;
    6)
        RELEASE_TYPE="rc"
        TIMESTAMP=$(date +%Y%m%d%H%M%S)
        NEXT_VERSION="${major}.${minor}.${patch}-rc.${TIMESTAMP}"
        ;;
    7)
        read -p "Enter custom version: " NEXT_VERSION
        RELEASE_TYPE="custom"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "📦 Next version: ${GREEN}$NEXT_VERSION${NC}"

# Run pre-release checks
echo ""
echo "🔍 Running pre-release checks..."

# Check if working directory is clean
if [[ -n $(git status -s) ]]; then
    echo -e "${YELLOW}⚠️  Warning: Working directory has uncommitted changes${NC}"
    read -p "Continue anyway? [y/N]: " confirm
    if [[ $confirm != [yY] ]]; then
        echo "Release cancelled"
        exit 1
    fi
fi

# Check if on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" && "$CURRENT_BRANCH" != "master" ]]; then
    echo -e "${YELLOW}⚠️  Warning: Not on main branch (current: $CURRENT_BRANCH)${NC}"
    read -p "Continue anyway? [y/N]: " confirm
    if [[ $confirm != [yY] ]]; then
        echo "Release cancelled"
        exit 1
    fi
fi

# Run tests
echo "🧪 Running tests..."
if make test > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Tests passed${NC}"
else
    echo -e "${RED}❌ Tests failed${NC}"
    read -p "Continue anyway? [y/N]: " confirm
    if [[ $confirm != [yY] ]]; then
        echo "Release cancelled"
        exit 1
    fi
fi

# Generate release notes
echo ""
echo "📝 Generating release notes..."

# Get last tag
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

# Create release notes file
cat > RELEASE_NOTES_TEMP.md << EOF
# Release v$NEXT_VERSION

**Release Date**: $(date +"%Y-%m-%d")
**Type**: $RELEASE_TYPE

## What's Changed

EOF

# Add commit summary
if [ -z "$LAST_TAG" ]; then
    git log --pretty=format:"- %s (%h)" --no-merges | head -20 >> RELEASE_NOTES_TEMP.md
else
    git log ${LAST_TAG}..HEAD --pretty=format:"- %s (%h)" --no-merges >> RELEASE_NOTES_TEMP.md
fi

echo "" >> RELEASE_NOTES_TEMP.md
echo "" >> RELEASE_NOTES_TEMP.md

# Add contributors
echo "## Contributors" >> RELEASE_NOTES_TEMP.md
if [ -z "$LAST_TAG" ]; then
    git log --format="%aN" | sort -u | sed 's/^/- @/' >> RELEASE_NOTES_TEMP.md
else
    git log ${LAST_TAG}..HEAD --format="%aN" | sort -u | sed 's/^/- @/' >> RELEASE_NOTES_TEMP.md
fi

# Show release notes
echo ""
echo "Release notes preview:"
echo "----------------------"
cat RELEASE_NOTES_TEMP.md
echo "----------------------"

# Confirm release
echo ""
read -p "Create release v$NEXT_VERSION? [y/N]: " confirm
if [[ $confirm != [yY] ]]; then
    echo "Release cancelled"
    rm RELEASE_NOTES_TEMP.md
    exit 1
fi

# Create the release
echo ""
echo "🏷️  Creating release..."

# Method 1: Using GitHub workflow (recommended)
if [[ -f ".github/workflows/release.yml" ]]; then
    echo "Triggering release workflow..."
    gh workflow run release.yml -f release_type=$RELEASE_TYPE
    echo -e "${GREEN}✅ Release workflow triggered${NC}"
    echo "Check progress at: https://github.com/$GITHUB_REPOSITORY/actions"
else
    # Method 2: Direct release creation
    echo "Creating release directly..."
    
    # Create and push tag
    git tag -a "v$NEXT_VERSION" -m "Release v$NEXT_VERSION"
    git push origin "v$NEXT_VERSION"
    
    # Create GitHub release
    gh release create "v$NEXT_VERSION" \
        --title "v$NEXT_VERSION" \
        --notes-file RELEASE_NOTES_TEMP.md \
        $(if [[ $NEXT_VERSION == *"-"* ]]; then echo "--prerelease"; fi)
    
    echo -e "${GREEN}✅ Release v$NEXT_VERSION created${NC}"
fi

# Clean up
rm -f RELEASE_NOTES_TEMP.md

# Post-release actions
echo ""
echo "📋 Post-release checklist:"
echo "- [ ] Verify deployment to staging/production"
echo "- [ ] Run smoke tests"
echo "- [ ] Update documentation if needed"
echo "- [ ] Notify stakeholders"
echo "- [ ] Create next milestone"

echo ""
echo -e "${GREEN}🎉 Release process completed!${NC}"
echo "View release at: https://github.com/$GITHUB_REPOSITORY/releases/tag/v$NEXT_VERSION"