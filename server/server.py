#!/usr/bin/env python3
"""Othello/reversi multiplayer server with room wait + start"""
import asyncio, json, websockets, random, string

ROOMS = {}
DIRS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

def new_board():
    b = ['.']*64
    b[27]=b[36]='W'; b[28]=b[35]='B'
    return b

def valid_moves(board, player):
    moves = []
    opp = 'W' if player == 'B' else 'B'
    for i in range(64):
        if board[i] != '.': continue
        r, c = i//8, i%8
        for dr, dc in DIRS:
            nr, nc = r+dr, c+dc
            if not (0<=nr<8 and 0<=nc<8): continue
            if board[nr*8+nc] != opp: continue
            for _ in range(6):
                nr += dr; nc += dc
                if not (0<=nr<8 and 0<=nc<8): break
                if board[nr*8+nc] == '.': break
                if board[nr*8+nc] == player:
                    moves.append(i); break
            else: continue
            break
    return moves

def apply_move(board, pos, player):
    b = board[:]
    b[pos] = player
    r, c = pos//8, pos%8
    opp = 'W' if player == 'B' else 'B'
    for dr, dc in DIRS:
        nr, nc = r+dr, c+dc
        flips = []
        while 0<=nr<8 and 0<=nc<8 and b[nr*8+nc]==opp:
            flips.append(nr*8+nc)
            nr+=dr; nc+=dc
        if 0<=nr<8 and 0<=nc<8 and b[nr*8+nc]==player:
            for f in flips: b[f]=player
    return b

def score(board):
    return sum(1 for c in board if c=='B'), sum(1 for c in board if c=='W')

def room_players(r):
    """Return player list for room update"""
    return [
        {'name': r.get('host_name','?'), 'role': 'host'},
        {'name': r.get('guest_name','?'), 'role': 'guest'}
    ]

async def broadcast_room_update(room):
    """Send player list to all in room"""
    r = ROOMS[room]
    msg = json.dumps({'type': 'room_update', 'players': room_players(r), 'room': room})
    targets = [r['host'], r['guest']] if r['guest'] else [r['host']]
    for t in targets:
        try: await t.send(msg)
        except: pass

async def handler(ws):
    room = None; player = None
    try:
        async for msg in ws:
            data = json.loads(msg)
            cmd = data.get('cmd')

            if cmd == 'create':
                code = ''.join(random.choices(string.digits, k=4))
                while code in ROOMS: code = ''.join(random.choices(string.digits, k=4))
                ROOMS[code] = {
                    'board': None, 'turn': None, 'moves': None,
                    'host': ws, 'host_name': data.get('name','?'),
                    'guest': None, 'guest_name': None,
                    'started': False
                }
                room, player = code, 'host'
                await ws.send(json.dumps({'type':'created','room':code,'player':'host'}))

            elif cmd == 'join':
                code = data.get('room')
                if code not in ROOMS:
                    await ws.send(json.dumps({'type':'error','msg':'Room not found'}))
                    continue
                r = ROOMS[code]
                if r['guest']:
                    await ws.send(json.dumps({'type':'error','msg':'Room full'}))
                    continue
                r['guest'] = ws; r['guest_name'] = data.get('name','?')
                room, player = code, 'guest'
                await ws.send(json.dumps({'type':'joined','room':code,'player':'guest'}))
                # Notify everyone about player list
                await broadcast_room_update(room)

            elif cmd == 'start':
                if not room: continue
                r = ROOMS[room]
                if player != 'host':
                    await ws.send(json.dumps({'type':'error','msg':'Only host can start'}))
                    continue
                if not r['guest']:
                    await ws.send(json.dumps({'type':'error','msg':'Waiting for opponent'}))
                    continue
                if r['started']:
                    await ws.send(json.dumps({'type':'error','msg':'Game already started'}))
                    continue
                # Start the game
                r['board'] = new_board()
                r['turn'] = 'B'
                r['moves'] = valid_moves(r['board'], 'B')
                r['started'] = True
                s = score(r['board'])
                state = {'type':'game_start','board':''.join(r['board']),
                    'turn':r['turn'],'moves':r['moves'],'score':s,
                    'black':r['host_name'],'white':r['guest_name']}
                await r['host'].send(json.dumps(state))
                await r['guest'].send(json.dumps(state))

            elif cmd == 'move':
                if not room: continue
                r = ROOMS[room]
                if not r['started']:
                    await ws.send(json.dumps({'type':'error','msg':'Game not started'}))
                    continue
                # Map player role to piece
                p = 'B' if player == 'host' else 'W'
                if p != r['turn']:
                    await ws.send(json.dumps({'type':'error','msg':'Not your turn'}))
                    continue
                pos = data.get('pos')
                if pos not in r['moves']:
                    await ws.send(json.dumps({'type':'error','msg':'Invalid move'}))
                    continue
                r['board'] = apply_move(r['board'], pos, p)
                r['turn'] = 'W' if r['turn'] == 'B' else 'B'
                r['moves'] = valid_moves(r['board'], r['turn'])
                s = score(r['board'])
                # Auto-switch if no moves
                if not r['moves']:
                    r['turn'] = 'W' if r['turn'] == 'B' else 'B'
                    r['moves'] = valid_moves(r['board'], r['turn'])
                    if not r['moves']:  # Game over
                        bw, wc = s
                        winner = 'B' if bw>wc else 'W' if wc>bw else 'draw'
                        state = json.dumps({'type':'state','board':''.join(r['board']),
                            'turn':r['turn'],'moves':[],'score':s,
                            'gameover':True,'winner':winner,
                            'black':r['host_name'],'white':r['guest_name']})
                        await r['host'].send(state)
                        await r['guest'].send(state)
                        del ROOMS[room]
                        break
                state = {'type':'state','board':''.join(r['board']),
                    'turn':r['turn'],'moves':r['moves'],'score':s}
                msg = json.dumps(state)
                await r['host'].send(msg)
                await r['guest'].send(msg)

    finally:
        if room and room in ROOMS:
            r = ROOMS[room]
            if not r['started']:
                # Room not started, just remove
                other = r['guest'] if player=='host' else r['host']
                if other:
                    try: await other.send(json.dumps({'type':'disconnected','msg':'The other player left'}))
                    except: pass
                del ROOMS[room]
            else:
                # Game in progress, cleanup
                other = r.get('guest') if player=='host' else r.get('host')
                if other:
                    try: await other.send(json.dumps({'type':'disconnected','msg':'Opponent disconnected'}))
                    except: pass
                del ROOMS[room]

async def main():
    print("Othello server on :8765 (with room wait)")
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
