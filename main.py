from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

import hashlib

# ---------------- APP ----------------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")

# ---------------- TEMPLATES & STATIC ----------------
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- DATABASE ----------------
engine = create_engine(
    "sqlite:///studyplanner.db",
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ---------------- MODELS ----------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    status = Column(String, default="Pending")
    user_id = Column(Integer)

Base.metadata.create_all(bind=engine)

# ---------------- HELPERS ----------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def task_to_dict(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status
    }

def get_current_user(request: Request):
    return request.session.get("user_id")

# ---------------- AUTH ROUTES ----------------

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None}
    )

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()

    if not user or user.password != hash_password(password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid username or password"}
        )

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return RedirectResponse("/", status_code=302)

@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error": None}
    )

@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    existing = db.query(User).filter(User.username == username).first()

    if existing:
        db.close()
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Username already taken"}
        )

    new_user = User(username=username, password=hash_password(password))
    db.add(new_user)
    db.commit()
    db.close()
    return RedirectResponse("/login", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

# ---------------- TASK ROUTES ----------------

@app.get("/")
def home(request: Request):
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    db = SessionLocal()
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    db.close()
    task_list = [task_to_dict(t) for t in tasks]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "tasks": task_list,
            "username": request.session.get("username")
        }
    )

@app.get("/add")
def add_page(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="add_task.html",
        context={}
    )

@app.post("/add")
def add_task(request: Request, title: str = Form(...), description: str = Form(...)):
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    db = SessionLocal()
    task = Task(title=title, description=description, status="Pending", user_id=user_id)
    db.add(task)
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=302)

@app.get("/delete/{task_id}")
def delete_task(request: Request, task_id: int):
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if task:
        db.delete(task)
        db.commit()
    db.close()
    return RedirectResponse("/", status_code=302)

@app.get("/done/{task_id}")
def mark_done(request: Request, task_id: int):
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if task:
        task.status = "Completed"
        db.commit()
    db.close()
    return RedirectResponse("/", status_code=302)