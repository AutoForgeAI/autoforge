#!/bin/bash

# =============================================================================
# AutoCoder Service Manager (local_deploy.sh)
# =============================================================================
# Unified script for deploying, controlling, and troubleshooting AutoCoder.
#
# Usage:
#   ./local_deploy.sh [command]
#
# Commands:
#   dev     - Stop, pull, and start with hot-reload (default if running)
#   prod    - Stop, pull, build, and start production mode
#   stop    - Stop all running processes
#   restart - Restart in current mode (auto-detects dev/prod)
#   status  - Show running processes and ports
#   pull    - Pull latest changes from master
#   logs    - View recent service logs
#   clean   - Kill orphan processes and remove lock files
#   help    - Show this help menu
# =============================================================================

MODE=${1:-"help"}

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# =============================================================================
# Helper Functions
# =============================================================================

show_help() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════╗"
    echo "║        AUTOCODER SERVICE MANAGER             ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║  DEPLOY:                                     ║"
    echo "║    dev    - Pull & start development mode    ║"
    echo "║    prod   - Pull, build & start production   ║"
    echo "║                                              ║"
    echo "║  CONTROL:                                    ║"
    echo "║    stop    - Stop all processes              ║"
    echo "║    restart - Restart current mode            ║"
    echo "║    status  - Show process status             ║"
    echo "║                                              ║"
    echo "║  MAINTENANCE:                                ║"
    echo "║    pull    - Pull latest from master         ║"
    echo "║    logs    - View recent logs                ║"
    echo "║    clean   - Kill orphans & remove locks     ║"
    echo "╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
}

stop_processes() {
    echo -e "${YELLOW}Stopping all running AutoCoder processes...${NC}"

    # Graceful shutdown first (SIGTERM) - gives processes time to close WebSockets cleanly
    pkill -TERM -f "uvicorn" 2>/dev/null
    pkill -TERM -f "vite" 2>/dev/null
    pkill -TERM -f "start_ui.py" 2>/dev/null
    pkill -TERM -f "start_ui.sh" 2>/dev/null

    # Wait for graceful shutdown
    sleep 2

    # Force kill any remaining processes (SIGKILL)
    pkill -9 -f "uvicorn" 2>/dev/null
    pkill -9 -f "vite" 2>/dev/null
    pkill -9 -f "start_ui.py" 2>/dev/null
    pkill -9 -f "start_ui.sh" 2>/dev/null

    sleep 1
    echo -e "${GREEN}All processes stopped.${NC}"
}

pull_latest() {
    echo -e "${BLUE}Pulling latest changes from origin/master...${NC}"
    git fetch origin master
    git merge origin/master --no-edit
    echo -e "${GREEN}Repository updated.${NC}"
}

status_check() {
    echo -e "${BOLD}=== AutoCoder Service Status ===${NC}"
    echo ""

    echo -e "${CYAN}Port 8888 (API Server):${NC}"
    if lsof -i :8888 >/dev/null 2>&1; then
        lsof -i :8888 2>/dev/null | head -5
        echo -e "${GREEN}  ✓ Running${NC}"
    else
        echo -e "${RED}  ✗ Not running${NC}"
    fi
    echo ""

    echo -e "${CYAN}Port 5173 (Vite Dev Server):${NC}"
    if lsof -i :5173 >/dev/null 2>&1; then
        lsof -i :5173 2>/dev/null | head -5
        echo -e "${GREEN}  ✓ Running (DEV mode)${NC}"
    else
        echo -e "${YELLOW}  - Not running (PROD mode or stopped)${NC}"
    fi
    echo ""

    echo -e "${CYAN}Agent Lock Files:${NC}"
    LOCK_COUNT=$(find . -name ".agent.lock" 2>/dev/null | wc -l)
    if [ "$LOCK_COUNT" -gt 0 ]; then
        find . -name ".agent.lock" 2>/dev/null
        echo -e "${YELLOW}  Found $LOCK_COUNT lock file(s)${NC}"
    else
        echo -e "${GREEN}  No lock files found${NC}"
    fi
}

view_logs() {
    echo -e "${BOLD}=== Recent Logs ===${NC}"
    echo ""

    # Check for common log locations
    if [ -f ~/.autocoder/service.log ]; then
        echo -e "${CYAN}~/.autocoder/service.log:${NC}"
        tail -50 ~/.autocoder/service.log
    elif [ -f ./logs/server.log ]; then
        echo -e "${CYAN}./logs/server.log:${NC}"
        tail -50 ./logs/server.log
    else
        echo -e "${YELLOW}No log files found. Logs may be in terminal output.${NC}"
        echo ""
        echo "Tip: Run with './local_deploy.sh dev 2>&1 | tee ~/.autocoder/service.log'"
    fi
}

cleanup() {
    echo -e "${YELLOW}=== Cleanup Starting ===${NC}"
    echo ""

    echo -e "${BLUE}Killing orphan processes...${NC}"
    pkill -9 -f "uvicorn" 2>/dev/null && echo "  Killed uvicorn processes" || echo "  No uvicorn processes"
    pkill -9 -f "vite" 2>/dev/null && echo "  Killed vite processes" || echo "  No vite processes"
    pkill -9 -f "node.*autocoder" 2>/dev/null && echo "  Killed node processes" || echo "  No node processes"
    pkill -9 -f "start_ui.py" 2>/dev/null && echo "  Killed start_ui processes" || echo "  No start_ui processes"

    echo ""
    echo -e "${BLUE}Removing lock files...${NC}"
    LOCK_COUNT=$(find . -name ".agent.lock" 2>/dev/null | wc -l)
    find . -name ".agent.lock" -delete 2>/dev/null
    echo "  Removed $LOCK_COUNT project lock file(s)"

    # Clean up ~/.autocoder lock files if they exist
    if [ -d ~/.autocoder ]; then
        find ~/.autocoder -name "*.lock" -delete 2>/dev/null
        echo "  Cleaned ~/.autocoder locks"
    fi

    echo ""
    echo -e "${GREEN}=== Cleanup Complete ===${NC}"
}

restart_service() {
    echo -e "${BLUE}=== Restarting Service ===${NC}"

    # Detect current mode by checking if Vite dev server is running
    if lsof -i :5173 >/dev/null 2>&1; then
        RESTART_MODE="dev"
        echo -e "${CYAN}Detected: Development mode${NC}"
    else
        RESTART_MODE="prod"
        echo -e "${CYAN}Detected: Production mode${NC}"
    fi

    stop_processes
    sleep 2

    echo -e "${BLUE}Starting in ${RESTART_MODE} mode...${NC}"
    case $RESTART_MODE in
        "dev")
            python3 start_ui.py --dev
            ;;
        "prod")
            python3 start_ui.py
            ;;
    esac
}

# =============================================================================
# Main Command Handler
# =============================================================================

case $MODE in
    "help"|"-h"|"--help"|"")
        show_help
        exit 0
        ;;
    "stop")
        stop_processes
        exit 0
        ;;
    "pull")
        pull_latest
        exit 0
        ;;
    "status")
        status_check
        exit 0
        ;;
    "logs")
        view_logs
        exit 0
        ;;
    "clean")
        cleanup
        exit 0
        ;;
    "restart")
        restart_service
        ;;
    "dev")
        stop_processes
        pull_latest
        echo -e "${BLUE}Launching in DEVELOPMENT mode (Hotload enabled)...${NC}"
        python3 start_ui.py --dev
        ;;
    "prod")
        stop_processes
        pull_latest
        echo -e "${BLUE}Launching in PRODUCTION mode...${NC}"
        python3 start_ui.py
        ;;
    *)
        echo -e "${RED}Invalid command: $MODE${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
