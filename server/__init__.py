"""
FastAPI Backend Server
======================

Web UI server for the Autonomous Coding Agent.
Provides REST API and WebSocket endpoints for project management,
feature tracking, and agent control.
"""

# Fix Windows asyncio subprocess support - MUST be before any other imports
# that might create an event loop
import sys

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
