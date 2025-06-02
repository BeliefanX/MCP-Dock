# Deployment Guide

This guide covers different deployment options for MCP-Dock in production environments.

## 🚀 Quick Deployment

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- 2GB+ RAM
- 200MB+ disk space

### Basic Deployment

```bash
# Clone repository
git clone https://github.com/your-username/MCP-Dock.git
cd MCP-Dock

# Install dependencies
uv sync

# Configure services
cp mcp_dock/config/mcp.config.example.json mcp_dock/config/mcp.config.json
cp mcp_dock/config/proxy_config.example.json mcp_dock/config/proxy_config.json

# Edit configurations
nano mcp_dock/config/mcp.config.json
nano mcp_dock/config/proxy_config.json

# Start server
uv run uvicorn mcp_dock.api.gateway:app --host 0.0.0.0 --port 8000
```

## 🐧 Linux Production Deployment

### 1. System Service (Systemd)

Create a systemd service for automatic startup and management:

```bash
# Create service file
sudo nano /etc/systemd/system/mcp-dock.service
```

```ini
[Unit]
Description=MCP-Dock Proxy Server
After=network.target
Wants=network.target

[Service]
Type=exec
User=mcp-dock
Group=mcp-dock
WorkingDirectory=/opt/mcp-dock
Environment=PATH=/opt/mcp-dock/.venv/bin
ExecStart=/opt/mcp-dock/.venv/bin/uvicorn mcp_dock.api.gateway:app --host 0.0.0.0 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Create user and directories
sudo useradd -r -s /bin/false mcp-dock
sudo mkdir -p /opt/mcp-dock
sudo chown mcp-dock:mcp-dock /opt/mcp-dock

# Deploy application
sudo -u mcp-dock git clone https://github.com/your-username/MCP-Dock.git /opt/mcp-dock
cd /opt/mcp-dock
sudo -u mcp-dock uv sync

# Configure
sudo -u mcp-dock cp mcp_dock/config/mcp.config.example.json mcp_dock/config/mcp.config.json
sudo -u mcp-dock cp mcp_dock/config/proxy_config.example.json mcp_dock/config/proxy_config.json

# Edit configurations as needed
sudo -u mcp-dock nano mcp_dock/config/mcp.config.json
sudo -u mcp-dock nano mcp_dock/config/proxy_config.json

# Enable and start service
sudo systemctl enable mcp-dock
sudo systemctl start mcp-dock
sudo systemctl status mcp-dock
```

### 2. Reverse Proxy (Nginx)

Configure Nginx for SSL termination and load balancing:

```bash
# Install Nginx
sudo apt update
sudo apt install nginx

# Create configuration
sudo nano /etc/nginx/sites-available/mcp-dock
```

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Proxy configuration
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/mcp-dock /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 🐳 Docker Deployment (Planned)

### Dockerfile

```dockerfile
FROM python:3.12-slim

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy application
COPY . .

# Create non-root user
RUN useradd -r -s /bin/false mcp-dock && \
    chown -R mcp-dock:mcp-dock /app

USER mcp-dock

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uv", "run", "uvicorn", "mcp_dock.api.gateway:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  mcp-dock:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./mcp_dock/config:/app/mcp_dock/config
      - ./logs:/app/logs
    environment:
      - MCP_DOCK_LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - mcp-dock
    restart: unless-stopped
```

## ☁️ Cloud Deployment

### AWS EC2

```bash
# Launch EC2 instance (Ubuntu 22.04 LTS)
# Security group: Allow ports 22, 80, 443, 8000

# Connect and setup
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.12
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Deploy application (follow Linux deployment steps above)
```

### Google Cloud Platform

```bash
# Create VM instance
gcloud compute instances create mcp-dock-instance \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --machine-type=e2-medium \
    --zone=us-central1-a \
    --tags=http-server,https-server

# SSH and deploy
gcloud compute ssh mcp-dock-instance --zone=us-central1-a
# Follow Linux deployment steps
```

### DigitalOcean

```bash
# Create droplet via web interface or API
# Choose Ubuntu 22.04, 2GB RAM minimum

# SSH and deploy
ssh root@your-droplet-ip
# Follow Linux deployment steps
```

## 🔧 Configuration for Production

### Environment Variables

```bash
# Create environment file
sudo nano /opt/mcp-dock/.env
```

```bash
# Server configuration
MCP_DOCK_HOST=0.0.0.0
MCP_DOCK_PORT=8000
MCP_DOCK_WORKERS=4

# Logging
MCP_DOCK_LOG_LEVEL=INFO
MCP_DOCK_LOG_FILE=/var/log/mcp-dock/app.log

# Security
MCP_DOCK_CORS_ORIGINS=["https://your-domain.com"]

# Performance
MCP_DOCK_MAX_CONNECTIONS=1000
MCP_DOCK_SESSION_TIMEOUT=300
```

### Production Configuration

```json
{
  "servers": {
    "production_service": {
      "command": "python",
      "args": ["-m", "production_mcp_server"],
      "transport_type": "stdio",
      "auto_start": true,
      "env": {
        "PRODUCTION": "true",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Monitoring and Logging

```bash
# Create log directory
sudo mkdir -p /var/log/mcp-dock
sudo chown mcp-dock:mcp-dock /var/log/mcp-dock

# Logrotate configuration
sudo nano /etc/logrotate.d/mcp-dock
```

```
/var/log/mcp-dock/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 mcp-dock mcp-dock
    postrotate
        systemctl reload mcp-dock
    endscript
}
```

## 📊 Monitoring

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Service status
curl http://localhost:8000/api/service/

# Proxy status
curl http://localhost:8000/api/proxy/
```

### Log Monitoring

```bash
# Follow logs
sudo journalctl -u mcp-dock -f

# Check recent errors
sudo journalctl -u mcp-dock --since "1 hour ago" -p err

# Application logs
tail -f /var/log/mcp-dock/app.log
```

## 🔒 Security Considerations

### Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# For development only
sudo ufw allow 8000
```

### SSL/TLS

```bash
# Let's Encrypt with Certbot
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Access Control

- Use reverse proxy for SSL termination
- Implement IP whitelisting if needed
- Consider VPN access for management endpoints
- Regular security updates

## 🚨 Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   sudo systemctl status mcp-dock
   sudo journalctl -u mcp-dock -n 50
   ```

2. **Port conflicts**
   ```bash
   sudo netstat -tlnp | grep :8000
   sudo lsof -i :8000
   ```

3. **Permission issues**
   ```bash
   sudo chown -R mcp-dock:mcp-dock /opt/mcp-dock
   sudo chmod +x /opt/mcp-dock/start.sh
   ```

4. **SSL certificate issues**
   ```bash
   sudo certbot certificates
   sudo nginx -t
   ```

This deployment guide provides a solid foundation for running MCP-Dock in production environments with proper security, monitoring, and reliability considerations.
