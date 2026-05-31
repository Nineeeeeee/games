#!/bin/bash
# Stop all game servers and tunnels
cd "$(dirname "$0")"

# Kill all known server processes
for name in othello monopoly chat; do
    pids=$(pgrep -f "server/$name" 2>/dev/null)
    [ -n "$pids" ] && kill $pids 2>/dev/null
done

# Kill server.py / monopoly_server.py / chat_demo.py
pkill -f "server.py" 2>/dev/null
pkill -f "monopoly_server.py" 2>/dev/null
pkill -f "chat_demo.py" 2>/dev/null

# Kill SSH tunnels
pkill -f "serveo.net" 2>/dev/null

# Clean temp files
rm -f /tmp/game_*.log /tmp/game_tunnel.log

echo "All game servers stopped"
