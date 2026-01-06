#!/bin/bash
#
# Initialize hackflix-catalog repository for GitHub Pages deployment
#
# Usage: ./init-repo.sh YOUR_GITHUB_USERNAME
#

set -e

# Check for username argument
if [ -z "$1" ]; then
    echo "Usage: $0 YOUR_GITHUB_USERNAME"
    echo "Example: $0 wiktor-jedski"
    exit 1
fi

USERNAME="$1"
REPO_NAME="hackflix-catalog"
REPO_URL="https://github.com/${USERNAME}/${REPO_NAME}.git"

echo "🚀 Initializing HackFlix Catalog Repository"
echo "================================================"
echo "Username: $USERNAME"
echo "Repository: $REPO_NAME"
echo "URL: $REPO_URL"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is not installed"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed"
    exit 1
fi

# Validate catalog before proceeding
echo "📋 Step 1: Validating catalog.json..."
python3 scripts/validate_catalog.py catalog.json

if [ $? -ne 0 ]; then
    echo "❌ Validation failed. Please fix errors before proceeding."
    exit 1
fi

echo "✅ Catalog validation passed"
echo ""

# Initialize git repository
echo "📦 Step 2: Initializing git repository..."
if [ -d .git ]; then
    echo "⚠️  Git repository already initialized"
else
    git init
    echo "✅ Git repository initialized"
fi

echo ""

# Create .gitignore if it doesn't exist
if [ ! -f .gitignore ]; then
    echo "📝 Creating .gitignore..."
    cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
.venv/
.DS_Store
*.bak
EOF
    echo "✅ .gitignore created"
fi

echo ""

# Add all files
echo "➕ Step 3: Adding files to git..."
git add .
echo "✅ Files added"

echo ""

# Check if initial commit exists
if git rev-parse HEAD >/dev/null 2>&1; then
    echo "⚠️  Initial commit already exists"
else
    echo "💾 Step 4: Creating initial commit..."
    git commit -m "Initial catalog setup

- 5 movies with complete metadata
- 3 series with seasons
- Automated validation via GitHub Actions
- Ready for GitHub Pages deployment"
    echo "✅ Initial commit created"
fi

echo ""

# Set main branch
echo "🌿 Step 5: Setting main branch..."
git branch -M main
echo "✅ Branch set to main"

echo ""

# Add remote
echo "🔗 Step 6: Adding remote repository..."
if git remote get-url origin &> /dev/null; then
    current_remote=$(git remote get-url origin)
    echo "⚠️  Remote already exists: $current_remote"
    echo "   To update: git remote set-url origin $REPO_URL"
else
    git remote add origin "$REPO_URL"
    echo "✅ Remote added: $REPO_URL"
fi

echo ""
echo "================================================"
echo "✅ Repository initialized successfully!"
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Create GitHub repository:"
echo "   - Go to: https://github.com/new"
echo "   - Name: $REPO_NAME"
echo "   - Visibility: Public"
echo "   - Don't initialize with README"
echo ""
echo "2. Push to GitHub:"
echo "   git push -u origin main"
echo ""
echo "3. Enable GitHub Pages:"
echo "   - Go to: https://github.com/${USERNAME}/${REPO_NAME}/settings/pages"
echo "   - Source: Deploy from branch 'main'"
echo "   - Folder: / (root)"
echo "   - Click Save"
echo ""
echo "4. Wait for deployment (~2 minutes)"
echo ""
echo "5. Access catalog:"
echo "   https://${USERNAME}.github.io/${REPO_NAME}/catalog.json"
echo ""
echo "6. Configure HackFlix client:"
echo "   CATALOG_URL=https://${USERNAME}.github.io/${REPO_NAME}/catalog.json"
echo ""
echo "================================================"
echo ""
echo "For detailed instructions, see SETUP.md"
