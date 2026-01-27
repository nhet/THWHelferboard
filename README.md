
# Helferboard – Webapplikation

- Admin unter `/admin`
- Öffentliche Anzeige unter `/`

## Start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Docker:
```bash
cd backend
docker build -t helferboard-backend .
root@organigramm:/home/pi/helferboard# docker run -d -p 8080:80 --name helferboard-app -v helferboard-db:/app/db -v helferboard-uploads:/app/app/static/uploads -e TMP=/app/tmp -e TMPDIR=/app/tmp --tmpfs /app/tmp:rw,size=30m helferboard-backend
```

### Version Information
The current version is displayed on the admin page at `/admin`.
