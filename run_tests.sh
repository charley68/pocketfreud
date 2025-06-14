#!/bin/zsh

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BLUE='\033[0;34m'
YELLOW='\033[1;33m'

# Error handling
set -e
setopt ERR_EXIT

check_mysql() {
    echo "${BLUE}Checking MySQL connection...${NC}"
    
    # Try connecting to MySQL without a password prompt
    mysql -u"$DB_USER" -p"$DB_PASS" -h"$DB_HOST" -e "SELECT 1" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "${GREEN}MySQL connection successful${NC}"
        return 0
    fi
    
    echo "${RED}Error: Cannot connect to MySQL. Please check if:${NC}"
    echo "  1. MySQL is running"
    echo "  2. Credentials in test.env are correct"
    echo "  3. User $DB_USER has necessary permissions"
    return 1
}

# Load test environment
echo "${BLUE}Loading test environment...${NC}"
if [[ ! -f "tests/test.env" ]]; then
    echo "${RED}Error: tests/test.env file not found${NC}"
    exit 1
else
    source tests/test.env
fi

# Verify environment variables
if [[ -z "$DB_HOST" || -z "$DB_USER" || -z "$DB_PASS" || -z "$DB_NAME" ]]; then
    echo "${RED}Error: Required database environment variables not set in test.env${NC}"
    exit 1
fi

# Verify MySQL connection
check_mysql || exit 1

echo "${BLUE}Running all tests for PocketFreud...${NC}\n"

echo "${BLUE}Running Python tests...${NC}"
# Add project root to PYTHONPATH
export PYTHONPATH="/Users/stephenlane/Develop/pocketfreud:$PYTHONPATH"

if pytest tests/ -v --no-header --tb=short; then
    echo "${GREEN}Python tests passed successfully!${NC}\n"
    PYTHON_SUCCESS=true
else
    echo "${RED}Python tests failed${NC}\n"
    PYTHON_SUCCESS=false
fi

echo "${BLUE}Running JavaScript tests...${NC}"
if npm test; then
    echo "${GREEN}JavaScript tests passed successfully!${NC}\n"
    JS_SUCCESS=true
else
    echo "${RED}JavaScript tests failed${NC}\n"
    JS_SUCCESS=false
fi

# Generate coverage report if Python tests passed
if [ "$PYTHON_SUCCESS" = true ]; then
    echo "${BLUE}Generating Python coverage report...${NC}"
    python -m pytest --cov=modules --cov=app --cov-report=html tests/ >/dev/null 2>&1
    echo "${GREEN}Coverage report generated in htmlcov/ directory${NC}"
fi

# Final status
if [ "$PYTHON_SUCCESS" = true ] && [ "$JS_SUCCESS" = true ]; then
    echo "\n${GREEN}All tests passed successfully! 🎉${NC}"
    exit 0
else
    echo "\n${RED}Some tests failed. Please check the output above.${NC}"
    exit 1
fi
