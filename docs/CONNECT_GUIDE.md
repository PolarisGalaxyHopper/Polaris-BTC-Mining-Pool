# Polaris Pool — Connect Guide

Published 2026-11-03. This page is served by the Polaris Pool Tor door at `/pool/guide`; the machine-readable summary is at `/pool`. One file, updated in place.

## What this pool is

Polaris Pool is a sovereign Bitcoin mining pool. It authors every block template from its own fully-validating Bitcoin node; connected hardware stamps it. Every block found here carries the `/PLSGH/` tag in its coinbase.

| | |
|---|---|
| Stratum endpoint | `stratum+tcp://orov3hzmryyh65ryggnud63heedmbsevp7uie6wos7nmen2cwlfdqwqd.onion:3333` (Tor) |
| Pool fee | 1.5 % of each block reward, kept by the pool treasury |
| Payout rule | PPLNS — the last shares worth 2 × network difficulty at the moment a block is found share the remaining 98.5 %, in proportion to difficulty submitted |
| When you are paid | after the found block's coinbase matures (100 confirmations), in one on-chain transaction to every worker's address; amounts under 10,000 sat are carried to the next block |
| Worker name | your own Bitcoin payout address, optionally followed by `.rigname` — for example `bc1q…yourpayout.rig1` |
| Password | anything (`x` is fine) |
| Difficulty | starts at 42, minimum 1, adjusts to your hardware |
| Status | see the `status` field at `/pool` — the stratum accepts work only when the pool is switched on |

Your payout address is your identity on this pool. Shares are credited to it, and the payout transaction pays it directly. Get it right: the pool rejects a worker name that is not a valid Bitcoin address.

## Why Tor, and what it means for you

The pool is reachable only through Tor today. Your hardware never learns the pool's network location and the pool never learns yours. The onion address above is the pool's identity: there is no certificate to check, the address is the key. A clearnet entrance with a DNS name, fronted by a relay so that no home network is ever exposed, is planned; this page will carry it when it is live.

## What can connect

Anything that speaks the stratum protocol: an ASIC, a GPU miner, a CPU miner. The pool credits every share by the difficulty it carries, so each machine is paid in exact proportion to the work it did. What differs is the amount of work:

| hardware | typical rate | time to one difficulty-1 share | note |
|---|---|---|---|
| ASIC, S9 class | ≈ 9 TH/s | a fraction of a second | the real workers; the pool raises their difficulty automatically |
| ASIC, current generation | 100–200 TH/s | instant | same |
| GPU | ≈ 1 GH/s | ≈ 4 seconds | about ten thousand times less than one S9, for more electricity |
| CPU | 1–3 MH/s per core | ≈ 20–40 minutes | proves the pipeline, earns nothing meaningful |

Minimum share difficulty is 1. The terminal shows every connected machine the pool's share of the network and the honest expected time to a block, so decide with that number in front of you.

## How to connect

ASICs cannot speak Tor, so you run one small proxy on your own network and point your machines at it. Any Linux box or Raspberry Pi will do.

1. **Install Tor and socat** on the proxy box.
   ```
   sudo apt install tor socat
   ```
   Tor starts a SOCKS listener on `localhost:9050` by itself.

2. **Start the forwarder.** Replace `PROXY_LAN_ADDRESS` with the proxy box's own address on your LAN.
   ```
   socat TCP-LISTEN:3333,fork,reuseaddr,bind=PROXY_LAN_ADDRESS \
         SOCKS4A:localhost:orov3hzmryyh65ryggnud63heedmbsevp7uie6wos7nmen2cwlfdqwqd.onion:3333,socksport=9050
   ```
   To keep it running across reboots, put that line in a systemd service (`Restart=always`, `After=tor.service`).

3. **Point your miners at the proxy.** In each ASIC's pool settings:
   - URL: `stratum+tcp://PROXY_LAN_ADDRESS:3333`
   - Worker: `bc1q…yourpayout.rig1`
   - Password: `x`

4. **Check the handshake** from the proxy box before you move hardware:
   ```
   printf '{"id":1,"method":"mining.subscribe","params":["test/1.0"]}\n' | torsocks nc orov3hzmryyh65ryggnud63heedmbsevp7uie6wos7nmen2cwlfdqwqd.onion 3333
   ```
   You should see a `result` for id 1, then `mining.set_difficulty` and a `mining.notify` job. If the pool is switched off you get no answer; check `/pool` for the status.

Software miners that take a SOCKS proxy (for example cpuminer with `--proxy socks4a://localhost:9050`) can connect to the onion directly without socat.

## What you can verify yourself

- The job you receive is built from the live Bitcoin chain tip; the coinbase in every job contains the bytes `/PLSGH/`.
- Found blocks are public on the Bitcoin chain, tag and payout included; the pool's payout transaction spends that coinbase and pays each worker address on chain.
- Pool and ledger status: `/status`, `/pool`, `/epochs` on this door.

## Run an entrance for this pool (free, for anyone)

The pool needs no paid server to be reachable by name. Anyone with an Ubuntu box that has a public address can host a public entrance in one command: it runs its own Tor client and forwards its port 3333 into the pool onion. The entrance learns nothing about the pool's location and holds no secret; the pool learns nothing about the entrance. Fetch the script from this door at `/pool/relay` and run it as root:
```
curl --socks5-hostname localhost:9050 -o relay.sh http://n4deym4zszn2pxwxydrr4phtw2zownckvbhllgmhjesiy756ykgdwjad.onion/pool/relay
sudo bash relay.sh
```
Point a DNS name at that box if you like, and miners near you can use `stratum+tcp://that-name:3333` without any Tor setup of their own. Read the script before you run it; it is short.

## Rules of the house

- One pool, one treasury, no custody of your coins: the only thing the pool ever holds for you is a balance under 10,000 sat waiting for the next block.
- The pool does not log your network address; through Tor it never sees one.
- Hardware you point here is yours; the pool offers work and pays for it, nothing else.
