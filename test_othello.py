#!/usr/bin/env python3
"""Test Othello game end-to-end via CDP"""
import subprocess, time, random, json, asyncio, urllib.request, websockets

ps = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
curl = "/mnt/c/Windows/System32/curl.exe"
chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
SERVEO = "4845527d61a63cf4-45-8-220-99.serveousercontent.com"
GAME = f"https://nineeeeeee.github.io/games/othello/?server={SERVEO}"

# Start Chrome CDP
print("Starting Chrome...")
subprocess.run([ps, "-NoProfile", "-Command", "Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force"], timeout=10)
time.sleep(3)
tmp = f"C:\\Temp\\cdp_{random.randint(10000,99999)}"
subprocess.run([ps, "-NoProfile", "-Command",
    f"Start-Process -FilePath '{chrome}' -ArgumentList @('--remote-debugging-port=9222','--remote-allow-origins=*','--no-first-run','--no-default-browser-check','--user-data-dir={tmp}','about:blank')"],
    timeout=10)
for i in range(10):
    time.sleep(2)
    r = subprocess.run([curl, "-s", "--max-time", "2", "http://127.0.0.1:9222/json/version"], capture_output=True, timeout=5)
    if r.stdout and b"Browser" in r.stdout:
        print(f"CDP ready: {json.loads(r.stdout)['Browser']}")
        break
else:
    print("CDP FAIL"); exit(1)

async def main():
    req = urllib.request.Request("http://127.0.0.1:9222/json/version")
    with urllib.request.urlopen(req, timeout=5) as resp:
        bw = json.loads(resp.read())["webSocketDebuggerUrl"]

    async with websockets.connect(bw, close_timeout=5) as cw:
        try:
            while True: await asyncio.wait_for(cw.recv(), timeout=0.3)
        except: pass

        # Create tab for serveo first (dismiss warning)
        print("1. Visiting serveo warning page...")
        await cw.send(json.dumps({"id":1,"method":"Target.createTarget","params":{"url":f"https://{SERVEO}"}}))
        tid = None
        for _ in range(30):
            try:
                msg = json.loads(await asyncio.wait_for(cw.recv(), timeout=2))
                if msg.get("id") == 1: tid = msg["result"]["targetId"]; break
            except: pass
        if not tid: print("Tab fail"); return

        await asyncio.sleep(1)
        req2 = urllib.request.Request("http://127.0.0.1:9222/json")
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            tabs = json.loads(resp2.read())
        page_ws = None
        for t in tabs:
            if t.get("id") == tid: page_ws = t["webSocketDebuggerUrl"]; break

        async with websockets.connect(page_ws, close_timeout=5) as ws:
            await asyncio.sleep(5)
            try: 
                while True: await asyncio.wait_for(ws.recv(), timeout=0.3)
            except: pass

            # Check serveo page
            js = "return document.title + ' | hasContinue: ' + (!!document.querySelector('button,a').textContent.includes('Continue'))"
            await ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":js}}))
            for _ in range(20):
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if msg.get("id") == 1:
                        print(f"   Serveo: {msg['result']['result']['value']}")
                        break
                except: break

            # Click Continue if present
            await ws.send(json.dumps({"id":2,"method":"Runtime.evaluate","params":{
                "expression": """(function(){
                    var btns=document.querySelectorAll('button,a');
                    for(var i=0;i<btns.length;i++){
                        if(btns[i].textContent.match(/Continue|Accept/i)){
                            btns[i].click(); return 'clicked';
                        }
                    }
                    return 'no button found';
                })()"""
            }}))
            await asyncio.sleep(2)

            # Navigate to game
            print("2. Opening game page...")
            await ws.send(json.dumps({"id":3,"method":"Page.navigate","params":{"url":GAME}}))
            await asyncio.sleep(6)
            try:
                while True: await asyncio.wait_for(ws.recv(), timeout=0.3)
            except: pass

            # Check page
            await ws.send(json.dumps({"id":4,"method":"Runtime.evaluate","params":{
                "expression": """(function(){
                    return JSON.stringify({
                        title: document.title,
                        lobby: document.getElementById('lobby').style.display,
                        game: document.getElementById('game').style.display
                    });
                })()"""
            }}))
            for _ in range(20):
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if msg.get("id") == 4:
                        val = msg["result"]["result"]["value"]
                        print(f"   Page state: {val}")
                        break
                except: break

            # Fill name
            print("3. Filling name + clicking Create Room...")
            await ws.send(json.dumps({"id":5,"method":"Runtime.evaluate","params":{
                "expression": """document.getElementById('nameInput').value='Tester'; 'ok'"""
            }}))
            await asyncio.sleep(0.5)

            # Call createRoom
            await ws.send(json.dumps({"id":6,"method":"Runtime.evaluate","params":{
                "expression": """
                (function(){
                    var alerts = [];
                    var oldAlert = window.alert;
                    window.alert = function(m){ alerts.push(m); oldAlert(m); };
                    try { createRoom(); return 'called, alerts: '+JSON.stringify(alerts); }
                    catch(e){ return 'error: '+e.message; }
                })()
                """
            }}))
            await asyncio.sleep(3)
            for _ in range(20):
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if msg.get("id") == 6:
                        print(f"   createRoom: {msg['result']['result']['value']}")
                        break
                except: break

            # Final state
            await ws.send(json.dumps({"id":7,"method":"Runtime.evaluate","params":{
                "expression": """(function(){
                    return JSON.stringify({
                        lobby: document.getElementById('lobby').style.display,
                        game: document.getElementById('game').style.display,
                        status: document.getElementById('status').textContent,
                        nameB: document.getElementById('nameB').textContent,
                    });
                })()"""
            }}))
            for _ in range(20):
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if msg.get("id") == 7:
                        val = msg["result"]["result"]["value"]
                        print(f"\nFINAL STATE: {val}")
                        break
                except: break

asyncio.run(main())
