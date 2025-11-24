#!/bin/bash
#
# Setup cron job for AI Newsletter
# Usage: ./scripts/setup-cron.sh [monday|daily|12hourly]
#
# Examples:
#   ./scripts/setup-cron.sh monday      # Every Monday 9 AM
#   ./scripts/setup-cron.sh daily       # Every day 9 AM
#   ./scripts/setup-cron.sh 12hourly    # Every 12 hours
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
PYTHON="$(which python3 || which python)"

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default schedule
SCHEDULE="${1:-monday}"

echo -e "${BLUE}=== AI Newsletter Cron Setup ===${NC}"
echo "Project directory: $PROJECT_DIR"
echo "Python executable: $PYTHON"
echo "Schedule: $SCHEDULE"
echo

# Determine cron expression based on schedule
case $SCHEDULE in
    monday)
        # Every Monday at 9:00 AM
        CRON_EXPR="0 9 * * 1"
        DESC="Every Monday at 9:00 AM UTC"
        ;;
    daily)
        # Every day at 9:00 AM
        CRON_EXPR="0 9 * * *"
        DESC="Every day at 9:00 AM UTC"
        ;;
    12hourly)
        # Every 12 hours (midnight and noon)
        CRON_EXPR="0 */12 * * *"
        DESC="Every 12 hours (00:00 and 12:00 UTC)"
        ;;
    *)
        echo -e "${YELLOW}Unknown schedule: $SCHEDULE${NC}"
        echo "Valid options: monday, daily, 12hourly"
        exit 1
        ;;
esac

# Create the cron command
CRON_CMD="$CRON_EXPR cd $PROJECT_DIR && $PYTHON -m src.main --log-level INFO >> logs/cron.log 2>&1"

echo -e "${BLUE}Schedule: $DESC${NC}"
echo "Cron expression: $CRON_EXPR"
echo "Command: $CRON_CMD"
echo

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "src.main"; then
    echo -e "${YELLOW}Cron job already exists!${NC}"
    echo "Current cron jobs:"
    crontab -l | grep "src.main" || true
    echo
    read -p "Remove old cron job and create new one? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove old cron job
        (crontab -l 2>/dev/null | grep -v "src.main") | crontab - || true
        echo -e "${GREEN}Old cron job removed${NC}"
    else
        echo "Aborting setup"
        exit 1
    fi
fi

# Add new cron job
(crontab -l 2>/dev/null || true; echo "$CRON_CMD") | crontab -
echo -e "${GREEN}✓ Cron job added successfully!${NC}"
echo

# Verify installation
echo "Verifying installation..."
if crontab -l | grep -q "src.main"; then
    echo -e "${GREEN}✓ Cron job installed and verified${NC}"
    echo
    echo "Cron jobs for this project:"
    crontab -l | grep "src.main"
else
    echo -e "${YELLOW}Warning: Could not verify cron installation${NC}"
    exit 1
fi

echo
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo
echo "Next steps:"
echo "1. Test the newsletter manually:"
echo "   cd $PROJECT_DIR"
echo "   python -m src.main --log-level INFO"
echo
echo "2. Monitor logs:"
echo "   tail -f $PROJECT_DIR/logs/cron.log"
echo
echo "3. List all cron jobs:"
echo "   crontab -l"
echo
echo "4. Edit cron jobs:"
echo "   crontab -e"
echo
echo "5. Remove cron job (if needed):"
echo "   crontab -l | grep -v 'src.main' | crontab -"
echo
