#!/usr/bin/env python3
"""Monopoly multiplayer server - supports 2-6 players"""
import asyncio, json, websockets, random, string

ROOMS = {}

# ===== Board =====
CELLS = [
    # name, type, price, rent
    ("起点",     "start",     0,   0),
    ("东街",     "property", 200,  50),
    ("机会",     "chance",    0,   0),
    ("南街",     "property", 220,  55),
    ("缴税",     "tax",       0,   0),
    ("西街",     "property", 260,  65),
    ("北街",     "property", 280,  70),
    ("人民路",   "property", 300,  75),
    ("监狱",     "jail",      0,   0),
    ("南京路",   "property", 320,  80),
    ("淮海路",   "property", 350,  85),
    ("机会",     "chance",    0,   0),
    ("延安路",   "property", 370,  90),
    ("长安街",   "property", 390,  95),
    ("解放路",   "property", 420, 100),
    ("建设路",   "property", 450, 110),
    ("免费停车", "parking",   0,   0),
    ("黄河路",   "property", 480, 120),
    ("长江路",   "property", 500, 130),
    ("机会",     "chance",    0,   0),
    ("珠江路",   "property", 520, 140),
    ("泰山路",   "property", 550, 150),
    ("华山道",   "property", 580, 160),
    ("昆仑关",   "property", 600, 170),
    ("前往监狱", "gojail",    0,   0),
    ("前门大街", "property", 200,  50),
    ("王府井",   "property", 220,  55),
    ("机会",     "chance",    0,   0),
    ("外滩",     "property", 260,  65),
    ("陆家嘴",   "property", 280,  70),
    ("缴税",     "tax",       0,   0),
    ("中关村",   "property", 300,  75),
]

CHANCES = [
    "银行发放红利，获得 $200",
    "中了彩票，获得 $300",
    "缴纳医疗费，损失 $100",
    "继承遗产，获得 $250",
    "去澳门旅游，损失 $150",
    "投资收益，获得 $400",
    "汽车维修费，损失 $200",
    "生日快乐！每人给你 $50",
    "缴纳学费，损失 $150",
    "股票分红，获得 $350",
]

COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#e67e22"]
COLOR_NAMES = ["红", "蓝", "绿", "黄", "紫", "橙"]

def new_board():
    return [0]*32  # owner indices, -1 = none

def roll_dice():
    return random.randint(1, 6)

def shuffle_chances():
    c = CHANCES[:]
    random.shuffle(c)
    return c

def find_next_player(players, current):
    n = len(players)
    for i in range(1, n):
        idx = (current + i) % n
        if players[idx]['alive']:
            return idx
    return current

# ===== Room Management =====

def room_players(r):
    return [{'name': p['name'], 'color': p['color'], 'alive': p['alive'],
             'money': p['money'], 'pos': p['pos'], 'props': p['props']}
            for p in r['players']]

async def broadcast(room, msg):
    msg_s = json.dumps(msg)
    for p in room['players']:
        try: await p['ws'].send(msg_s)
        except: pass

async def broadcast_state(room):
    """Send full game state to all players"""
    state = {
        'type': 'state',
        'players': room_players(room),
        'current': room['turn_index'],
        'phase': room['phase'],
        'dice': room['dice'],
        'board': room['board'],
        'owner_names': [room['players'][o]['name'] if o >= 0 else None for o in room['board']],
        'message': room['message']
    }
    await broadcast(room, state)

# ===== Game Logic =====

async def handle_game_command(room, player_idx, cmd, data):
    """Process an in-game command"""
    if room['phase'] == 'ended':
        return

    p = room['players'][player_idx]
    turn = room['turn_index']

    if cmd == 'roll':
        if player_idx != turn:
            await p['ws'].send(json.dumps({'type': 'error', 'msg': '还没轮到你'}))
            return
        if room['phase'] != 'rolling':
            return

        d = roll_dice()
        room['dice'] = [d]
        room['message'] = f"{p['name']} 掷出了 {d} 点"

        # Move
        new_pos = (p['pos'] + d) % 32
        p['pos'] = new_pos

        # Check if passed start (going backwards: if new_pos < old_pos accounting for wrap)
        # Actually, since we always move forward, passing start = new_pos < old_pos + d but >=0
        # passing start = position wrapped around
        if p['pos'] < room['_last_pos']:
            p['money'] += 200
            room['message'] += f"，经过起点获得 $200"

        cell = CELLS[new_pos]
        await broadcast_state(room)
        await asyncio.sleep(1)

        # Handle cell
        await handle_cell(room, player_idx, cell)

    elif cmd == 'buy':
        if player_idx != turn:
            await p['ws'].send(json.dumps({'type': 'error', 'msg': '还没轮到你'}))
            return
        if room['phase'] != 'buying':
            return

        cell_idx = p['pos']
        cell = CELLS[cell_idx]
        if cell[1] != 'property' or room['board'][cell_idx] >= 0:
            return
        if p['money'] < cell[2]:
            await p['ws'].send(json.dumps({'type': 'error', 'msg': '资金不足'}))
            return

        p['money'] -= cell[2]
        room['board'][cell_idx] = player_idx
        p['props'].append(cell_idx)
        room['message'] = f"{p['name']} 购买了 {cell[0]}（${cell[2]}）"
        room['phase'] = 'done'
        await broadcast_state(room)

    elif cmd == 'skip_buy':
        if player_idx != turn:
            await p['ws'].send(json.dumps({'type': 'error', 'msg': '还没轮到你'}))
            return
        if room['phase'] != 'buying':
            return
        room['phase'] = 'done'
        room['message'] = f"{p['name']} 放弃了购买"
        await broadcast_state(room)

    elif cmd == 'end_turn':
        if player_idx != turn:
            await p['ws'].send(json.dumps({'type': 'error', 'msg': '还没轮到你'}))
            return
        if room['phase'] != 'done' and room['phase'] != 'rolling':
            return

        await next_turn(room)


async def handle_cell(room, player_idx, cell):
    p = room['players'][player_idx]
    ctype = cell[1]

    if ctype == 'property':
        owner = room['board'][p['pos']]
        if owner < 0:
            # Nobody owns it
            if p['money'] >= cell[2]:
                room['phase'] = 'buying'
                room['message'] = f"{p['name']} 到达 {cell[0]}，售价 ${cell[2]}，要购买吗？"
                await p['ws'].send(json.dumps({
                    'type': 'need_decision',
                    'action': 'buy',
                    'cell_name': cell[0],
                    'price': cell[2],
                    'money': p['money']
                }))
                await broadcast_state(room)
            else:
                room['message'] = f"{p['name']} 到达 {cell[0]}，资金不足无法购买"
                room['phase'] = 'done'
                await broadcast_state(room)
        elif owner != player_idx:
            # Pay rent
            rent = cell[3]
            p['money'] -= rent
            room['players'][owner]['money'] += rent
            room['message'] = f"{p['name']} 支付 ${rent} 租金给 {room['players'][owner]['name']}"
            await check_bankruptcy(room, player_idx)
            if room['phase'] != 'ended':
                room['phase'] = 'done'
                await broadcast_state(room)
        else:
            room['message'] = f"{p['name']} 回到自己的地产 {cell[0]}"
            room['phase'] = 'done'
            await broadcast_state(room)

    elif ctype == 'chance':
        card = room['chances'].pop(0)
        room['chances'].append(card)  # recycle
        room['message'] = f"{p['name']} 抽到机会卡：{card}"
        # Parse card effect
        if '200' in card and '获得' in card:
            p['money'] += 200
        elif '300' in card and '获得' in card:
            p['money'] += 300
        elif '250' in card and '获得' in card:
            p['money'] += 250
        elif '400' in card and '获得' in card:
            p['money'] += 400
        elif '350' in card and '获得' in card:
            p['money'] += 350
        elif '损失 100' in card:
            p['money'] -= 100
        elif '损失 150' in card:
            p['money'] -= 150
        elif '损失 200' in card:
            p['money'] -= 200
        elif '每人给你' in card:
            bonus = 50 * len(room['players'])
            p['money'] += bonus
            for i, op in enumerate(room['players']):
                if i != player_idx and op['alive']:
                    op['money'] -= 50

        await check_bankruptcy(room, player_idx)
        if room['phase'] != 'ended':
            room['phase'] = 'done'
            await broadcast_state(room)

    elif ctype == 'tax':
        p['money'] -= 100
        room['message'] = f"{p['name']} 缴税 $100"
        await check_bankruptcy(room, player_idx)
        if room['phase'] != 'ended':
            room['phase'] = 'done'
            await broadcast_state(room)

    elif ctype == 'gojail':
        p['pos'] = 8  # jail cell
        room['message'] = f"{p['name']} 被送进监狱！"
        room['phase'] = 'done'
        await broadcast_state(room)

    elif ctype in ('start', 'jail', 'parking'):
        room['message'] = f"{p['name']} 到达 {cell[0]}"
        room['phase'] = 'done'
        await broadcast_state(room)


async def check_bankruptcy(room, player_idx):
    p = room['players'][player_idx]
    if p['money'] <= 0 and sum(CELLS[prop][3] for prop in p['props']) < abs(p['money']):
        # Bankrupt - can't even cover with max rent
        p['alive'] = False
        # Release properties
        for prop_idx in p['props']:
            room['board'][prop_idx] = -1
        p['props'] = []
        alive_count = sum(1 for pl in room['players'] if pl['alive'])
        room['message'] = f"{p['name']} 破产了！"
        await broadcast_state(room)

        if alive_count <= 1:
            winner_idx = next(i for i, pl in enumerate(room['players']) if pl['alive'])
            room['phase'] = 'ended'
            room['message'] = f"游戏结束！{room['players'][winner_idx]['name']} 获胜！"
            await broadcast(room, {
                'type': 'game_over',
                'winner': room['players'][winner_idx]['name'],
                'winner_idx': winner_idx,
                'players': room_players(room)
            })


async def next_turn(room):
    room['turn_index'] = find_next_player(room['players'], room['turn_index'])
    room['phase'] = 'rolling'
    room['dice'] = []
    p = room['players'][room['turn_index']]
    room['message'] = f"轮到 {p['name']} 了"
    room['_last_pos'] = p['pos']
    await broadcast_state(room)
    await p['ws'].send(json.dumps({'type': 'your_turn'}))


# ===== WebSocket Handler =====

async def handler(ws):
    room = None
    player_idx = None

    try:
        async for msg in ws:
            data = json.loads(msg)
            cmd = data.get('cmd')

            # ---- Lobby commands ----
            if cmd == 'create':
                max_p = min(max(int(data.get('max_players', 4)), 2), 6)
                code = ''.join(random.choices(string.digits, k=4))
                while code in ROOMS: code = ''.join(random.choices(string.digits, k=4))
                name = data.get('name', 'Player')
                ROOMS[code] = {
                    'players': [{
                        'ws': ws, 'name': name, 'color': COLORS[0],
                        'money': 1500, 'pos': 0, 'props': [], 'alive': True,
                    }],
                    'board': new_board(),
                    'chances': shuffle_chances(),
                    'turn_index': 0,
                    'phase': 'waiting',  # waiting / rolling / buying / done / ended
                    'dice': [],
                    'message': '等待玩家加入...',
                    'max_players': max_p,
                    'started': False,
                    '_last_pos': 0,
                }
                room = code
                player_idx = 0
                await ws.send(json.dumps({
                    'type': 'created', 'room': code,
                    'player_idx': 0, 'players': room_players(ROOMS[code]),
                    'max_players': max_p
                }))

            elif cmd == 'join':
                code = data.get('room')
                if code not in ROOMS:
                    await ws.send(json.dumps({'type': 'error', 'msg': '房间不存在'}))
                    continue
                r = ROOMS[code]
                if r['started']:
                    await ws.send(json.dumps({'type': 'error', 'msg': '游戏已开始'}))
                    continue
                if len(r['players']) >= r['max_players']:
                    await ws.send(json.dumps({'type': 'error', 'msg': '房间已满'}))
                    continue

                idx = len(r['players'])
                name = data.get('name', f'Player{idx+1}')
                r['players'].append({
                    'ws': ws, 'name': name, 'color': COLORS[idx],
                    'money': 1500, 'pos': 0, 'props': [], 'alive': True,
                })
                room = code
                player_idx = idx
                await ws.send(json.dumps({
                    'type': 'joined', 'room': code,
                    'player_idx': idx, 'players': room_players(r),
                    'max_players': r['max_players']
                }))
                await broadcast(r, {'type': 'room_update', 'players': room_players(r), 'max_players': r['max_players']})

            elif cmd == 'start':
                if not room: continue
                r = ROOMS[room]
                if r['started']:
                    await ws.send(json.dumps({'type': 'error', 'msg': '游戏已开始'}))
                    continue
                if len(r['players']) < 2:
                    await ws.send(json.dumps({'type': 'error', 'msg': '至少需要2名玩家'}))
                    continue
                if player_idx != 0:
                    await ws.send(json.dumps({'type': 'error', 'msg': '只有房主可以开始'}))
                    continue

                r['started'] = True
                r['phase'] = 'rolling'
                r['_last_pos'] = 0
                r['message'] = f"游戏开始！{r['players'][0]['name']} 先手"
                await broadcast(r, {'type': 'game_start', 'players': room_players(r)})
                await broadcast_state(r)
                await r['players'][0]['ws'].send(json.dumps({'type': 'your_turn'}))

            # ---- In-game commands ----
            elif cmd in ('roll', 'buy', 'skip_buy', 'end_turn'):
                if not room or room not in ROOMS: continue
                r = ROOMS[room]
                if not r['started']:
                    await ws.send(json.dumps({'type': 'error', 'msg': '游戏未开始'}))
                    continue
                await handle_game_command(r, player_idx, cmd, data)

    finally:
        if room and room in ROOMS:
            r = ROOMS[room]
            if r['started']:
                r['players'][player_idx]['alive'] = False
                await broadcast(r, {'type': 'disconnected', 'msg': f"{r['players'][player_idx]['name']} 掉线了"})
                if sum(1 for p in r['players'] if p['alive']) <= 1:
                    r['phase'] = 'ended'
                    winners = [p for p in r['players'] if p['alive']]
                    if winners:
                        await broadcast(r, {'type': 'game_over', 'winner': winners[0]['name'],
                            'winner_idx': r['players'].index(winners[0]), 'players': room_players(r)})
            else:
                r['players'] = [p for p in r['players'] if p['ws'] != ws]
                if r['players']:
                    await broadcast(r, {'type': 'room_update', 'players': room_players(r), 'max_players': r['max_players']})
                else:
                    del ROOMS[room]


async def main():
    print("Monopoly server on :8766")
    async with websockets.serve(handler, "localhost", 8766):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
