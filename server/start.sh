#!/bin/bash
# Othello server + localhost.run public tunnel
cd "$(dirname "$0")"

cleanup() {
    echo "Stopping..."
    if [ -f /tmp/othello_pids.txt ]; then
        read SSH_PID SERVER_PID < /tmp/othello_pids.txt
        kill $SSH_PID $SERVER_PID 2>/dev/null
        rm -f /tmp/othello_pids.txt /tmp/othello_tunnel.log
    fi
    exit 0
}
trap cleanup INT TERM

echo "Starting server..."
python3 server.py &
SERVER_PID=$!
sleep 1

echo "Creating public tunnel via localhost.run..."
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    -R 80:localhost:8765 localhost.run > /tmp/othello_tunnel.log 2>&1 &
SSH_PID=$!
echo $SSH_PID $SERVER_PID > /tmp/othello_pids.txt

# Extract URL from tunnel log
URL=""
for i in $(seq 1 30); do
    sleep 2
    URL=$(grep -oP 'https?://[a-zA-Z0-9.-]+\.lhr\.life' /tmp/othello_tunnel.log 2>/dev/null | head -1)
    if [ -n "$URL" ]; then break; fi
done

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║        🎮  Othello Server Ready!                  ║"
if [ -n "$URL" ]; then
    echo "║                                                   ║"
    echo "║  📡 Server:  $URL  ║"
    echo "║                                                   ║"
    echo "║  🔗 Play:                                       ║"
    echo "║     https://nineeeeeee.github.io/games/othello/  ║"
    echo "║                                                   ║"
    echo "║  🤝 Share (friend add as param):                 ║"
    echo "║     ?server=${URL#https://}  ║"
else
    echo "║  ⚠️  Tunnel not yet ready, check log:              ║"
    echo "║  /tmp/othello_tunnel.log                         ║"
fi
echo "║                                                   ║"
echo "║  Ctrl+C to stop                                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

wait $SSH_PID
