#!/bin/bash

# Initialize Semantic Release for the project
# This script helps set up the initial release

echo "🚀 Initializing Semantic Release..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Please install Poetry first."
    echo "Visit: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
poetry install

# Check current version
echo "📌 Current version:"
poetry run semantic-release version --print

# Dry run to see what would happen
echo "🔍 Preview of next version (dry run):"
poetry run semantic-release version --dry-run

echo ""
echo "✅ Semantic Release is configured!"
echo ""
echo "📝 Next steps:"
echo "1. Start using conventional commits:"
echo "   - feat: for new features (minor version bump)"
echo "   - fix: for bug fixes (patch version bump)"
echo "   - BREAKING CHANGE: for breaking changes (major version bump)"
echo ""
echo "2. Push to main branch to trigger automatic releases"
echo ""
echo "3. Check release status at:"
echo "   - GitHub Actions: .../actions/workflows/release.yml"
echo "   - Releases page: .../releases"
echo ""
echo "📚 For more info, see docs/SEMANTIC_RELEASE.md"