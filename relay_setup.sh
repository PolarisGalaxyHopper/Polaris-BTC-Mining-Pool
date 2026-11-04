#!/bin/bash
# relay_vm_setup_tor.sh — public stratum entrance for the the pool pool that NEVER learns the home address (2026-11-03).
# Design: the relay reaches the pool only through Tor (relay → Tor → pool onion → ckpool on the pool's loopback). No WireGuard,
# no tunnel from the house, nothing on the VM points at the home connection. The VPS provider sees Tor traffic, nothing else.
# Any Ubuntu 22.04/24.04 VPS with a public IPv4 works (1 vCPU / 1 GB is plenty; stratum is a few kB/s per miner).
# Run ON the VM as root (Tars runs it over ssh after the operator hands back the address privately):   bash relay_vm_setup_tor.sh
# Rollback: systemctl disable --now polaris-stratum-relay; the VM holds no secret of ours.
set -eu
ONION="orov3hzmryyh65ryggnud63heedmbsevp7uie6wos7nmen2cwlfdqwqd.onion"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq tor socat nftables fail2ban unattended-upgrades >/dev/null
systemctl enable --now tor >/dev/null
cat > /etc/systemd/system/polaris-stratum-relay.service <<U
[Unit]
Description=Polaris Pool stratum relay — public tcp/3333 → Tor → pool onion (no home address involved)
After=network-online.target tor.service
Wants=network-online.target tor.service
[Service]
ExecStart=/usr/bin/socat -T 600 TCP-LISTEN:3333,fork,reuseaddr,max-children=400 SOCKS4A:localhost:${ONION}:3333,socksport=9050
Restart=always
RestartSec=3
DynamicUser=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
U
systemctl daemon-reload; systemctl enable --now polaris-stratum-relay >/dev/null
cat > /etc/nftables.conf <<N
#!/usr/sbin/nft -f
flush ruleset
table inet filter {
  set ratelimit4 { type ipv4_addr; flags dynamic; timeout 1m; }
  chain input {
    type filter hook input priority 0; policy drop;
    ct state established,related accept
    iif lo accept
    ip protocol icmp accept
    tcp dport 22 ct state new limit rate 10/minute accept
    tcp dport 3333 ct state new meter m3333 { ip saddr ct count over 20 } drop
    tcp dport 3333 ct state new limit rate 50/second accept
  }
  chain forward { type filter hook forward priority 0; policy drop; }
  chain output  { type filter hook output priority 0; policy accept; }
}
N
systemctl enable --now nftables >/dev/null; nft -f /etc/nftables.conf
sleep 3; echo "relay: $(systemctl is-active polaris-stratum-relay) · tor: $(systemctl is-active tor) · listening: $(ss -ltnH | awk '{print $4}' | grep ':3333' | paste -sd' ')"
echo "self-test (through this relay → Tor → pool):"; printf '{"id":1,"method":"mining.subscribe","params":["relay-selftest/1.0"]}\n' | timeout 40 socat - TCP:localhost:3333 2>/dev/null | head -c 300 || echo "(no answer: the pool is switched off, or Tor still bootstrapping — retry in a minute)"
echo "DONE — next: DNS A record for the pool name → this VM's address; then the pool page/guide get the clearnet line."
