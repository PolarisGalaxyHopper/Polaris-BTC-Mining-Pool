[README.md](https://github.com/user-attachments/files/34354184/README.md)
# Polaris-BTC-Mining-Pool
Public interface and proxy tools for Polaris BTC Miner. Zero-exposure Tor routing, local LAN forwarders, and direct Stratum connectivity for home hardware and ASIC rigs.
# Polaris Pool Client

Connect your miners to the **Polaris Pool — a sovereign Bitcoin pool** and watch them from your own computer. No account, no browser, no personal data. The pool is reached only through Tor; everything here runs on your side.

## What you get

- **A full terminal interface** (`polaris-pool`): a **Setup** tab with fields for your payout address, rig name, proxy address and Tor port, a one-key proxy start, and the exact settings to type into each miner; then **Dashboard**, **Workers** (your rigs: hashrate, shares, best share, last share), **Shares** (watch them arrive), **Blocks & payouts** (what you are owed and paid, on-chain ids), **Entrance** (with a one-key handshake test) and **Help**. Clickable tabs, mouse wheel, same console on Linux, macOS and Windows.
- **A LAN proxy** so ASICs, which cannot speak Tor, reach the pool: `install.sh` sets it up as a service on a Linux box or Raspberry Pi.
- **`verify_job.py`**: ask the pool for one job and see for yourself that its coinbase carries `/PLSGH/` and pays the pool treasury.
- **`relay_setup.sh`**: host a public entrance for the pool on any box with a public address, with no knowledge of the pool's location.
- **`docs/CONNECT_GUIDE.md`**: the full guide, also served by the pool's Tor door at `/pool/guide`.

## What can connect

Anything that speaks stratum: ASIC, GPU or CPU. Shares are credited by difficulty, so each machine is paid in exact proportion to the work it did. One S9-class ASIC does about 9 TH/s; a strong GPU about 1 GH/s (ten thousand times less); a CPU core 1–3 MH/s (millions of times less). Minimum share difficulty is 1. The terminal tells every machine the pool's share of the network and the honest expected time to a block.

## Install

**Option A, the proxy box (Linux / Raspberry Pi, recommended for ASICs)**
```
git clone <this repository> && cd POLARIS_POOL_CLIENT_KIT
sudo bash install.sh        # installs Tor + the LAN proxy service + the terminal; asks for your payout address
polaris-pool                  # the terminal (press 1 for Setup)
```

**Option B, terminal only (Linux, macOS, Windows)**
```
pip install .               # or: pipx install .
polaris-pool --door           # needs a local Tor SOCKS port: the tor service (9050) or Tor Browser running (9150, set it in Setup)
```
Windows: `pip install windows-curses` first, and run it in Windows Terminal. On Windows the proxy for ASICs still needs a Linux box or Raspberry Pi; the terminal itself works anywhere.

Then in each miner: URL `stratum+tcp://<proxy LAN address>:3333`, worker `<your payout address>.rig1`, password `x`. The Setup tab prints exactly these lines for your values. Software miners that take a SOCKS proxy can point straight at the onion instead.

## Facts

- Pool fee 1.5 %. PPLNS: when a block is found, the last shares worth 2 × network difficulty share 98.5 % of the reward in proportion to difficulty submitted. Paid on chain after 100 confirmations; amounts under 10,000 sat are carried to the next block.
- Your payout address is your identity. The pool rejects a worker name that is not a valid Bitcoin address.
- Through Tor the pool never sees your network address and you never see its.
- A small pool finds blocks rarely. The Dashboard shows the expected time to a block for the pool's current hashrate. Decide with that number in front of you.

## Files

| file | role |
|---|---|
| `polaris_pool_terminal.py` | the terminal (standard library only; SOCKS5 built in) |
| `install.sh` | proxy service + terminal installer for Linux |
| `verify_job.py` | one-job verification through Tor |
| `relay_setup.sh` | public entrance host script |
| `docs/CONNECT_GUIDE.md` | the guide |
| `pyproject.toml` | `pip install .` → the `polaris-pool` command |

## Licence

MIT. This repository contains the client side only.
