import subprocess
from datetime import datetime
import os
import asyncio
import sys
from typing import Optional, List
import zipfile
import shutil
import tempfile
from pathlib import Path
import csv
import io

from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
import itertools
from sqlalchemy.orm import joinedload
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.status import HTTP_303_SEE_OTHER
from sqlalchemy import or_, text, exists
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sa_func

from .database import Base, engine, get_db
from .models import Group, Function, Helper, Setting, CarouselImage, GroupImage, helper_secondary_functions
from .version import __version__

class CacheStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        self.cache_timeout = 31536000  # 1 Jahr in Sekunden
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = f"public, max-age={self.cache_timeout}, immutable"
        return response

app = FastAPI(title="Helferboard")

BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
app.mount("/static",                  CacheStaticFiles(directory=static_dir),                      name="static")
app.mount("/static/uploads/photos",   CacheStaticFiles(directory=static_dir / "uploads/photos"),   name="photos")
app.mount("/static/uploads/emblems",  CacheStaticFiles(directory=static_dir / "uploads/emblems"),  name="emblems")
app.mount("/static/uploads/groups",   CacheStaticFiles(directory=static_dir / "uploads/groups"),   name="groups")
app.mount("/static/uploads/carousel", CacheStaticFiles(directory=static_dir / "uploads/carousel"), name="carousel")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.add_extension('jinja2.ext.do')

# Auth
security = HTTPBasic()
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if not (credentials.username == ADMIN_USER and credentials.password == ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def initialize_last_update():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT value FROM settings WHERE key = 'last_update'"))
            if not result.fetchone():
                now = datetime.now().isoformat()
                conn.execute(text("INSERT INTO settings (key, value) VALUES (:key, :value)"), {"key": "last_update", "value": now})
                conn.commit()
    except Exception as e:
        print(f"Error initializing settings: {e}")

def get_last_update(db: Session) -> datetime:
    setting = db.query(Setting).filter(Setting.key == "last_update").first()
    if setting:
        return datetime.fromisoformat(setting.value)
    return datetime.now()

def set_last_update(db: Session):
    now = datetime.now()
    setting = db.query(Setting).filter(Setting.key == "last_update").first()
    if setting:
        setting.value = now.isoformat()
    else:
        setting = Setting(key="last_update", value=now.isoformat())
        db.add(setting)

def get_incognito_level(db: Session) -> int:
    setting = db.query(Setting).filter(Setting.key == "incognito_level").first()
    if setting:
        try:
            return int(setting.value)
        except:
            return 0
    return 0

def set_incognito_level(db: Session, value: int):
    setting = db.query(Setting).filter(Setting.key == "incognito_level").first()
    if setting:
        setting.value = str(value)
    else:
        setting = Setting(key="incognito_level", value=str(value))
        db.add(setting)

def get_carousel_title(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "carousel_title").first()
    return setting.value if setting else ""

def set_carousel_title(db: Session, title: str):
    setting = db.query(Setting).filter(Setting.key == "carousel_title").first()
    if setting:
        setting.value = title
    else:
        setting = Setting(key="carousel_title", value=title)
        db.add(setting)

def save_upload(upload: Optional[UploadFile], subdir: str) -> Optional[str]:
    if not upload:
        return None
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if subdir == "uploads/emblems" and ext != ".svg":
        raise HTTPException(status_code=400, detail="Emblem muss SVG sein")
    target_dir = static_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{os.urandom(8).hex()}{ext}"
    out_path = target_dir / fname
    with out_path.open("wb") as f:
        f.write(upload.file.read())
    return f"{subdir}/{fname}"

def get_used_functions(db: Session) -> List[Function]:
    """
    Returns a list of Function objects that are actually used by helpers (as main or secondary functions),
    filtered by sort_order > 0, and sorted ascending by sort_order.
    """
    # Subquery for functions used as main functions
    main_subquery = db.query(Function.id).join(Helper, Helper.main_function_id == Function.id).subquery()

    # Subquery for functions used as secondary functions
    secondary_subquery = db.query(helper_secondary_functions.c.function_id).subquery()

    # Combine and filter
    used_function_ids = db.query(Function.id).filter(
        (Function.id.in_(main_subquery)) | (Function.id.in_(secondary_subquery))
    ).filter(Function.sort_order > 0).subquery()

    # Get the functions, sorted by sort_order ascending
    functions = db.query(Function).filter(Function.id.in_(used_function_ids)).order_by(Function.sort_order.asc()).all()

    return functions

# ---------- Public ----------
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(static_dir / "favicon.ico")

@app.get("/", response_class=HTMLResponse)
def public_index(request: Request, db: Session = Depends(get_db)):
    incognito_level = get_incognito_level(db)
    carousel_title = get_carousel_title(db) if incognito_level >= 2 else ""
    carousel_images = []
    if incognito_level >= 2:
        try:
            carousel_images = db.query(CarouselImage).order_by(CarouselImage.sort_order.asc()).all()
        except:
            carousel_images = []
    def build(parent_id=None, level=0):
        groups = db.query(Group).filter(Group.parent_id == parent_id).order_by(Group.sort_order.asc(), Group.name.asc()).all()
        result = []
        for g in groups:
            helpers = (
                db.query(Helper)
                .filter(Helper.group_id == g.id)
                .outerjoin(Helper.main_function)
                .order_by(Function.sort_order.asc(), Helper.last_name.asc(), Helper.first_name.asc())
                .all()
            )
            result.append({"group": g, "level": level, "helpers": helpers})
            result.extend(build(g.id, level+1))
        return result
    tree = build(None, 0)
    # Gruppen mit Detailseiten
    detail_groups = db.query(Group).filter(Group.detail_enabled == 1).order_by(Group.sort_order.asc()).all()
    allFunctionsInUse = get_used_functions(db)
    return templates.TemplateResponse("public_index.html", {"request": request, "tree": tree, "incognito_level": incognito_level, "carousel_title": carousel_title, "carousel_images": carousel_images, "detail_groups": detail_groups, "allFunctionsInUse": allFunctionsInUse})

@app.get("/group/{group_id}", response_class=HTMLResponse)
def group_detail(group_id: int, request: Request, db: Session = Depends(get_db)):
    group = db.query(Group).get(group_id)
    if not group or not group.detail_enabled:
        raise HTTPException(404)
    
    incognito_level = get_incognito_level(db)
    images = db.query(GroupImage).filter(GroupImage.group_id == group_id).order_by(GroupImage.sort_order.asc()).all()
    detail_groups = db.query(Group).filter(Group.detail_enabled == 1).order_by(Group.sort_order.asc()).all()
    
    helpers_query = (
        db.query(Helper)
        .join(Helper.main_function)
        .filter(Helper.group_id == group_id)
        .options(joinedload(Helper.main_function), joinedload(Helper.secondary_functions))
        .order_by(Function.sort_order.asc(), Helper.last_name.asc())
    )
    helpers = helpers_query.all()

    helpers_by_function = []
    if helpers:
        for key, group_helpers in itertools.groupby(helpers, key=lambda h: h.main_function):
            helpers_by_function.append((key, list(group_helpers)))

    return templates.TemplateResponse("group_detail.html", {"request": request, "group": group, "images": images, "detail_groups": detail_groups, "helpers_by_function": helpers_by_function,"incognito_level": incognito_level})

@app.get("/last_update")

@app.get("/last_update")
def get_last_update_endpoint(db: Session = Depends(get_db)):
    return {"timestamp": get_last_update(db).isoformat()}

# ---------- Admin Home ----------
@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db) ):
    counts = {
        'groups': db.query(Group).count(),
        'functions': db.query(Function).count(),
        'helpers': db.query(Helper).count(),
    }
    return templates.TemplateResponse("admin/index.html", {"request": request, "counts": counts, "version": __version__})

@app.get("/admin/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    incognito_level = get_incognito_level(db)
    carousel_title = get_carousel_title(db)
    carousel_images = []
    try:
        carousel_images = db.query(CarouselImage).order_by(CarouselImage.sort_order.asc()).all()
    except:
        carousel_images = []
    return templates.TemplateResponse("admin/settings.html", {"request": request, "incognito_level": incognito_level, "carousel_title": carousel_title, "carousel_images": carousel_images})

@app.post("/admin/settings/save")
async def settings_save(incognito_level: int = Form(0), carousel_title: str = Form(""), db: Session = Depends(get_db)):  #, _: bool = Depends(require_admin)
    set_incognito_level(db, incognito_level)
    set_carousel_title(db, carousel_title)
    set_last_update(db)
    db.commit()
    return RedirectResponse(url="/admin/settings", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/settings/upload_carousel")
async def upload_carousel(image: UploadFile = File(...), db: Session = Depends(get_db)):
    path = save_upload(image, "uploads/carousel")
    if path:
        max_sort = db.query(sa_func.max(CarouselImage.sort_order)).scalar() or 0
        carousel_img = CarouselImage(path=path, sort_order=max_sort + 10)
        db.add(carousel_img)
        set_last_update(db)
        db.commit()
    return RedirectResponse(url="/admin/settings", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/settings/delete_carousel/{img_id}")
async def delete_carousel(img_id: int, db: Session = Depends(get_db)):
    img = db.query(CarouselImage).get(img_id)
    if img:
        # Datei löschen
        try:
            p = static_dir / img.path
            if p.exists():
                p.unlink()
        except:
            pass
        db.delete(img)
        set_last_update(db)
        db.commit()
    return RedirectResponse(url="/admin/settings", status_code=HTTP_303_SEE_OTHER)

def restart_backend(backend_dir):
        import time
        time.sleep(2)
        os.execv(sys.executable, ['python'] + [str(backend_dir / "app" / "main.py")])   

def install_requirements(backend_dir="/backend", req_file="requirements.txt", timeout=None):
    backend_path = Path(backend_dir)
    req_path = backend_path / req_file

    if not req_path.exists():
        raise FileNotFoundError(f"Requirements-Datei nicht gefunden: {req_path}")

    print(f"Installiere Dependencies aus {req_path} …")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
            cwd=str(backend_path),          
            check=True,                     
            text=True,                      
            capture_output=True,            
            timeout=timeout                 
        )
        print(result.stdout)
        print("✅ Installation abgeschlossen.")
    except subprocess.CalledProcessError as e:
        print("❌ Installation fehlgeschlagen.")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        raise
    except subprocess.TimeoutExpired as e:
        print(f"⏱️ Timeout nach {timeout} Sekunden.")
        raise


@app.post("/admin/groups/{group_id}/upload_image")
async def upload_group_image(group_id: int, images: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    group = db.query(Group).get(group_id)
    if not group:
        raise HTTPException(404)
    
    max_sort = db.query(sa_func.max(GroupImage.sort_order)).filter(GroupImage.group_id == group_id).scalar() or 0
    
    for image in images:
        path = save_upload(image, f"uploads/groups/{group_id}")
        if path:
            max_sort += 10
            group_img = GroupImage(path=path, group_id=group_id, sort_order=max_sort)
            db.add(group_img)

    set_last_update(db)
    db.commit()
    return RedirectResponse(url=f"/admin/groups/{group_id}", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/groups/{group_id}/delete_image/{img_id}")
async def delete_group_image(group_id: int, img_id: int, db: Session = Depends(get_db)):
    img = db.query(GroupImage).filter(GroupImage.id == img_id, GroupImage.group_id == group_id).first()
    if img:
        # Datei löschen
        try:
            p = static_dir / img.path
            if p.exists():
                p.unlink()
        except:
            pass
        db.delete(img)
        set_last_update(db)
        db.commit()
    return RedirectResponse(url=f"/admin/groups/{group_id}", status_code=HTTP_303_SEE_OTHER)

# ---------- Groups CRUD ----------
@app.post("/admin/groups/import")
async def import_groups_from_csv(
    csv_file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    # _: bool = Depends(require_admin) # Temporarily disabled for testing
):
    if not csv_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    content = await csv_file.read()
    try:
        # We need to decode the content to a string to use io.StringIO
        content_as_string = content.decode('utf-8')
        # Skip the header
        reader = csv.reader(io.StringIO(content_as_string))
        header = next(reader)
        # Verify header
        if header != ['ID', 'Bezeichnung', 'parentId']:
             raise HTTPException(status_code=400, detail=f"Falscher Spaltenaufbau. Erwartet: ID,Bezeichnung,parentId. Gefunden: {','.join(header)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Lesen der CSV-Datei: {e}")

    groups_in_db = {g.id: g for g in db.query(Group).all()}

    for row in reader:
        try:
            group_id = int(row[0])
            name = row[1]
            parent_id_str = row[2]

            parent_id = int(parent_id_str) if parent_id_str and parent_id_str.isdigit() and int(parent_id_str) != 0 else None

            if group_id in groups_in_db:
                # Update existing group
                group = groups_in_db[group_id]
                group.name = name
                group.parent_id = parent_id
            else:
                # Create new group
                group = Group(id=group_id, name=name, parent_id=parent_id)
                db.add(group)

        except (ValueError, IndexError) as e:
            # Handle potential errors in row data
            # Maybe log this or add an error message to the UI
            print(f"Skipping row due to error: {row}, {e}")
            continue

    set_last_update(db)
    db.commit()

    return RedirectResponse(url="/admin/groups", status_code=HTTP_303_SEE_OTHER)

@app.get("/admin/groups", response_class=HTMLResponse)
def groups_list(request: Request, db: Session = Depends(get_db)):
    groups = db.query(Group).order_by(Group.parent_id.asc(), Group.sort_order.asc(), Group.name.asc()).all()
    return templates.TemplateResponse("admin/groups_list.html", {"request": request, "groups": groups})

@app.get("/admin/groups/new", response_class=HTMLResponse)
def group_new(request: Request, db: Session = Depends(get_db)):
    parents = db.query(Group).order_by(Group.sort_order.asc(), Group.name.asc()).all()
    return templates.TemplateResponse("admin/groups_form.html", {"request": request, "group": None, "parents": parents})

@app.get("/admin/groups/{group_id}", response_class=HTMLResponse)
def group_edit(group_id: int, request: Request, db: Session = Depends(get_db)):
    g = db.query(Group).get(group_id)
    if not g:
        raise HTTPException(404)
    parents = db.query(Group).filter(Group.id != group_id).order_by(Group.sort_order.asc(), Group.name.asc()).all()
    return templates.TemplateResponse("admin/groups_form.html", {"request": request, "group": g, "parents": parents})

@app.post("/admin/groups/save")
async def group_save(
    request: Request,
    id: Optional[int] = Form(None),
    name: str = Form(...),
    parent_id: Optional[str] = Form(None),
    sort_order: int = Form(0),
    detail_enabled: bool = Form(False),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    def _to_opt_int(v: Optional[str]) -> Optional[int]:
        if v is None: return None
        v = v.strip()
        if v in ("", "0"): return None
        try:
            return int(v)
        except Exception:
            return None
    pid = _to_opt_int(parent_id)

    if id:
        g = db.query(Group).get(id)
        if not g:
            raise HTTPException(404)
        g.name = name
        g.parent_id = pid
        g.sort_order = sort_order
        g.detail_enabled = detail_enabled
        g.description = description
    else:
        g = Group(name=name, parent_id=pid, sort_order=sort_order, detail_enabled=detail_enabled, description=description)
        db.add(g)
    
    set_last_update(db)
    db.commit()
    return RedirectResponse(url="/admin/groups", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/groups/{group_id}/delete")
async def group_delete(group_id: int, db: Session = Depends(get_db)):
    g = db.query(Group).get(group_id)
    if g:
        # Delete associated upload directory
        group_upload_dir = static_dir / "uploads" / "groups" / str(g.id)
        if group_upload_dir.exists() and group_upload_dir.is_dir():
            shutil.rmtree(group_upload_dir)

        db.delete(g)
        set_last_update(db)
        db.commit()

    return RedirectResponse(url="/admin/groups", status_code=HTTP_303_SEE_OTHER)


# ---------- Functions CRUD + Import ----------
@app.post("/admin/functions/import")
async def import_functions_from_csv(
    csv_file: UploadFile = File(...), 
    db: Session = Depends(get_db),
):
    if not csv_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    content = await csv_file.read()
    try:
        content_as_string = content.decode('utf-8')
        reader = csv.reader(io.StringIO(content_as_string))
        header = next(reader)
        if header != ['id', 'Bezeichnung']:
             raise HTTPException(status_code=400, detail=f"Falscher Spaltenaufbau. Erwartet: id,Bezeichnung. Gefunden: {','.join(header)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Lesen der CSV-Datei: {e}")

    functions_in_db = {f.id: f for f in db.query(Function).all()}

    for row in reader:
        try:
            func_id = int(row[0])
            name = row[1]

            if func_id in functions_in_db:
                # Update existing function
                func = functions_in_db[func_id]
                func.name = name
            else:
                # Create new function
                func = Function(id=func_id, name=name, legend_name=name, short_name=name)
                db.add(func)

        except (ValueError, IndexError) as e:
            print(f"Skipping row due to error: {row}, {e}")
            continue

    set_last_update(db)
    db.commit()

    return RedirectResponse(url="/admin/functions", status_code=HTTP_303_SEE_OTHER)

@app.get("/admin/functions", response_class=HTMLResponse)
def functions_list(request: Request, db: Session = Depends(get_db)):
    funcs = db.query(Function).order_by(Function.sort_order.asc(), Function.id.asc(), Function.name.asc()).all()
    return templates.TemplateResponse("admin/functions_list.html", {"request": request, "functions": funcs})

@app.get("/admin/functions/new", response_class=HTMLResponse)
def function_new(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/functions_form.html", {"request": request, "func": None})

@app.get("/admin/functions/{func_id}", response_class=HTMLResponse)
def function_edit(func_id: int, request: Request, db: Session = Depends(get_db)):
    f = db.query(Function).get(func_id)
    if not f:
        raise HTTPException(404)
    helpers = db.query(Helper).filter(
        or_(Helper.main_function_id == func_id,
            Helper.secondary_functions.any(Function.id == func_id))).all()
    return templates.TemplateResponse("admin/functions_form.html", {"request": request, "func": f, "helpers": helpers})

@app.post("/admin/functions/save")
async def function_save(
    id: Optional[int] = Form(None),
    name: str = Form(...),
    short_name: Optional[str] = Form(None),
    legend_name: Optional[str] = Form(None),
    sort_order: int = Form(0),
    delete_emblem: Optional[str] = Form(None),
    emblem: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    exists = db.execute(select(Function).where(Function.name == name)).scalar_one_or_none()
    if exists and (not id or exists.id != id):
        raise HTTPException(status_code=400, detail="Funktion mit diesem Namen existiert bereits")

    emblem_path = None

    if emblem and emblem.size > 0:
        if os.path.splitext(emblem.filename or "")[1].lower() != '.svg':
            raise HTTPException(status_code=400, detail="Emblem muss SVG sein")
        emblem_path = save_upload(emblem, "uploads/emblems")

    if id:
        f = db.query(Function).get(id)
        if not f: raise HTTPException(404)
        f.name = name
        f.short_name = short_name
        f.legend_name = legend_name
        f.sort_order = sort_order
        if emblem_path is not None:
            f.emblem_svg_path = emblem_path
        elif delete_emblem:
            f.emblem_svg_path = None
    else:
        max_sort = db.query(sa_func.max(Function.sort_order)).scalar() or 0
        sort_order = max_sort + 10
        f = Function(name=name, short_name=short_name, legend_name=legend_name, sort_order=sort_order, emblem_svg_path=emblem_path)
        db.add(f)
        
    set_last_update(db)
    db.commit()
    return RedirectResponse(url="/admin/functions", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/functions/{func_id}/delete")
async def function_delete(func_id: int, db: Session = Depends(get_db)):
    f = db.query(Function).get(func_id)
    if f:
        if f.emblem_svg_path:
            try:
                p = static_dir / f.emblem_svg_path
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        db.delete(f)
        
    set_last_update(db)
    db.commit()
    return RedirectResponse(url="/admin/functions", status_code=HTTP_303_SEE_OTHER)


# ---------- Helpers CRUD ----------
@app.post("/admin/helpers/import_csv")
async def import_helpers_from_csv(
    csv_file: UploadFile = File(...), 
    db: Session = Depends(get_db),
):
    if not csv_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    content = await csv_file.read()
    try:
        content_as_string = content.decode('utf-8')
        reader = csv.reader(io.StringIO(content_as_string))
        header = next(reader)
        expected_header = ['Vorname', 'Nachname', 'GruppenID', 'Hauptfunktion', 'Zusatzfunktion I', 'Zusatzfunktion II', 'Zusatzfunktion III']
        if header != expected_header:
             raise HTTPException(status_code=400, detail=f"Falscher Spaltenaufbau. Erwartet: {','.join(expected_header)}. Gefunden: {','.join(header)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Lesen der CSV-Datei: {e}")

    functions_map = {f.id for f in db.query(Function).all()}
    groups_map = {g.id for g in db.query(Group).all()}

    for row in reader:
        try:
            first_name, last_name, group_id_str, main_function_id, zusatz1_str, zusatz2_str, zusatz3_str = row
            group_id = int(group_id_str)
            main_function_id = int(main_function_id)
            zusatz1_id = int(zusatz1_str) if zusatz1_str.isdigit() else None
            zusatz2_id = int(zusatz2_str) if zusatz2_str.isdigit() else None
            zusatz3_id = int(zusatz3_str) if zusatz3_str.isdigit() else None
            
            if group_id not in groups_map:
                print(f"Skipping row: Group with ID {group_id} not found. Row: {row}")
                continue

            if main_function_id not in functions_map:
                print(f"Skipping row: Function with id '{main_function_id} ' not found. Row: {row}")
                continue

            if zusatz1_id and zusatz1_id not in functions_map:
                print(f"Skipping row: Function with id '{zusatz1_id}' not found. Row: {row}")
                continue

            if zusatz2_id and zusatz2_id not in functions_map:
                print(f"Skipping row: Function with id '{zusatz2_id}' not found. Row: {row}")
                continue

            if zusatz3_id and zusatz3_id not in functions_map:
                print(f"Skipping row: Function with id '{zusatz3_id}' not found. Row: {row}")
                continue

            if zusatz1_id or zusatz2_id or zusatz3_id:
                zusatzfunktionen = [z for z in [zusatz1_id, zusatz2_id, zusatz3_id] if z]
            else:
                zusatzfunktionen = []

            helper = db.query(Helper).filter(Helper.first_name == first_name, Helper.last_name == last_name).first()
            if not helper:
                helper = Helper(
                    first_name=first_name,
                    last_name=last_name,
                    group_id=group_id,
                    main_function_id=main_function_id
                )
                db.add(helper)
                db.flush()
            else:
                helper.group_id = group_id
                helper.main_function_id = main_function_id
            
            if zusatzfunktionen:
                secondary_functions = db.query(Function).filter(Function.id.in_(zusatzfunktionen)).all()
                helper.secondary_functions = secondary_functions
            else:
                helper.secondary_functions = []
            
            db.commit()
        except (ValueError, IndexError) as e:
            print(f"Skipping row due to error: {row}, {e}")
            continue

    set_last_update(db)
    db.commit()

    return RedirectResponse(url="/admin/helpers", status_code=HTTP_303_SEE_OTHER)

@app.get("/admin/helpers", response_class=HTMLResponse)
async def helpers_list(request: Request, db: Session = Depends(get_db)):
    helpers = db.query(Helper).order_by(Helper.last_name.asc(), Helper.first_name.asc()).all()
    return templates.TemplateResponse("admin/helpers_list.html", {"request": request, "helpers": helpers})

@app.get("/admin/helpers/new", response_class=HTMLResponse)
async def helper_new(request: Request, db: Session = Depends(get_db)):
    groups = db.query(Group).order_by(Group.sort_order.asc(), Group.name.asc()).all()
    functions = db.query(Function).order_by(Function.sort_order.asc(), Function.name.asc()).all()
    return templates.TemplateResponse("admin/helpers_form.html", {"request": request, "helper": None, "groups": groups, "functions": functions})

@app.get("/admin/helpers/{helper_id}", response_class=HTMLResponse)
async def helper_edit(helper_id: int, request: Request, db: Session = Depends(get_db)):
    h = db.query(Helper).get(helper_id)
    if not h: raise HTTPException(404)
    groups = db.query(Group).order_by(Group.sort_order.asc(), Group.name.asc()).all()
    functions = db.query(Function).order_by(Function.sort_order.asc(), Function.name.asc()).all()
    sec_ids = ",".join(str(f.id) for f in h.secondary_functions)
    return templates.TemplateResponse("admin/helpers_form.html", {"request": request, "helper": h, "groups": groups, "functions": functions, "sec_ids": sec_ids})

@app.post("/admin/helpers/save")
async def helper_save(id: Optional[int] = Form(None), first_name: str = Form(...), last_name: str = Form(...), group_id: int = Form(...), main_function_id: int = Form(...), secondary_function_ids: Optional[str] = Form(""), photo: Optional[UploadFile] = File(None), delete_photo: Optional[str] = Form(None), db: Session = Depends(get_db)):
    photo_path = save_upload(photo, "uploads/photos") if photo and photo.size > 0 else None
    if id:
        h = db.query(Helper).get(id)
        if not h: raise HTTPException(404)
        h.first_name = first_name
        h.last_name = last_name
        h.group_id = group_id
        h.main_function_id = main_function_id
        if delete_photo:
            try:
                if h.photo_path:
                    p = static_dir / h.photo_path
                    if p.exists(): p.unlink()
            except Exception:
                pass
            h.photo_path = None
        elif photo_path:
            if h.photo_path:
                try:
                    p = static_dir / h.photo_path
                    if p.exists(): p.unlink()
                except Exception:
                    pass
            h.photo_path = photo_path
    else:
        h = Helper(first_name=first_name, last_name=last_name, group_id=group_id, main_function_id=main_function_id, photo_path=photo_path)
        db.add(h)
        db.flush()
    sec_ids = [int(x) for x in (secondary_function_ids or "").split(",") if x.strip().isdigit()]
    if sec_ids:
        funcs = db.query(Function).filter(Function.id.in_(sec_ids)).all()
        h.secondary_functions = funcs
    else:
        h.secondary_functions = []
    
    set_last_update(db)
    db.commit()
    return RedirectResponse(url="/admin/helpers", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/helpers/{helper_id}/delete")
async def helper_delete(helper_id: int, db: Session = Depends(get_db)):
    h = db.query(Helper).get(helper_id)
    if h:
        if h.photo_path:
            try:
                p = static_dir / h.photo_path
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        db.delete(h)
        set_last_update(db)
        db.commit()
    return RedirectResponse(url="/admin/helpers", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/helpers/{helper_id}/delete_photo")
async def helper_delete_photo(helper_id: int, db: Session = Depends(get_db)):
    h = db.query(Helper).get(helper_id)
    if h and h.photo_path:
        try:
            p = static_dir / h.photo_path
            if p.exists():
                p.unlink()
        except Exception:
            pass
        h.photo_path = None
        set_last_update(db)
        db.commit()
    return RedirectResponse(url=f"/admin/helpers/{helper_id}", status_code=HTTP_303_SEE_OTHER)

@app.post("/admin/helpers/import_photos")
async def import_photos(zip_file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not zip_file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Nur ZIP-Dateien erlaubt")
    print("Starte Import Fotos aus ZIP …")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "photos.zip"
        
        print(f"Versuche zu entpacken: {zip_path}")
        print(f"Zielverzeichnis: {temp_dir}")

        try:
            with zip_path.open("wb") as f:
                f.write(await zip_file.read())
        except Exception as e:
            print(f"Fehler beim Entpacken: {e}")
                  
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                files = zip_ref.namelist()
                print(f"Dateien im ZIP: {len(files)} Stück")
                
                zip_ref.extractall(temp_dir)
                
            actual_files = os.listdir(temp_dir)
            print(f"Inhalt von {temp_dir} nach Entpacken: {actual_files}")
        except Exception as e:
            print(f"Fehler beim Entpacken: {e}")
        
        updated_count = 0
        for file_path in Path(temp_dir).rglob("*.jpg", case_sensitive=False):
            filename = file_path.name
            print(f"Verarbeite Bild: {filename}")
            if filename.lower().endswith('.jpg'):
                name_part = filename[:-4]
                parts = name_part.split(' ', 1)
                if len(parts) == 2:
                    last_name, first_name = parts
                    helper = db.query(Helper).filter(
                        Helper.last_name.ilike(last_name.strip()),
                        Helper.first_name.ilike(first_name.strip())
                    ).first()
                    if helper:
                        print(f"  Gefunden: {helper.first_name} {helper.last_name} (ID: {helper.id})")
                        photo_path = save_upload_from_path(file_path, "uploads/photos")
                        if helper.photo_path:
                            print(f"Lösche altes Foto: {helper.photo_path}")
                            try:
                                p = static_dir / helper.photo_path
                                if p.exists():
                                    p.unlink()
                            except Exception:
                                pass
                        if photo_path:
                            helper.photo_path = photo_path
                            updated_count += 1
                            print(f"Foto aktualisiert.")
        
        print(f"Import abgeschlossen. {updated_count} Fotos aktualisiert.")
        
        if updated_count > 0:
            set_last_update(db)
            db.commit()
    
    return RedirectResponse(url="/admin/helpers", status_code=HTTP_303_SEE_OTHER)

def save_upload_from_path(file_path: Path, subdir: str) -> Optional[str]:
    ext = file_path.suffix.lower()
    target_dir = static_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{os.urandom(8).hex()}{ext}"
    out_path = target_dir / fname
    import shutil
    shutil.copy(file_path, out_path)
    return f"{subdir}/{fname}"
