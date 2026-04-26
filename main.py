from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
import uvicorn

from database import get_db, engine
from models import Base
import models
from schemas import (
    UserCreate, UserOut, UserLogin, TokenResponse,
    ProjectCreate, ProjectOut, ProjectUpdate,
    TaskCreate, TaskOut, TaskUpdate,
    CommentCreate, CommentOut,
    TeamMemberAdd, DashboardStats, UserPfpUpdate
)
import schemas
from crud import (
    create_user, get_user_by_email, authenticate_user, create_token,
    get_current_user, require_role,
    create_project, get_projects, get_project, update_project, delete_project,
    add_member_to_project, remove_member_from_project,
    create_task, get_tasks, get_task, update_task, delete_task,
    create_comment, get_comments,
    get_dashboard_stats
)
from fastapi.staticfiles import StaticFiles
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TaskNova — Project Management API",
    description="Modern role-based project management system with full CRUD operations",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


@app.post("/auth/register", response_model=UserOut, status_code=201, tags=["Auth"])
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, user_data.email):
        raise HTTPException(400, "Email already registered")
    return create_user(db, user_data)

@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    return create_token(user)


@app.get("/users/me", response_model=UserOut, tags=["Users"])
def get_me(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    return get_current_user(credentials.credentials, db)

@app.get("/users", response_model=List[UserOut], tags=["Users"])
def list_users(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    require_role(current, ["admin"])
    return db.query(models.User).order_by(models.User.id.desc()).all()

@app.delete("/users/{user_id}", status_code=204, tags=["Users"])
def remove_user(user_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    require_role(current, ["admin"])
    from crud import delete_user
    delete_user(db, user_id, current)

@app.put("/users/me/pfp", response_model=UserOut, tags=["Users"])
def update_pfp(data: schemas.UserPfpUpdate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    from crud import update_user_pfp
    return update_user_pfp(db, current.id, data.profile_picture)

@app.put("/users/me/profile", response_model=UserOut, tags=["Users"])
def update_profile(data: schemas.UserProfileUpdate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    from crud import update_user_profile
    return update_user_profile(db, current.id, data)


@app.post("/projects", response_model=ProjectOut, status_code=201, tags=["Projects"])
def new_project(data: ProjectCreate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    require_role(current, ["admin", "manager"])
    return create_project(db, data, current.id)

@app.get("/projects", response_model=List[ProjectOut], tags=["Projects"])
def list_projects(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return get_projects(db, current)

@app.get("/projects/{project_id}", response_model=ProjectOut, tags=["Projects"])
def read_project(project_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return get_project(db, project_id, current)

@app.put("/projects/{project_id}", response_model=ProjectOut, tags=["Projects"])
def edit_project(project_id: int, data: ProjectUpdate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return update_project(db, project_id, data, current)

@app.delete("/projects/{project_id}", status_code=204, tags=["Projects"])
def remove_project(project_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    require_role(current, ["admin", "manager"])
    delete_project(db, project_id, current)

@app.post("/projects/{project_id}/members", response_model=ProjectOut, tags=["Projects"])
def add_member(project_id: int, data: TeamMemberAdd, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return add_member_to_project(db, project_id, data.user_id, current)

@app.delete("/projects/{project_id}/members/{user_id}", response_model=ProjectOut, tags=["Projects"])
def remove_member(project_id: int, user_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return remove_member_from_project(db, project_id, user_id, current)


@app.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=201, tags=["Tasks"])
def new_task(project_id: int, data: TaskCreate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    require_role(current, ["admin", "manager"])
    return create_task(db, project_id, data, current)

@app.get("/projects/{project_id}/tasks", response_model=List[TaskOut], tags=["Tasks"])
def list_tasks(project_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return get_tasks(db, project_id, current)

@app.put("/tasks/{task_id}", response_model=TaskOut, tags=["Tasks"])
def edit_task(task_id: int, data: TaskUpdate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return update_task(db, task_id, data, current)

@app.delete("/tasks/{task_id}", status_code=204, tags=["Tasks"])
def remove_task(task_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    delete_task(db, task_id, current)


@app.post("/tasks/{task_id}/comments", response_model=CommentOut, status_code=201, tags=["Comments"])
def new_task_comment(task_id: int, data: CommentCreate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return create_task_comment(db, task_id, data, current)

@app.get("/tasks/{task_id}/comments", response_model=List[CommentOut], tags=["Comments"])
def list_task_comments(task_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return get_task_comments(db, task_id, current) if "get_task_comments" in globals() else get_comments(db, task_id, current)

@app.post("/projects/{project_id}/comments", response_model=CommentOut, status_code=201, tags=["Comments"])
def new_project_comment(project_id: int, data: CommentCreate, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return create_project_comment(db, project_id, data, current)

@app.get("/projects/{project_id}/comments", response_model=List[CommentOut], tags=["Comments"])
def list_project_comments(project_id: int, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return get_project_comments(db, project_id, current)


@app.get("/dashboard/stats", response_model=DashboardStats, tags=["Dashboard"])
def dashboard(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    current = get_current_user(credentials.credentials, db)
    return get_dashboard_stats(db, current)
app.mount("/", StaticFiles(directory=".", html=True), name="static")