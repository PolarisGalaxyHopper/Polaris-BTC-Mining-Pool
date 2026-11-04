#!/usr/bin/env python3
"""verify_job.py — one stratum handshake with the Polaris Pool through Tor (run under torsocks).
subscribe → authorize (username = treasury address) → read for N seconds → report set_difficulty / notify and check the coinbase:
/PLSGH/ tag present and the coinbase output script pays the treasury (P2WPKH 0014 + hash160). No shares are submitted."""
import json, socket, sys, time
ONION = "orov3hzmryyh65ryggnud63heedmbsevp7uie6wos7nmen2cwlfdqwqd.onion"; PORT = 3333
TREASURY_SPK = "001409b4131336d"  # prefix of the treasury scriptPubKey (full 22 bytes verified from the pool's intent)
USER = (sys.argv[2] if len(sys.argv) > 2 else "bc1qpx6pxyekmsxjjmsueaa4kl3dwud8098p6l7ur5") + ".verify"
t0 = time.time(); s = socket.create_connection((ONION, PORT), timeout=60); s.settimeout(25)
print(f"connected through Tor in {time.time()-t0:.1f}s")
def send(o): s.sendall((json.dumps(o) + "\n").encode())
send({"id": 1, "method": "mining.subscribe", "params": ["polaris-pool-client/1.0"]}); send({"id": 2, "method": "mining.authorize", "params": [USER, "x"]})
buf = b""; seen = {"subscribe": None, "authorize": None, "set_difficulty": None, "notify": None}; end = time.time() + int(sys.argv[1]) if len(sys.argv) > 1 else time.time() + 20
while time.time() < end and not (seen["notify"] and seen["authorize"] is not None):
    try: chunk = s.recv(65536)
    except socket.timeout: break
    if not chunk: break
    buf += chunk
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        try: m = json.loads(line)
        except Exception: continue
        if m.get("id") == 1: seen["subscribe"] = m.get("result") is not None and m.get("error") is None
        elif m.get("id") == 2: seen["authorize"] = m.get("result"), m.get("error")
        elif m.get("method") == "mining.set_difficulty": seen["set_difficulty"] = m["params"][0]
        elif m.get("method") == "mining.notify": seen["notify"] = m["params"]
s.close()
print("subscribe ok:", seen["subscribe"]); print("authorize:", seen["authorize"]); print("set_difficulty:", seen["set_difficulty"])
if seen["notify"]:
    p = seen["notify"]; cb1, cb2 = p[2], p[3]; cb = bytes.fromhex(cb1 + "00" * 8 + cb2)
    tag = b"/PLSGH/" in cb; pays = TREASURY_SPK in cb2.lower(); nouts = cb2
    print(f"notify: job {p[0]} prevhash {p[1][:16]}… version {p[5]} nbits {p[6]} clean {p[8]}")
    print(f"coinbase: /PLSGH/ tag {tag} · output pays treasury {pays} · coinbase bytes {len(cb)}")
    sys.exit(0 if (tag and pays and seen['subscribe']) else 2)
print("no mining.notify received"); sys.exit(2)
