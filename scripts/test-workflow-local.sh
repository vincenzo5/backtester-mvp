#!/bin/bash
# Local testing script to validate workflow steps before pushing
# This mirrors EXACTLY what GitHub Actions does in the 'test' job

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

# Step 1: Test Python setup (mirrors: Set up Python 3.11)
echo -e "${YELLOW}Step 1: Testing Python 3.11 setup...${NC}"
if python3.11 --version 2>/dev/null; then
    echo -e "${GREEN}✓ Python 3.11 found${NC}"
else
    echo -e "${RED}✗ Python 3.11 not found. Install with: brew install python@3.11${NC}"
    FAILED=1
fi
echo ""

# Step 2: Test dependency installation (mirrors: Install dependencies)
echo -e "${YELLOW}Step 2: Testing dependency installation...${NC}"
if pip install -e ".[dev]" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Dependencies installed successfully${NC}"
else
    echo -e "${RED}✗ Dependency installation failed${NC}"
    FAILED=1
fi
echo ""

# Step 3: Run unit tests (mirrors: Run unit tests)
echo -e "${YELLOW}Step 3: Running unit tests...${NC}"
if pytest tests/unit/ -v --tb=short > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Unit tests pass${NC}"
else
    echo -e "${RED}✗ Unit tests failed${NC}"
    echo "Run 'pytest tests/unit/ -v --tb=short' to see details"
    FAILED=1
fi
echo ""

# Step 4: Run integration tests (mirrors: Run integration tests)
echo -e "${YELLOW}Step 4: Running integration tests...${NC}"
if pytest tests/integration/ -v --tb=short > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Integration tests pass${NC}"
else
    echo -e "${RED}✗ Integration tests failed${NC}"
    echo "Run 'pytest tests/integration/ -v --tb=short' to see details"
    FAILED=1
fi
echo ""

# Step 5: Run system tests (mirrors: Run system tests)
echo -e "${YELLOW}Step 5: Running system tests...${NC}"
if pytest tests/system/ -v --tb=short > /dev/null 2>&1; then
    echo -e "${GREEN}✓ System tests pass${NC}"
else
    echo -e "${RED}✗ System tests failed${NC}"
    echo "Run 'pytest tests/system/ -v --tb=short' to see details"
    FAILED=1
fi
echo ""

# Step 6: Run E2E tests (mirrors: Run E2E tests with || true)
echo -e "${YELLOW}Step 6: Running E2E tests (if data available)...${NC}"
if pytest tests/e2e/ -v -m "not requires_data" --tb=short > /dev/null 2>&1 || true; then
    echo -e "${GREEN}✓ E2E tests completed${NC}"
else
    # This should not fail the script since workflow uses || true
    echo -e "${YELLOW}⚠ E2E tests skipped or failed (non-blocking)${NC}"
fi
echo ""

# Summary
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All local checks passed!${NC}"
    echo "This matches the GitHub Actions 'test' job."
    echo "You can safely push to GitHub."
    exit 0
else
    echo -e "${RED}✗ Some checks failed${NC}"
    echo "Fix the issues above before pushing."
    exit 1
fi
