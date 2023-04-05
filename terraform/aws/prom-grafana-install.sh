#!/bin/bash
apt update
apt -y upgrade
mkdir /home/ubuntu/prom-grafana-install
cd /home/ubuntu/prom-grafana-install

apt-get install -y apt-transport-https -y
wget -q -O /usr/share/keyrings/grafana.key https://packages.grafana.com/gpg.key
echo "deb [signed-by=/usr/share/keyrings/grafana.key] https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
apt-get update
apt-get install grafana -y

# Create directory to hold provisioned dashboards.  Other writable so terraform file provisioner can
# easily drop files into the directory
mkdir /var/lib/grafana/dashboards
chown grafana /var/lib/grafana/dashboards
chgrp grafana /var/lib/grafana/dashboards
chmod o+w /var/lib/grafana/dashboards

cat << EOF >> /etc/grafana/provisioning/datasources/local-prometheus.yaml
# config file version
apiVersion: 1

# list of datasources that should be deleted from the database
deleteDatasources:
  - name: Prometheus
    orgId: 1

    apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    # Access mode - proxy (server in the UI) or direct (browser in the UI).
    access: proxy
    url: http://localhost:9090
    jsonData:
      httpMethod: POST
    editable: true
EOF
chown grafana /etc/grafana/provisioning/datasources/local-prometheus.yaml
chgrp grafana /etc/grafana/provisioning/datasources/local-prometheus.yaml

cat << EOF >> /etc/grafana/provisioning/dashboards/default.yaml
# config file version
apiVersion: 1

providers:
 - name: 'default'
   orgId: 1
   folder: ''
   folderUid: ''
   type: file
   disableDeletion: false
   options:
     path: /var/lib/grafana/dashboards
EOF

chown grafana /etc/grafana/provisioning/dashboards/default.yaml
chgrp grafana /etc/grafana/provisioning/dashboards/default.yaml

systemctl daemon-reload
systemctl start grafana-server
systemctl enable grafana-server.service

mkdir -p /etc/prometheus
mkdir -p /var/lib/prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.1/prometheus-2.40.1.linux-amd64.tar.gz
tar -xvf prometheus-2.40.1.linux-amd64.tar.gz
cd prometheus-2.40.1.linux-amd64
mv prometheus /usr/local/bin/
mv promtool /usr/local/bin/
mv consoles/ console_libraries/ /etc/prometheus/
mv prometheus.yml /etc/prometheus/prometheus.yml
groupadd --system prometheus
useradd -s /sbin/nologin --system -g prometheus prometheus
chown -R prometheus:prometheus /etc/prometheus/ /var/lib/prometheus/
chmod -R 775 /etc/prometheus/ /var/lib/prometheus/

cat << EOF >> /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Restart=always
Type=simple
ExecStart=/usr/local/bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus/ \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries \
    --web.listen-address=0.0.0.0:9090

[Install]
WantedBy=multi-user.target
EOF

mv /etc/prometheus/prometheus.yml /etc/prometheus/prometheus.yml.old
cat << EOF >> /etc/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

  # Attach these labels to any time series or alerts when communicating with
  # external systems (federation, remote storage, Alertmanager).
  external_labels:
    monitor: "prometheus-stack-monitor"

scrape_configs:
  # scrape Prometheus itself
  - job_name: prometheus-grafana-host
    scrape_interval: 10s
    scrape_timeout: 5s
    static_configs:
      - targets: ["localhost:9090"]

  # scrape Prometheus itself
  - job_name: locust-machines
    scrape_interval: 10s
    scrape_timeout: 5s
    static_configs:
      - targets: [
          "intr-tboyd-locust-master.redisdemo.com:9100",
          "intr-tboyd-locust-worker-001.redisdemo.com:9100",
          "intr-tboyd-locust-worker-002.redisdemo.com:9100",
          "intr-tboyd-locust-worker-003.redisdemo.com:9100",
          "intr-tboyd-locust-worker-004.redisdemo.com:9100",
          "intr-tboyd-locust-worker-005.redisdemo.com:9100",
          "intr-tboyd-locust-worker-006.redisdemo.com:9100"
          ]
EOF

systemctl start prometheus
systemctl enable prometheus