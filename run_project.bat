@echo off
title Primasistant-HR Starter

echo Starting Backend...
start "Backend" cmd /k "cd /d %~dp0backend && conda activate ragmcp && python app.py"

echo Starting MCP Server...
start "MCP Server" cmd /k "cd /d %~dp0backend\MCP && conda activate ragmcp && python mcp_server.py"

echo Starting Frontend...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo All processes have been launched in separate windows.
echo You can close this window now.
pause
