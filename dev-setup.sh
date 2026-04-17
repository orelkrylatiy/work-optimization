#!/bin/bash
# Quick setup script for new developers

set -e

echo "🚀 HH Applicant Tool - Developer Setup"
echo ""

# Check Python
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $python_version"

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Install it with:"
    echo "   pip install poetry"
    exit 1
fi
echo "✅ Poetry found: $(poetry --version)"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found (optional, needed for docker-compose)"
else
    echo "✅ Docker found: $(docker --version)"
fi

echo ""
echo "📦 Installing dependencies..."
poetry install --with dev

echo ""
echo "🪝 Setting up pre-commit hooks..."
poetry run pip install pre-commit
pre-commit install

echo ""
echo "📝 Setting up configuration files..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env (EDIT THIS!)"
else
    echo "⚠️  .env already exists"
fi

if [ ! -f config/config.yaml ]; then
    cp config/config.example.yaml config/config.yaml
    echo "✅ Created config/config.yaml (EDIT THIS!)"
else
    echo "⚠️  config/config.yaml already exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your HH_PROFILE_ID"
echo "2. Edit config/config.yaml with your settings"
echo "3. Run tests: poetry run pytest tests/"
echo "4. Or start dev with Docker: docker-compose up"
echo ""
echo "📚 For more info, see DEVOPS.md"
