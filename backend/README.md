
# Helferboard – Option A (inkl. Admin-Import für Funktionen)

## Features
- Admin: Gruppen, Funktionen, Helfer (CRUD), Basic Auth per ENV `ADMIN_USER`, `ADMIN_PASSWORD`
- Öffentliche Seite: Porträt/HD, 9 Kacheln pro Reihe, Platzhalter-Bild, Emblem (SVG)
- Gruppen: robuster parent_id-Fix (""/"0" → `None`)
- Helfer: Foto löschen möglich
- **NEU**: Funktionen-Import
  - `/admin/functions/import` mit Datei-Upload (CSV), Vorschau, Automatik für `short_name` (optional), Dublettenprüfung und automatischer Sortierung (10er Schritte)

## Start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scriptsctivate
pip install -r requirements.txt
export ADMIN_USER=admin ADMIN_PASSWORD=admin
uvicorn app.main:app --reload
```
- Admin: http://localhost:8000/admin
- Import: http://localhost:8000/admin/functions/import
- Public: http://localhost:8000/

## CSV-Format
Pflicht: `name`  | Optional: `short_name`
```csv
name,short_name
Zugführer/in,
Gruppenführer/in Bergung,
```
