#!/bin/bash
set -e

echo "=== Pixolab Server Setup ==="

# Update system
echo "[1/8] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y git nginx python3-pip python3-venv python3-dev \
    build-essential curl certbot python3-certbot-nginx \
    iptables netfilter-persistent iptables-persistent

# Install Node.js 20
echo "[2/8] Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Open OS firewall ports
echo "[3/8] Configuring firewall..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

# Clone repo
echo "[4/8] Cloning repository..."
if [ -d "/home/ubuntu/pixolab" ]; then
    cd /home/ubuntu/pixolab && git pull
else
    git clone https://github.com/wahab5763/pixolab.online.git /home/ubuntu/pixolab
fi

# Create storage folders
mkdir -p /home/ubuntu/pixolab/backend/storage/uploads
mkdir -p /home/ubuntu/pixolab/backend/storage/results

# Python setup
echo "[5/8] Setting up Python environment..."
python3 -m venv /home/ubuntu/pixolab/backend/.venv
/home/ubuntu/pixolab/backend/.venv/bin/pip install --upgrade pip
/home/ubuntu/pixolab/backend/.venv/bin/pip install -r /home/ubuntu/pixolab/backend/requirements.txt
/home/ubuntu/pixolab/backend/.venv/bin/pip install -r /home/ubuntu/pixolab/backend/requirements-optional-ai.txt

# Create .env
echo "[6/8] Creating .env file..."
cat > /home/ubuntu/pixolab/backend/.env << 'ENVEOF'
APP_NAME=Pixolab
DATABASE_URL=sqlite:///./pixolab.db
BACKEND_URL=http://localhost:8000
CORS_ORIGINS=*
ENABLE_BACKGROUND_REMOVAL=true
HF_TOKEN=
ENABLE_HF_BACKGROUND=false
ENVEOF

# Build frontend
echo "[7/8] Building frontend..."
cd /home/ubuntu/pixolab/frontend
npm install
npm run build

# Systemd service
echo "[8/8] Configuring services..."
sudo tee /etc/systemd/system/pixolab.service > /dev/null << 'SVCEOF'
[Unit]
Description=Pixolab Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/pixolab/backend
Environment="PATH=/home/ubuntu/pixolab/backend/.venv/bin"
ExecStart=/home/ubuntu/pixolab/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable pixolab
sudo systemctl start pixolab

# Nginx config
sudo tee /etc/nginx/sites-available/pixolab > /dev/null << 'NGXEOF'
server {
    listen 80;
    server_name _;
    root /home/ubuntu/pixolab/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 25M;
        proxy_read_timeout 120s;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:8000;
    }
}
NGXEOF

sudo ln -sf /etc/nginx/sites-available/pixolab /etc/nginx/sites-enabled/pixolab
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

echo ""
echo "=== Setup Complete! ==="
echo "Backend status:"
sudo systemctl status pixolab --no-pager | head -5
echo ""
echo "Nginx status:"
sudo systemctl status nginx --no-pager | head -5
echo ""
echo "Visit: http://$(curl -s ifconfig.me)"
