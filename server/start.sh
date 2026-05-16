#!/bin/bash
# Start Othello server + public tunnel
# Usage: bash start.sh

cd "$(dirname "$0")"

# 1. Start server in background
echo "Starting Othello server..."
python3 server.py &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 1

# 2. Create SSH tunnel via localhost.run
echo "Creating public tunnel..."
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    -R 80:localhost:8765 localhost.run 2>&1 | while read line; do
    echo "$line"
    # Extract the URL
    if echo "$line" | grep -qoP 'https?://[a-zA-Z0-9.-]+\.lhr\.life'; then
        URL=$(echo "$line" | grep -oP 'https?://[a-zA-Z0-9.-]+\.lhr\.life')
        echo ""
        echo "============================================"
        echo "  🎮 Game URL: $URL"
        echo "  发送这个链接给朋友即可对战"
        echo "  按 Ctrl+C 关闭服务器"
        echo "============================================"
        # Save URL for stop script
        echo "$URL" > /tmp/othello_url.txt
        echo "$SSH_PID $SERVER_PID" > /tmp/othello_pids.txt
    fi
done &
SSH_PID=$!

# Save PIDs
echo "$SSH_PID $SERVER_PID" > /tmp/othello_pids.txt

echo ""
echo "服务已启动。使用 stop.sh 关闭。"
echo "PID saved to /tmp/othello_pids.txt"

# Wait for any signal
trap "kill $SERVER_PID $SSH_PID 2>/dev/null; echo 'Server stopped'" INT TERM
wait $SSH_PID 2>/dev/null
