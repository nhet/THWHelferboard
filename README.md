
# Helferboard – Webapplikation

- Admin unter `/admin` (Basic Auth via ENV: `ADMIN_USER`, `ADMIN_PASSWORD`)
- Öffentliche Anzeige unter `/`

## Anforderungen
- Gruppen (Bezeichnung, übergeordnet, Sortierung)
- Funktionen (Bezeichnung, Kurz, Emblem **SVG**, Sortierung)
- Helfer (Vorname, Nachname, Foto, Gruppe, **eine Hauptfunktion**, beliebig viele Nebenfunktionen)
- Öffentliche Seite: Portrait/HD, Gruppen hierarchisch, Helfer **horizontal** in Kacheln, max **9** pro Zeile, Kachel: **Bild → Vorname → Nachname → Emblem (Hauptfunktion)**
- Platzhalter-Bild wenn kein Foto vorhanden
- Admin: Foto kann gelöscht werden
- Robuster Fix: `parent_id` akzeptiert `""` und `"0"` → `None`

## Start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ADMIN_USER=admin ADMIN_PASSWORD=admin
uvicorn app.main:app --reload
```

Docker:
```bash
cd backend
docker build -t helferboard-backend .
docker run -p 8000:8000 -e ADMIN_USER=admin -e ADMIN_PASSWORD=admin   -v $(pwd)/app/static/uploads:/app/app/static/uploads helferboard-backend
```

## Raspberry Pi Deployment (PiOS Trixie)

### Prerequisites
- Raspberry Pi with PiOS Trixie (Debian-based)
- Internet connection for package installation
- Root access (sudo)

### Deployment Steps
1. Download the latest `helferboard.zip` from GitHub Actions artifacts
2. Extract to `/opt/helferboard`:
   ```bash
   sudo mkdir -p /opt/helferboard
   sudo unzip helferboard.zip -d /opt/helferboard
   ```
3. Run the deployment script:
   ```bash
   cd /opt/helferboard
   sudo ./scripts/deploy.sh
   ```

### Service Management
- Start service: `sudo systemctl start helferboard.service`
- Stop service: `sudo systemctl stop helferboard.service`
- Restart service: `sudo systemctl restart helferboard.service`
- Check status: `sudo systemctl status helferboard.service`
- View logs: `sudo journalctl -u helferboard.service -f`

### Access
- Public interface: http://localhost:8000
- Admin interface: http://localhost:8000/admin (credentials via environment variables)

### Environment Variables
Set these in `/etc/systemd/system/helferboard.service` or create `/opt/helferboard/.env`:
- `ADMIN_USER`: Admin username (default: admin)
- `ADMIN_PASSWORD`: Admin password (default: admin)

### Version Information
The current version is displayed on the admin page at `/admin`.
