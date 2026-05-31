#!/bin/bash
# Start all game servers + serveo tunnels, print share links
cd "$(dirname "$0")"

PYTHON=/usr/local/lib/hermes-agent/venv/bin/python3
PIDS=()

cleanup() {
    echo ""
    echo "Stopping all..."
    for pid in "${PIDS[@]}"; do kill $pid 2>/dev/null; done
    rm -f /tmp/game_*.log /tmp/game_tunnel.log
    exit 0
}
trap cleanup INT TERM

# ---- Start a server ----
start_srv() {
    local name=$1 port=$2 script=$3
    echo "Starting $name server on :$port..."
    $PYTHON "$script" $port &
    PIDS+=($!)
    sleep 0.5
}

# ---- Create serveo tunnel ----
tunnel() {
    local name=$1 port=$2
    echo "Tunneling $name..."
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
        -R 80:localhost:$port serveo.net > /tmp/game_${name}.log 2>&1 &
    PIDS+=($!)
    local url=""
    for i in $(seq 1 20); do
        sleep 1
        url=$(grep -oP '[a-zA-Z0-9.-]+\.serveo(usercontent)?\.(com|net)' /tmp/game_${name}.log 2>/dev/null | head -1)
        if [ -n "$url" ]; then
            echo "  $name → serveo: $url"
            return 0
        fi
    done
    echo "  $name → tunnel failed, check /tmp/game_${name}.log"
    return 1
}

# ---- Start everything ----
echo "=== Starting Game Servers ==="

start_srv "othello"  8765 "server.py"
start_srv "monopoly" 8766 "monopoly_server.py"
start_srv "chat"     8767 "chat_demo.py"

echo ""
echo "=== Creating Tunnels ==="
tunnel "othello" 8765
tunnel "monopoly" 8766
tunnel "chat" 8767

# Build links
O=$(grep -oP '[a-zA-Z0-9.-]+\.serveo(usercontent)?\.(com|net)' /tmp/game_othello.log 2>/dev/null | head -1)
M=$(grep -oP '[a-zA-Z0-9.-]+\.serveo(usercontent)?\.(com|net)' /tmp/game_monopoly.log 2>/dev/null | head -1)
C=$(grep -oP '[a-zA-Z0-9.-]+\.serveo(usercontent)?\.(com|net)' /tmp/game_chat.log 2>/dev/null | head -1)

echo ""
echo "=============================================="
echo "  All Games Ready!"
echo ""
[ -n "$O" ] && echo "  Othello:  https://nineeeeeee.github.io/games/othello/?server=$O"
[ -n "$M" ] && echo "  Monopoly: https://nineeeeeee.github.io/games/monopoly/?server=$M"
[ -n "$C" ] && echo "  Chat:     https://nineeeeeee.github.io/games/chat/?server=$C"
echo ""
echo "  Ctrl+C to stop all"
echo "=============================================="
echo ""

wait
