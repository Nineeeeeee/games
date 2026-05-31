#!/usr/bin/env python3
"""Chat demo — pure WebSocket, same pattern as Othello server"""
import asyncio, json, sys, websockets

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8767

CLIENTS = {}

async def handler(ws):
    name = '???'; CLIENTS[ws] = name
    try:
        async for msg in ws:
            try:
                d = json.loads(msg)
                if d.get('t') == 'join':
                    name = d.get('n','???')[:12]; CLIENTS[ws] = name
                    await broadcast({'t':'join','n':name,'c':len(CLIENTS)})
                elif d.get('t') == 'msg':
                    await broadcast({'t':'msg','n':CLIENTS.get(ws,'?'),'m':d.get('m','')[:500]})
            except: pass
    finally:
        if ws in CLIENTS:
            n = CLIENTS.pop(ws)
            await broadcast({'t':'leave','n':n,'c':len(CLIENTS)})

async def broadcast(data):
    if CLIENTS:
        m = json.dumps(data, ensure_ascii=False)
        await asyncio.gather(*[c.send(m) for c in list(CLIENTS)], return_exceptions=True)

async def main():
    async with websockets.serve(handler, "localhost", PORT):
        print(f"Chat WS on localhost:{PORT}")
        await asyncio.Future()

asyncio.run(main())
