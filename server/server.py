#!/usr/bin/env python3
"""Othello/reversi multiplayer server via WebSocket"""
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

async def handler(ws):
    room = None; player = None
    try:
        async for msg in ws:
            data = json.loads(msg)
            cmd = data.get('cmd')

            if cmd == 'create':
                code = ''.join(random.choices(string.digits, k=4))
                while code in ROOMS: code = ''.join(random.choices(string.digits, k=4))
                ROOMS[code] = {'board': new_board(), 'turn': 'B',
                    'black': ws, 'white': None, 'black_name': data.get('name','?'),
                    'white_name': '?', 'moves': valid_moves(new_board(), 'B')}
                room, player = code, 'B'
                await ws.send(json.dumps({'type':'created','room':code,'player':'B'}))

            elif cmd == 'join':
                code = data.get('room')
                if code not in ROOMS:
                    await ws.send(json.dumps({'type':'error','msg':'Room not found'}))
                    continue
                r = ROOMS[code]
                if r['white']:
                    await ws.send(json.dumps({'type':'error','msg':'Room full'}))
                    continue
                r['white'] = ws; r['white_name'] = data.get('name','?')
                room, player = code, 'W'
                await ws.send(json.dumps({'type':'joined','room':code,'player':'W'}))
                # Notify black
                await r['black'].send(json.dumps({'type':'opponent',
                    'name':r['white_name'],'turn':r['turn'],
                    'board':''.join(r['board']),
                    'moves':r['moves'],
                    'score':score(r['board'])}))

            elif cmd == 'move':
                if not room: continue
                r = ROOMS[room]
                if player != r['turn']:
                    await ws.send(json.dumps({'type':'error','msg':'Not your turn'}))
                    continue
                pos = data.get('pos')
                if pos not in r['moves']:
                    await ws.send(json.dumps({'type':'error','msg':'Invalid move'}))
                    continue
                r['board'] = apply_move(r['board'], pos, player)
                r['turn'] = 'W' if r['turn'] == 'B' else 'B'
                r['moves'] = valid_moves(r['board'], r['turn'])
                s = score(r['board'])
                # If no moves, switch turn
                if not r['moves']:
                    r['turn'] = 'W' if r['turn'] == 'B' else 'B'
                    r['moves'] = valid_moves(r['board'], r['turn'])
                    if not r['moves']:  # Game over
                        bw, wc = s
                        winner = 'B' if bw>wc else 'W' if wc>bw else 'draw'
                        msg = json.dumps({'type':'state','board':''.join(r['board']),
                            'turn':r['turn'],'moves':[],'score':s,
                            'gameover':True,'winner':winner,
                            'black':r['black_name'],'white':r['white_name']})
                state = {'type':'state','board':''.join(r['board']),
                    'turn':r['turn'],'moves':r['moves'],'score':s}
                msg = json.dumps(state)
                await r['black'].send(msg)
                await r['white'].send(msg)
    finally:
        if room and room in ROOMS:
            r = ROOMS[room]
            other = r.get('white') if player=='B' else r.get('black')
            if other: await other.send(json.dumps({'type':'disconnected'}))
            del ROOMS[room]

async def main():
    print("Othello server on :8765")
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
