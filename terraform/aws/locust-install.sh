#!/bin/bash
cd /home/ubuntu
add-apt-repository -y ppa:redislabs/redis
apt update
apt -y upgrade
apt -y install redis-tools
apt-get install python3-pip -y
pip3 install locust
pip3 install redis
pip3 install scipy
wget https://github.com/prometheus/node_exporter/releases/download/v1.4.0/node_exporter-1.4.0.linux-amd64.tar.gz
tar xvfz node_exporter-1.4.0.linux-amd64.tar.gz
cd node_exporter-1.4.0.linux-amd64
cp node_exporter /usr/local/bin
useradd --no-create-home --shell /bin/false node_exporter
chown node_exporter:node_exporter /usr/local/bin/node_exporter
cat << EOF >> /etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target
[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter
[Install]
WantedBy=multi-user.target
EOF
cat << EOF >> /etc/security/limits.conf
* soft nproc 65535
* hard nproc 65535
* soft nofile 65535
* hard nofile 65535
EOF
ulimit -n 10000
systemctl daemon-reload
systemctl start node_exporter
systemctl enable node_exporter.service
usermod -a -G node_exporter ubuntu