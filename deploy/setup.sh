#!/bin/bash
# LabTrack - One-time Server Setup Script
#
# Prerequisites:
#   - Debian 12 server with nginx, Python 3.11, Node 18+
#   - DNS A record: labtrack.bodytools.work -> server IP
#   - SSH access as root or sudo user
#   - .env file scp'd to /opt/labtrack/backend/.env before running
#
# Usage:
#   sudo bash /opt/labtrack/deploy/setup.sh

set -e

APP_NAME="labtrack"
APP_DIR="/opt/${APP_NAME}"
WEB_DIR="/var/www/${APP_NAME}"
BACKEND_DIR="${APP_DIR}/backend"
REPO_URL="https://github.com/grbod/labtrack.git"

echo "=========================================="
echo " LabTrack Server Setup"
echo "=========================================="

# 1. Create system user
echo "[1/8] Creating system user..."
if id "${APP_NAME}" &>/dev/null; then
    echo "  User '${APP_NAME}' already exists"
else
    useradd --system --shell /usr/sbin/nologin --home-dir "${APP_DIR}" "${APP_NAME}"
    echo "  Created user '${APP_NAME}'"
fi

# 2. Clone repository
echo "[2/8] Setting up repository..."
if [ -d "${APP_DIR}/.git" ]; then
    echo "  Repository already exists, pulling latest..."
    cd "${APP_DIR}"
    git fetch origin main
    git reset --hard origin/main
else
    git clone "${REPO_URL}" "${APP_DIR}"
fi
chown -R "${APP_NAME}:${APP_NAME}" "${APP_DIR}"

# 3. Create Python virtual environment and install dependencies
echo "[3/8] Setting up Python environment..."
cd "${BACKEND_DIR}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
deactivate

# 4. Check for .env file
echo "[4/8] Checking .env file..."
if [ ! -f "${BACKEND_DIR}/.env" ]; then
    echo "  WARNING: .env file not found at ${BACKEND_DIR}/.env"
    echo "  Please scp your .env file before starting the service:"
    echo "    scp .env.production root@SERVER:${BACKEND_DIR}/.env"
else
    echo "  .env file found"
    chown "${APP_NAME}:${APP_NAME}" "${BACKEND_DIR}/.env"
    chmod 600 "${BACKEND_DIR}/.env"
fi

# 5. Initialize database
echo "[5/8] Initializing database..."
cd "${BACKEND_DIR}"
source venv/bin/activate
python -c "from app.database import init_db; init_db()" 2>/dev/null || echo "  Database init will run on first start"
deactivate

# Create data, uploads, COAs, and exports directories
mkdir -p "${BACKEND_DIR}/data" "${BACKEND_DIR}/uploads" "${BACKEND_DIR}/COAs" "${BACKEND_DIR}/exports"
chown -R "${APP_NAME}:${APP_NAME}" "${BACKEND_DIR}/data" "${BACKEND_DIR}/uploads" "${BACKEND_DIR}/COAs" "${BACKEND_DIR}/exports"

# 6. Create web directory for frontend
echo "[6/8] Setting up web directory..."
mkdir -p "${WEB_DIR}"
chown -R "${APP_NAME}:${APP_NAME}" "${WEB_DIR}"

# Create log directory
mkdir -p "/var/log/${APP_NAME}"
chown -R "${APP_NAME}:${APP_NAME}" "/var/log/${APP_NAME}"

# 7. Install systemd service
echo "[7/8] Installing systemd service..."
cp "${APP_DIR}/deploy/labtrack-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable labtrack-api

# 8. Install nginx configuration (copy, not symlink — certbot modifies it in-place)
echo "[8/8] Installing nginx configuration..."
if [ ! -f "/etc/nginx/sites-available/${APP_NAME}" ]; then
    cp "${APP_DIR}/deploy/nginx.conf" "/etc/nginx/sites-available/${APP_NAME}"
    ln -sf "/etc/nginx/sites-available/${APP_NAME}" "/etc/nginx/sites-enabled/${APP_NAME}"
    echo "  Nginx config installed (run certbot after setup to add SSL)"
else
    echo "  Nginx config already exists, skipping (preserves certbot SSL)"
fi

# Test nginx config
if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "  Nginx configured and reloaded"
else
    echo "  WARNING: Nginx config test failed. Check /etc/nginx/sites-available/${APP_NAME}"
fi

echo ""
echo "=========================================="
echo " Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Ensure .env file is at ${BACKEND_DIR}/.env"
echo "  2. Start the service:  sudo systemctl start labtrack-api"
echo "  3. Get SSL cert:       sudo certbot --nginx -d labtrack.bodytools.work"
echo "  4. Check status:       sudo systemctl status labtrack-api"
echo "  5. View logs:          sudo journalctl -u labtrack-api -f"
echo ""
echo "The GitHub Actions workflow will handle future deployments automatically."
