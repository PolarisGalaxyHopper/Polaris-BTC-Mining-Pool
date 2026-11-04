#!/bin/bash
# install.sh — Polaris Pool client: Tor + a stratum forwarder as a service, plus the pool terminal. Debian/Ubuntu/Raspberry Pi OS.
# Run as root on the box that will sit between your miners and the pool:   sudo bash install.sh
# Afterwards point each ASIC at  stratum+tcp://<this box's LAN address>:3333  with worker = your payout address (.rigname optional).
set -eu
ONION="orov3hzmryyh65ryggnud63heedmbsevp7uie6wos7nmen2cwlfdqwqd.onion"
read -rp "Your Bitcoin payout address (bc1…): " ADDR
case "$ADDR" in bc1q*|bc1p*|1*|3*) ;; *) echo "that does not look like a Bitcoin address"; exit 1;; esac
LAN=$(hostname -I 2>/dev/null | awk '{print $1}'); read -rp "LAN address to listen on [$LAN]: " L; LAN=${L:-$LAN}
export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq tor torsocks socat python3 >/dev/null
systemctl enable --now tor >/dev/null
cat > /etc/systemd/system/polaris-pool-proxy.service <<U
[Unit]
Description=Polaris Pool proxy — LAN :3333 → Tor → pool onion
After=network-online.target tor.service
Wants=network-online.target tor.service
[Service]
ExecStart=/usr/bin/socat -T 600 TCP-LISTEN:3333,fork,reuseaddr,bind=${LAN} SOCKS4A:localhost:${ONION}:3333,socksport=9050
Restart=always
RestartSec=3
DynamicUser=yes
NoNewPrivileges=yes
[Install]
WantedBy=multi-user.target
U
systemctl daemon-reload; systemctl enable --now polaris-pool-proxy >/dev/null
install -d /opt/polaris-pool; install -m 755 "$(dirname "$0")/polaris_pool_terminal.py" "$(dirname "$0")/verify_job.py" /opt/polaris-pool/
cat > /usr/local/bin/polaris-pool <<W
#!/bin/bash
# the pool terminal, through Tor, with your address pinned
exec torsocks python3 /opt/polaris-pool/polaris_pool_terminal.py --door --me "$ADDR" "\$@"
W
chmod 755 /usr/local/bin/polaris-pool
echo; echo "proxy: $(systemctl is-active polaris-pool-proxy) on ${LAN}:3333 → Tor → pool"
echo "ASIC settings:   URL stratum+tcp://${LAN}:3333   worker ${ADDR}.rig1   password x"
echo "terminal:        polaris-pool        (your workers, shares, blocks, payouts — read through Tor)"
echo "verify a job:    torsocks python3 /opt/polaris-pool/verify_job.py 30 ${ADDR}"
