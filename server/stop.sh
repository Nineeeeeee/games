#!/bin/bash
# Stop Othello server and tunnel
if [ -f /tmp/othello_pids.txt ]; then
    read SSH_PID SERVER_PID < /tmp/othello_pids.txt
    kill $SSH_PID $SERVER_PID 2>/dev/null
    rm -f /tmp/othello_pids.txt /tmp/othello_url.txt
    echo "Othello server stopped"
else
    echo "No running server found"
fi
