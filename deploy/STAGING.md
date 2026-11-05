# Staging only: independent service, without JACKSIDE/Timer changes

Preparation (run as deploy user in a **new** folder, not `/opt/hi-jack-admin-helper-v2`):

```bash
sudo mkdir -p /opt/sochi-show
sudo chown "$USER":www-data /opt/sochi-show
# Upload the extracted project to /opt/sochi-show using scp/rsync or git.
cd /opt/sochi-show
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
openssl rand -hex 32
openssl rand -hex 32
# Set both secrets in .env, SOCHI_SECURE_COOKIE=false ONLY over localhost/SSH tunnel
set -a; source .env; set +a
.venv/bin/pytest -q
```

Start isolated service only AFTER tests, secrets and DB directories are ready:

```bash
sudo mkdir -p /opt/sochi-show/data/media
sudo chown -R www-data:www-data /opt/sochi-show/data
sudo chown root:root /opt/sochi-show/.env
sudo chmod 600 /opt/sochi-show/.env
sudo cp /opt/sochi-show/deploy/sochi-show.service.example /etc/systemd/system/sochi-show.service
sudo systemctl daemon-reload
sudo systemctl enable --now sochi-show.service
sudo systemctl status sochi-show.service --no-pager
curl -fsS http://127.0.0.1:8092/health
# Once the service has created its database, back it up separately:
cd /opt/sochi-show && sudo -u www-data .venv/bin/python scripts/backup.py --database data/sochi.sqlite3 --media data/media --out /tmp/sochi-backups
```

SSH-tunnel from laptop (no public Nginx or firewall changes):

```bash
ssh -L 8092:127.0.0.1:8092 USER@VPS
```

Browser locally: `http://127.0.0.1:8092/sochi/admin` and `http://127.0.0.1:8092/sochi/screen`.

**Important:** on staging with local HTTP the cookie is `SOCHI_SECURE_COOKIE=false` and the app only listens on 127.0.0.1. For real external HTTPS, use a separate domain such as `sochi.hijackpoker.ru`, enable `SOCHI_SECURE_COOKIE=true`, and provision a separate TLS vhost. No edits to existing Nginx files or main services are required.

Rollback for this staging module only:

```bash
sudo systemctl stop sochi-show.service
# Restore only /opt/sochi-show/data from /opt/sochi-show/backups/<timestamp>
# If rollback to an earlier code revision is needed, checkout that commit only within /opt/sochi-show.
sudo systemctl start sochi-show.service
curl -fsS http://127.0.0.1:8092/health
```

Never copy `club_tools.sqlite3` or Hi Jack Timer DB into the SOCHI SHOW folder.
