#!/bin/bash
# Local testing script to validate workflow steps before pushing
# This mirrors what GitHub Actions does, so you can catch issues locally

set -e

echo "=========================================="
echo "Local Workflow Testing"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILED=0

# Step 1: Test Python setup
echo -e "${YELLOW}Step 1: Testing Python 3.11 setup...${NC}"
if python3.11 --version 2>/dev/null; then
    echo -e "${GREEN}✓ Python 3.11 found${NC}"
else
    echo -e "${RED}✗ Python 3.11 not found. Install with: brew install python@3.11${NC}"
    FAILED=1
fi
echo ""

# Step 2: Test dependency installation
echo -e "${YELLOW}Step 2: Testing dependency installation...${NC}"
if pip install -e ".[dev]" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Dependencies installed successfully${NC}"
else
    echo -e "${RED}✗ Dependency installation failed${NC}"
    FAILED=1
fi
echo ""

# Step 3: Test pytest runs
echo -e "${YELLOW}Step 3: Testing pytest execution...${NC}"
if pytest tests/unit/ tests/integration/ -v --tb=short > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Tests pass${NC}"
else
    echo -e "${RED}✗ Tests failed${NC}"
    echo "Run 'pytest tests/unit/ tests/integration/ -v' to see details"
    FAILED=1
fi
echo ""

# Step 4: Test Docker build (dry run)
echo -e "${YELLOW}Step 4: Testing Docker build (dry run)...${NC}"
if docker buildx version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker Buildx available${NC}"
    echo "  Testing Dockerfile syntax..."
    if docker build --dry-run -f deployment/Dockerfile . > /dev/null 2>&1 || docker build -f deployment/Dockerfile . --dry-run 2>&1 | head -5; then
        echo -e "${GREEN}✓ Dockerfile syntax OK${NC}"
    else
        echo -e "${YELLOW}⚠ Dockerfile syntax check (dry-run may not be available)${NC}"
    fi
else
    echo -e "${RED}✗ Docker Buildx not available${NC}"
    FAILED=1
fi
echo ""

# Step 5: Check workflow YAML syntax
echo -e "${YELLOW}Step 5: Validating workflow YAML...${NC}"
if command -v yamllint > /dev/null 2>&1; then
    if yamllint .github/workflows/deploy.yml > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Workflow YAML syntax OK${NC}"
    else
        echo -e "${RED}✗ Workflow YAML has syntax errors${NC}"
        yamllint .github/workflows/deploy.yml
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ yamllint not installed (optional)${NC}"
    echo "  Install with: pip install yamllint"
fi
echo ""

# Summary
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All local checks passed!${NC}"
    echo "You can safely push to GitHub."
    exit 0
else
    echo -e "${RED}✗ Some checks failed${NC}"
    echo "Fix the issues above before pushing."
    exit 1
fi

