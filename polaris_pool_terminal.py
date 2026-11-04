#!/usr/bin/env python3
"""
POLARIS POOL TERMINAL — the pool console for the Polaris Pool — a sovereign Bitcoin pool.  2026-11-03.

Two ways to run it, one screen:
  on the pool operator:         python3 pool_terminal.py            reads the pool directly (pool_data.py, read-only)
  anywhere (miners):         polaris-pool  /  python3 polaris_pool_terminal.py --door    reads the pool through its public Tor door
Needs a local Tor SOCKS port (tor service 9050, or Tor Browser 9150) — the terminal speaks SOCKS5 itself, no torsocks required.

SETUP tab: type your payout address, rig name and proxy address; save; start the LAN proxy (Linux, root); copy the ASIC settings.
Anything that speaks stratum can mine here — ASIC, GPU or CPU — paid in exact proportion to the difficulty it submits.
READ-ONLY towards the pool: writes only its own config (~/.polaris-pool/config.json) and, if you ask, the local proxy service.
Tabs are CLICKABLE (mouse) and keyed:  1 Setup  2 Dashboard  3 Workers  4 Shares  5 Blocks & payouts  6 Entrance  7 Help
  t  test the stratum handshake    r refresh    q quit     (in Setup: ↑↓ pick a field · Enter edit · s save · p proxy on/off · a ASIC settings)
"""
import curses, json, os, socket, struct, subprocess, sys, threading, time
from collections import deque
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
DOOR = "http://n4deym4zszn2pxwxydrr4phtw2zownckvbhllgmhjesiy756ykgdwjad.onion"
ONION = "orov3hzmryyh65ryggnud63heedmbsevp7uie6wos7nmen2cwlfdqwqd.onion"
ARGS = sys.argv[1:]; DOOR_MODE = "--door" in ARGS or not os.path.exists(os.path.join(HERE, "pool_data.py"))
CONF_DIR = os.path.expanduser("~/.polaris-pool"); CONF_PATH = os.path.join(CONF_DIR, "config.json")
FIELDS = [("payout_address", "Your Bitcoin payout address (bc1…)  = your worker name on the pool"), ("rig_name", "Rig name (letters/digits; shown as address.rigname)"),
          ("proxy_listen", "LAN address of the proxy box your miners point at (blank = this machine)"), ("tor_socks", "Tor SOCKS port on this machine (9050 tor service · 9150 Tor Browser)"),
          ("hardware", "What you point at the pool: asic / gpu / cpu (information only)")]
def load_conf():
    d = {"payout_address": "", "rig_name": "rig1", "proxy_listen": "", "tor_socks": "9050", "hardware": "asic"}
    try: d.update(json.load(open(CONF_PATH)))
    except Exception: pass
    if "--me" in ARGS and ARGS.index("--me") + 1 < len(ARGS): d["payout_address"] = ARGS[ARGS.index("--me") + 1].strip()
    elif os.environ.get("POLARIS_ME"): d["payout_address"] = os.environ["POLARIS_ME"].strip()
    return d
def save_conf(d):
    os.makedirs(CONF_DIR, exist_ok=True); json.dump(d, open(CONF_PATH, "w"), indent=1); os.chmod(CONF_PATH, 0o600)
CONF = load_conf(); ME = CONF.get("payout_address", "")
LABEL = "operator console" if not DOOR_MODE else "via the Tor door"
VIEWS = ["SETUP", "DASHBOARD", "WORKERS", "SHARES", "BLOCKS & PAYOUTS", "ENTRANCE", "HELP"]
def socks_connect(host, port, timeout=60):
    """SOCKS5 CONNECT through the local Tor port (domain-name form, so .onion resolves inside Tor)."""
    try: s = socket.create_connection(("localhost", int(CONF.get("tor_socks") or 9050)), timeout=timeout)
    except OSError: raise OSError("Tor is not listening on port %s — start the tor service (9050) or Tor Browser (9150) and set the port in Setup" % (CONF.get("tor_socks") or 9050))
    s.settimeout(timeout)
    s.sendall(b"\x05\x01\x00"); r = s.recv(2)
    if r != b"\x05\x00": raise OSError("Tor SOCKS refused (is tor running on port %s?)" % CONF.get("tor_socks"))
    h = host.encode(); s.sendall(b"\x05\x01\x00\x03" + bytes([len(h)]) + h + struct.pack(">H", port)); r = s.recv(10)
    if len(r) < 2 or r[1] != 0: raise OSError("Tor could not reach %s (code %s)" % (host, r[1] if len(r) > 1 else "?"))
    return s
def door_get(path):
    s = socks_connect(DOOR.split("//")[1], 80); s.sendall(("GET %s HTTP/1.0\r\nHost: %s\r\n\r\n" % (path, DOOR.split("//")[1])).encode()); buf = b""
    while True:
        c = s.recv(65536)
        if not c: break
        buf += c
    s.close(); return json.loads(buf.split(b"\r\n\r\n", 1)[1])
def load():
    if DOOR_MODE: return door_get("/pool/live")
    import pool_data; return pool_data.snapshot()
def proxy_unit_state():
    try: return subprocess.run(["systemctl", "is-active", "polaris-pool-proxy"], capture_output=True, text=True, timeout=5).stdout.strip() or "absent"
    except Exception: return "n/a"
def proxy_toggle():
    """start or stop the local LAN proxy service (Linux; needs root). Writes the unit on first use from the saved config."""
    if os.geteuid() != 0: return "run the terminal as root (sudo polaris-pool) to control the proxy"
    st = proxy_unit_state()
    if st == "active": subprocess.run(["systemctl", "stop", "polaris-pool-proxy"]); return "proxy stopped"
    listen = CONF.get("proxy_listen") or (subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split() or [""])[0]
    bind = (",bind=" + listen) if listen else ""
    if not os.path.exists("/usr/bin/socat"): return "socat is not installed (apt install tor socat)"
    unit = ("[Unit]\nDescription=Polaris Pool proxy — LAN :3333 → Tor → pool onion\nAfter=network-online.target tor.service\nWants=network-online.target tor.service\n[Service]\n"
            "ExecStart=/usr/bin/socat -T 600 TCP-LISTEN:3333,fork,reuseaddr%s SOCKS4A:localhost:%s:3333,socksport=%s\nRestart=always\nRestartSec=3\nDynamicUser=yes\nNoNewPrivileges=yes\n[Install]\nWantedBy=multi-user.target\n") % (bind, ONION, CONF.get("tor_socks") or 9050)
    open("/etc/systemd/system/polaris-pool-proxy.service", "w").write(unit); subprocess.run(["systemctl", "daemon-reload"]); subprocess.run(["systemctl", "enable", "--now", "polaris-pool-proxy"], capture_output=True)
    return "proxy %s on %s:3333" % (proxy_unit_state(), listen or "all interfaces")
def fmt_hs(h):
    h = float(h or 0)
    for u in ("H/s", "kH/s", "MH/s", "GH/s", "TH/s", "PH/s", "EH/s"):
        if h < 1000: return f"{h:,.1f} {u}"
        h /= 1000
    return f"{h:,.1f} ZH/s"
def ago(ts):
    if not ts: return "never"
    s = int(time.time() - float(ts)); return f"{s}s ago" if s < 120 else (f"{s // 60}m ago" if s < 7200 else f"{s // 3600}h ago")
def handshake():
    """one stratum subscribe through Tor (or loopback on the pool): proves the job carries /PLSGH/ and pays the treasury."""
    try:
        if DOOR_MODE: s = socks_connect(ONION, 3333)
        else: s = socket.create_connection(("localhost", 3333), timeout=10)
        user = (ME or "bc1qpx6pxyekmsxjjmsueaa4kl3dwud8098p6l7ur5") + ".terminal"
        s.settimeout(20); s.sendall(('{"id":1,"method":"mining.subscribe","params":["polaris-pool-terminal/1.0"]}\n{"id":2,"method":"mining.authorize","params":["%s","x"]}\n' % user).encode())
        buf = b""; t0 = time.time()
        while time.time() - t0 < 20 and b"mining.notify" not in buf:
            c = s.recv(65536)
            if not c: break
            buf += c
        s.close()
        for line in buf.split(b"\n"):
            try: m = json.loads(line)
            except Exception: continue
            if m.get("method") == "mining.notify":
                p = m["params"]; cb = bytes.fromhex(p[2] + "00" * 8 + p[3])
                return {"ok": True, "job": p[0], "tag": b"/PLSGH/" in cb, "pays_treasury": "001409b4131336d" in p[3].lower(), "diff_note": "set_difficulty seen" if b"set_difficulty" in buf else ""}
        return {"ok": False, "error": "no job received (pool switched off?)"}
    except Exception as e: return {"ok": False, "error": str(e)[:80]}
class State:
    def __init__(self): self.d = {}; self.err = ""; self.msg = "loading…"; self.busy = False; self.hist = deque(maxlen=600); self.test = None
    def refresh(self):
        self.busy = True
        try:
            d = load(); self.d = d; self.err = ""; lv = d.get("live", {})
            self.hist.append((d.get("ts", int(time.time())), float(lv.get("hashrate", {}).get("hashrate1m", 0) or 0), lv.get("accepted", 0), lv.get("rejected", 0)))
            self.msg = f"updated {time.strftime('%H:%M:%S')}"
        except Exception as e: self.err = str(e)[:100]; self.msg = "load error: " + self.err
        self.busy = False
class UI:
    def __init__(self, scr):
        self.s = scr; self.st = State(); self.view = 1 if ME else 0; self.scroll = 0; self.tab_spans = []; self.field = 0; self.show_asic = False
        curses.curs_set(0); curses.start_color(); curses.use_default_colors()
        for i, (fg, bg) in enumerate([(curses.COLOR_BLACK, curses.COLOR_GREEN), (curses.COLOR_GREEN, -1), (curses.COLOR_RED, -1), (curses.COLOR_YELLOW, -1), (curses.COLOR_CYAN, -1), (curses.COLOR_WHITE, -1), (curses.COLOR_MAGENTA, -1)], 1):
            curses.init_pair(i, fg, bg)
        self.BAR, self.G, self.R, self.Y, self.C, self.W, self.M = (curses.color_pair(i) for i in range(1, 8))
        try: curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION); curses.mouseinterval(0)
        except Exception: pass
        scr.timeout(1000)
    def put(self, y, x, text, attr=0):
        h, w = self.s.getmaxyx()
        if 0 <= y < h and x < w:
            try: self.s.addnstr(y, x, str(text), max(0, w - x - 1), attr)
            except curses.error: pass
    def header(self, d):
        h, w = self.s.getmaxyx(); p = d.get("pool", {}); lv = d.get("live", {}); ch = d.get("chain", {})
        self.put(0, 0, " " * w, self.BAR); self.put(0, 1, f" POLARIS POOL TERMINAL — {LABEL} ", self.BAR | curses.A_BOLD)
        on = p.get("unit") == "active"
        self.put(0, 40, f"POOL {'ON ' if on else 'OFF'}  {fmt_hs(lv.get('hashrate', {}).get('hashrate1m'))}  workers {lv.get('workers', 0)}  block {ch.get('height') or '?'}", self.BAR)
        self.put(0, max(30, w - 10), time.strftime("%H:%M:%S"), self.BAR)
        x, spans = 1, []
        for i, v in enumerate(VIEWS):
            label = f" [{i + 1}] {v} "; self.put(1, x, label, (self.BAR | curses.A_BOLD) if i == self.view else (self.C | curses.A_UNDERLINE)); spans.append((x, x + len(label) - 1, i)); x += len(label) + 1
        self.tab_spans = spans; self.put(1, x + 1, "← click a tab", self.W | curses.A_DIM); self.put(2, 0, "─" * w, self.G)
    def footer(self):
        h, w = self.s.getmaxyx(); self.put(h - 2, 0, "─" * w, self.G)
        self.put(h - 1, 1, ("⏳ " if self.st.busy else "") + self.st.msg, self.Y if self.st.busy else self.W)
        keys = " click tabs · wheel scroll · 1 setup  t test handshake  r refresh  q quit "; self.put(h - 1, max(1, w - len(keys) - 1), keys, self.BAR)
    def lines_setup(self, d):
        L = [("SET UP YOUR MINER  —  ↑↓ pick a field · Enter type a new value · s save · p start/stop the LAN proxy · a show the ASIC settings · t test", self.C | curses.A_BOLD), ("", 0)]
        for i, (k, label) in enumerate(FIELDS):
            v = CONF.get(k, ""); mark = "▶" if i == self.field else " "
            L.append((f" {mark} {label}", (self.Y if i == self.field else self.W) | curses.A_BOLD)); L.append((f"      {v if v else '(empty)'}", self.G if v else self.R)); L.append(("", 0))
        addr = CONF.get("payout_address", ""); rig = CONF.get("rig_name") or "rig1"; listen = CONF.get("proxy_listen") or "<this machine's LAN address>"
        ok = addr.startswith(("bc1q", "bc1p", "1", "3")) and len(addr) >= 26
        L.append((f"  config file  {CONF_PATH}   ·   address {'looks valid ✔' if ok else 'MISSING or invalid — the pool rejects a worker name that is not a Bitcoin address'}", self.G if ok else self.R))
        L.append((f"  local proxy  {proxy_unit_state()}   (the proxy is the small box between your miners and Tor; start it here as root, or run install.sh)", self.W))
        if self.show_asic or ok:
            L += [("", 0), ("TYPE THIS INTO EACH MINER  (ASIC web page → Pool settings · GPU/CPU software → pool URL/user/pass)", self.C | curses.A_BOLD),
                  (f"  Pool URL   stratum+tcp://{listen}:3333        (through your proxy; or directly  stratum+tcp://{ONION}:3333  if the software can use Tor/SOCKS)", self.G),
                  (f"  Worker     {addr or '<your payout address>'}.{rig}", self.G), ("  Password   x", self.G),
                  ("  Works with anything that speaks stratum: ASIC (the real work), GPU (≈10 000× weaker than one S9), CPU (≈3 000 000× weaker). Paid strictly by difficulty submitted.", self.W)]
        return L
    def edit_field(self):
        k, label = FIELDS[self.field]; h, w = self.s.getmaxyx(); curses.echo(); curses.curs_set(1)
        self.put(h - 1, 0, " " * (w - 1)); self.put(h - 1, 1, f"{label}: ", self.Y | curses.A_BOLD); self.s.refresh()
        try: v = self.s.getstr(h - 1, len(label) + 3, 120).decode(errors="ignore").strip()
        except Exception: v = None
        curses.noecho(); curses.curs_set(0)
        if v is not None and v != "":
            CONF[k] = v
            if k == "payout_address":
                global ME; ME = v
            self.st.msg = f"{k} set (press s to save)"
    def lines_dashboard(self, d):
        p, lv, ch, po = d.get("pool", {}), d.get("live", {}), d.get("chain", {}), d.get("payouts", {}); hs = lv.get("hashrate", {}); L = []
        on = p.get("unit") == "active"
        L.append((f"THE POOL — {p.get('name', '')}", self.C | curses.A_BOLD))
        L.append((f"  Stratum           {'ACCEPTING WORK ✔' if on else 'SWITCHED OFF'}      Tor {p.get('tor', '?')}      entrance  stratum+tcp://{p.get('onion', ONION)}:{p.get('port', 3333)}", self.G if on else self.Y))
        L.append((f"  Coinbase          pays {p.get('coinbase_address')}   tag {p.get('coinbase_tag')}   fee {int(p.get('fee_bps', 150)) / 100:.2f} %   difficulty start {p.get('startdiff')} / min {p.get('mindiff')}", self.W))
        L.append(("", 0)); L.append(("LIVE", self.C | curses.A_BOLD))
        L.append((f"  Hashrate          1m {fmt_hs(hs.get('hashrate1m'))}   5m {fmt_hs(hs.get('hashrate5m'))}   1h {fmt_hs(hs.get('hashrate1hr'))}   1d {fmt_hs(hs.get('hashrate1d'))}   7d {fmt_hs(hs.get('hashrate7d'))}", self.G))
        L.append((f"  Users / workers   {lv.get('users', 0)} / {lv.get('workers', 0)}   idle {lv.get('idle', 0)}   disconnected {lv.get('disconnected', 0)}      shares accepted {lv.get('accepted', 0):,}  rejected {lv.get('rejected', 0):,}   best share {float(lv.get('bestshare') or 0):,.0f}", self.W))
        L.append((f"  Shares per second 1m {lv.get('sps', {}).get('SPS1m', 0)}   5m {lv.get('sps', {}).get('SPS5m', 0)}   1h {lv.get('sps', {}).get('SPS1h', 0)}      pool status updated {ago(lv.get('lastupdate'))}   pool up {int(lv.get('runtime_s') or 0) // 60} min", self.W))
        L.append(("", 0)); L.append(("BITCOIN (the pool builds every job from this chain tip)", self.C | curses.A_BOLD))
        if ch.get("height"):
            nh = float(ch.get("networkhashps") or 0); my = float(hs.get("hashrate1h") or hs.get("hashrate1hr") or 0)
            L.append((f"  Height {ch['height']:,}   {'SYNCING' if ch.get('ibd') else 'AT TIP ✔'}   difficulty {float(ch.get('difficulty') or 0):,.0f}   network {fmt_hs(nh)}   mempool {ch.get('mempool_tx') or 0:,} tx", self.G))
            if nh and my: L.append((f"  This pool's share of the network: {my / nh * 100:.9f} %  → expected time to a block at this rate ≈ {nh / my * 600 / 86400:,.0f} days", self.W))
        else: L.append(("  chain view unavailable", self.R))
        L.append(("", 0)); L.append(("PAYOUTS", self.C | curses.A_BOLD)); r = po.get("rule", {})
        L.append((f"  PPLNS window {r.get('window_multiplier', 2.0)} × network difficulty · fee {int(r.get('fee_bps', 150)) / 100:.2f} % to the treasury · paid after {r.get('coinbase_maturity', 100)} confirmations · minimum {r.get('min_payout_sat', 10000):,} sat (smaller amounts carried)", self.W))
        L.append((f"  Balances carried  {len(po.get('balances', {}))} addresses   ·   blocks found {len(po.get('rounds', []))}   ·   payout engine {'LOCKED (operator)' if po.get('lock') else 'armed'}", self.W))
        if ME: L.append(("", 0)); L.append((f"YOU ({ME[:14]}…): " + self.me_line(d), self.M | curses.A_BOLD))
        return L
    def me_line(self, d):
        u = d.get("users", {}).get(ME)
        if not u: return "no shares seen from this address yet"
        return f"{fmt_hs(u.get('hashrate1m'))} now · {fmt_hs(u.get('hashrate1d'))} 1d · shares {int(float(u.get('shares') or 0)):,} · best {float(u.get('bestshare') or 0):,.0f} · last share {ago(u.get('lastshare'))} · balance {int(d.get('payouts', {}).get('balances', {}).get(ME, 0) or 0):,} sat"
    def lines_workers(self, d):
        users = d.get("users", {}); L = [("WORKERS — one row per payout address, then each rig under it", self.C | curses.A_BOLD),
                                          (f"{'ADDRESS / rig':44} {'1m':>12} {'5m':>12} {'1h':>12} {'1d':>12} {'SHARES':>10} {'BEST':>12} {'LAST SHARE':>12}", self.C | curses.A_BOLD)]
        order = sorted(users, key=lambda a: (a != ME, -float(users[a].get("hashrate1m") or 0)))
        if not order: L.append(("  no worker has connected yet", self.Y))
        for a in order:
            u = users[a]; mine = a == ME
            L.append((f"{a[:44]:44} {fmt_hs(u.get('hashrate1m')):>12} {fmt_hs(u.get('hashrate5m')):>12} {fmt_hs(u.get('hashrate1hr')):>12} {fmt_hs(u.get('hashrate1d')):>12} {int(float(u.get('shares') or 0)):>10,} {float(u.get('bestshare') or 0):>12,.0f} {ago(u.get('lastshare')):>12}", (self.M if mine else self.G) | curses.A_BOLD))
            for w in u.get("worker", []):
                L.append((f"   └ {str(w.get('workername', '')).split('.')[-1][:38]:38} {fmt_hs(w.get('hashrate1m')):>12} {fmt_hs(w.get('hashrate5m')):>12} {fmt_hs(w.get('hashrate1hr')):>12} {fmt_hs(w.get('hashrate1d')):>12} {int(float(w.get('shares') or 0)):>10,} {float(w.get('bestshare') or 0):>12,.0f} {ago(w.get('lastshare')):>12}", self.W))
        return L
    def lines_shares(self, d):
        L = [("SHARES — pool-wide, sampled every refresh (hashrate 1m · accepted · rejected)", self.C | curses.A_BOLD), (f"{'TIME':>8}  {'HASHRATE 1m':>14}  {'ACCEPTED':>10}  {'REJECTED':>9}  {'Δ accepted':>10}", self.C | curses.A_BOLD)]
        prev = None
        for ts, h, a, r in list(self.st.hist)[-400:]:
            L.append((f"{time.strftime('%H:%M:%S', time.localtime(ts)):>8}  {fmt_hs(h):>14}  {a:>10,}  {r:>9,}  {('+' + str(a - prev)) if prev is not None and a - prev else '':>10}", self.G if (prev is not None and a > prev) else self.W)); prev = a
        if len(self.st.hist) < 2: L.append(("  collecting… (one row per refresh; leave this open to watch shares arrive)", self.Y))
        return L
    def lines_blocks(self, d):
        po = d.get("payouts", {}); L = [("BLOCKS FOUND BY THIS POOL (from the pool's own chain view)", self.C | curses.A_BOLD)]
        if not po.get("rounds"): L.append(("  none yet — a block appears here the moment one of our templates is stamped and confirmed", self.Y))
        for r in po.get("rounds", [])[-30:]:
            L.append((f"  height {r.get('height', '?')}  reward {int(r.get('reward_sat', 0) or 0):,} sat  fee {int(r.get('fee_sat', 0) or 0):,}  workers paid {len(r.get('payouts', {}) or {})}  txid {str(r.get('payout_txid') or r.get('txid') or '')[:20]}…  {r.get('status', '')}", self.G))
        L.append(("", 0)); L.append(("BALANCES CARRIED (under the minimum payout)", self.C | curses.A_BOLD))
        bal = po.get("balances", {})
        if not bal: L.append(("  none", self.W))
        for a, v in sorted(bal.items(), key=lambda kv: -int(kv[1] or 0))[:40]: L.append((f"  {a:44} {int(v or 0):>12,} sat", self.M if a == ME else self.W))
        L.append(("", 0)); L.append(("PAYOUT LEDGER (hash-chained, newest last)", self.C | curses.A_BOLD))
        for row in po.get("ledger_tail", [])[-25:]: L.append((f"  {time.strftime('%Y-%m-%d %H:%M', time.localtime(int(row.get('ts', 0) or 0)))}  {row.get('event', ''):18} {json.dumps(row.get('data', {}), default=str)[:110]}", self.W))
        if not po.get("ledger_tail"): L.append(("  empty — nothing has been owed or paid yet", self.W))
        return L
    def lines_entrance(self, d):
        p = d.get("pool", {}); L = [("HOW TO REACH THIS POOL", self.C | curses.A_BOLD),
            (f"  Stratum (Tor)      stratum+tcp://{p.get('onion', ONION)}:{p.get('port', 3333)}", self.G),
            ("  Worker name        your own Bitcoin payout address, optionally .rigname        password: anything", self.W),
            ("  ASICs cannot speak Tor: run one proxy box on your LAN (tor + socat) and point the miners at it — full guide on the door at /pool/guide", self.W),
            ("  Anyone may host a public entrance for this pool: the script is on the door at /pool/relay (it learns nothing about the pool's location)", self.W),
            ("", 0), ("HANDSHAKE TEST  (press  t  — one mining.subscribe, no share is sent)", self.C | curses.A_BOLD)]
        t = self.st.test
        if t is None: L.append(("  not run yet", self.W))
        elif t.get("ok"): L.append((f"  job {t.get('job')}  ·  coinbase carries /PLSGH/: {t.get('tag')}  ·  coinbase pays the treasury: {t.get('pays_treasury')}  ·  {t.get('diff_note', '')}", self.G if (t.get('tag') and t.get('pays_treasury')) else self.R))
        else: L.append((f"  failed: {t.get('error')}", self.R))
        L.append(("", 0)); L.append(("WHAT YOU CAN VERIFY YOURSELF", self.C | curses.A_BOLD))
        L += [("  · every job is built from the live chain tip shown on the dashboard", self.W), ("  · every coinbase carries /PLSGH/ and pays the treasury address shown on the dashboard", self.W),
              ("  · found blocks and payout transactions are public on the Bitcoin chain", self.W), ("  · through Tor the pool never sees your network address, and you never see its", self.W)]
        return L
    def lines_help(self, d):
        return [("WHAT THE NUMBERS MEAN", self.C | curses.A_BOLD),
                ("  Hashrate 1m/5m/1h/1d  work rate estimated from accepted shares over that window (a single ASIC shows noise at 1m; trust 1h)", self.W),
                ("  Shares                difficulty-weighted units of work the pool accepted; PPLNS pays the last shares worth 2 × network difficulty when a block is found", self.W),
                ("  Best share            the hardest share a worker ever produced; a share above the network difficulty IS a block", self.W),
                ("  Expected time to a block  network hashrate ÷ pool hashrate × 10 minutes — honest, and large for a small pool", self.W),
                ("  Balances carried      amounts under 10 000 sat held for the next block; never custody beyond that", self.W),
                ("", 0), ("WHAT CAN CONNECT", self.C | curses.A_BOLD),
                ("  Anything that speaks stratum: ASIC, GPU or CPU. The pool credits shares by difficulty, so each is paid in exact proportion to the work it did.", self.W),
                ("  One S9-class ASIC ≈ 9 TH/s; a strong GPU ≈ 1 GH/s (≈10 000× less); a CPU core ≈ 1–3 MH/s (millions of times less). Minimum share difficulty is 1.", self.W),
                ("", 0), ("KEYS", self.C | curses.A_BOLD), ("  1–7 or click: tabs   ·   wheel / ↑↓ / PgUp PgDn: scroll   ·   t: handshake test   ·   r: refresh now   ·   q: quit   ·   Setup: Enter edit · s save · p proxy · a ASIC settings", self.W),
                ("", 0), (f"  mode: {'public door over Tor' if DOOR_MODE else 'the pool local files (read-only)'}   ·   refresh every 30 s   ·   pin your address with --me <address> or POLARIS_ME", self.W | curses.A_DIM)]
    def draw(self):
        self.s.erase(); d = self.st.d; self.header(d)
        try: L = [self.lines_setup, self.lines_dashboard, self.lines_workers, self.lines_shares, self.lines_blocks, self.lines_entrance, self.lines_help][self.view](d)
        except Exception as e: L = [(f"render error: {e}", self.R)]
        if self.st.err and not d: L = [(f"cannot load the pool view: {self.st.err}", self.R)]
        h, w = self.s.getmaxyx(); room = h - 5; self.scroll = max(0, min(self.scroll, max(0, len(L) - room)))
        for i, (t, a) in enumerate(L[self.scroll:self.scroll + room]): self.put(3 + i, 1, t, a)
        self.footer(); self.s.refresh()
    def run(self):
        threading.Thread(target=self.st.refresh, daemon=True).start(); last = time.time()
        while True:
            self.draw(); k = self.s.getch()
            if time.time() - last > 30 and not self.st.busy: threading.Thread(target=self.st.refresh, daemon=True).start(); last = time.time()
            if k == -1: continue
            if k in (ord("q"), 27): return
            if k == ord("r"): threading.Thread(target=self.st.refresh, daemon=True).start(); last = time.time()
            if k == ord("t"):
                self.st.msg = "handshake…"; threading.Thread(target=lambda: setattr(self.st, "test", handshake()), daemon=True).start(); self.view = 5
            if ord("1") <= k <= ord("7"): self.view = k - ord("1"); self.scroll = 0
            if self.view == 0:
                if k == curses.KEY_DOWN: self.field = min(len(FIELDS) - 1, self.field + 1); continue
                if k == curses.KEY_UP: self.field = max(0, self.field - 1); continue
                if k in (10, 13, curses.KEY_ENTER): self.edit_field(); continue
                if k == ord("s"): save_conf(CONF); self.st.msg = "saved " + CONF_PATH; continue
                if k == ord("p"): self.st.msg = proxy_toggle(); continue
                if k == ord("a"): self.show_asic = not self.show_asic; continue
            if k in (curses.KEY_DOWN, ord("j")): self.scroll += 1
            if k in (curses.KEY_UP, ord("k")): self.scroll -= 1
            if k == curses.KEY_NPAGE: self.scroll += 20
            if k == curses.KEY_PPAGE: self.scroll -= 20
            if k == curses.KEY_MOUSE:
                try: _, mx, my, _, b = curses.getmouse()
                except Exception: continue
                if b & curses.BUTTON4_PRESSED: self.scroll -= 3
                elif b & getattr(curses, "BUTTON5_PRESSED", 1 << 21): self.scroll += 3
                elif my == 1:
                    for x0, x1, i in self.tab_spans:
                        if x0 <= mx <= x1: self.view = i; self.scroll = 0
def main():
    try: curses.wrapper(lambda scr: UI(scr).run())
    except KeyboardInterrupt: pass
if __name__ == "__main__":
    main()
