from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
import bcrypt as _bcrypt
import hashlib
import base64
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
import random

import models
import schemas

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret-key-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

AVATAR_COLORS = ["#6C63FF", "#FF6584", "#43BBAD", "#F5A623", "#4ECDC4", "#45B7D1", "#96CEB4", "#FF8B94"]

def _prepare_password(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(_prepare_password(password), _bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(_prepare_password(plain), hashed.encode("utf-8"))

def create_token(user: models.User) -> dict:
    role_val = user.role.value if hasattr(user.role, "value") else user.role
    payload = {
        "sub": str(user.id),
        "role": role_val,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

def get_current_user(token: str, db: Session) -> models.User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(401, "Invalid or expired token")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")

    return user

def require_role(user: models.User, roles: list):
    role_val = user.role.value if hasattr(user.role, "value") else user.role
    if role_val not in roles:
        raise HTTPException(403, f"Requires one of roles: {roles}")

def create_user(db: Session, data: schemas.UserCreate) -> models.User:
    hashed_password = hash_password(data.password)

    user = models.User(
        name=data.name,
        email=data.email,
        hashed_password=hashed_password,
        role=data.role,
        avatar_color=random.choice(AVATAR_COLORS)
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def delete_user(db: Session, user_id: int, admin_user: models.User):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    if user.id == admin_user.id:
        raise HTTPException(400, "Admins cannot delete themselves")
    
    projects = db.query(models.Project).filter(models.Project.owner_id == user.id).all()
    for p in projects:
        p.owner_id = admin_user.id
    
    db.delete(user)
    db.commit()

def update_user_pfp(db: Session, user_id: int, pfp_base64: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    user.profile_picture = pfp_base64
    db.commit()
    db.refresh(user)
    return user

def update_user_profile(db: Session, user_id: int, data: schemas.UserProfileUpdate):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    for k, v in data.dict(exclude_none=True).items():
        setattr(user, k, v)
        
    db.commit()
    db.refresh(user)
    return user

def create_project(db: Session, data: schemas.ProjectCreate, owner_id: int) -> models.Project:
    project = models.Project(**data.dict(), owner_id=owner_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    _set_task_count(project, db)
    return project

def get_projects(db: Session, user: models.User):
    role_val = user.role.value if hasattr(user.role, "value") else user.role

    if role_val == "admin":
        projects = db.query(models.Project).all()
    else:
        owned = db.query(models.Project).filter(models.Project.owner_id == user.id).all()
        member_ids = [p.id for p in user.member_projects]
        member_ps = db.query(models.Project).filter(models.Project.id.in_(member_ids)).all()
        seen = {p.id for p in owned}
        projects = owned + [p for p in member_ps if p.id not in seen]

    for p in projects:
        _set_task_count(p, db)

    return projects

def get_project(db: Session, project_id: int, user: models.User) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()

    if not project:
        raise HTTPException(404, "Project not found")

    _check_project_access(project, user)
    _set_task_count(project, db)

    return project

def update_project(db: Session, project_id: int, data: schemas.ProjectUpdate, user: models.User) -> models.Project:
    project = get_project(db, project_id, user)
    role_val = user.role.value if hasattr(user.role, "value") else user.role
    is_proj_member = any(m.id == user.id for m in project.members)
    is_owner = project.owner_id == user.id

    if role_val not in ["admin", "manager"] and not is_owner and not is_proj_member:
        raise HTTPException(403, "Not authorized to update project details")

    update_data = data.dict(exclude_none=True)

    if role_val == "member" and not (role_val in ["admin", "manager"] or is_owner):
        allowed = ["completion_percentage", "completion_image", "status"]
        for key in update_data.keys():
            if key not in allowed:
                raise HTTPException(403, f"Members cannot modify '{key}'")
        
        if update_data.get("status") == "completed":
            raise HTTPException(403, "Members cannot mark projects as 'completed'. Please submit for review.")

    if update_data.get("status") == "completed":
        if role_val not in ["admin", "manager"]:
            raise HTTPException(403, "Only Admin or Manager can mark projects as completed.")

    for k, v in update_data.items():
        setattr(project, k, v)

    db.commit()
    db.refresh(project)
    _set_task_count(project, db)

    return project

def delete_project(db: Session, project_id: int, user: models.User):
    project = get_project(db, project_id, user)
    role_val = user.role.value if hasattr(user.role, "value") else user.role

    if role_val not in ["admin"] and project.owner_id != user.id:
        raise HTTPException(403, "Only admin or owner can delete")

    db.delete(project)
    db.commit()

def add_member_to_project(db: Session, project_id: int, user_id: int, current_user: models.User):
    project = get_project(db, project_id, current_user)
    role_val = current_user.role.value if hasattr(current_user.role, "value") else current_user.role

    if role_val not in ["admin", "manager"] and project.owner_id != current_user.id:
        raise HTTPException(403, "Not authorized to add members")

    target = db.query(models.User).filter(models.User.id == user_id).first()

    if not target:
        raise HTTPException(404, "User not found")

    if target not in project.members:
        project.members.append(target)
        db.commit()
        db.refresh(project)

    _set_task_count(project, db)
    return project

def remove_member_from_project(db: Session, project_id: int, user_id: int, current_user: models.User):
    project = get_project(db, project_id, current_user)
    role_val = current_user.role.value if hasattr(current_user.role, "value") else current_user.role

    if role_val not in ["admin", "manager"] and project.owner_id != current_user.id:
        raise HTTPException(403, "Not authorized to remove members")

    target = db.query(models.User).filter(models.User.id == user_id).first()

    if target and target in project.members:
        project.members.remove(target)
        db.commit()
        db.refresh(project)

    _set_task_count(project, db)
    return project

def create_task(db: Session, project_id: int, data: schemas.TaskCreate, user: models.User) -> models.Task:
    project = get_project(db, project_id, user)
    task = models.Task(**data.dict(), project_id=project.id, created_by_id=user.id)

    db.add(task)
    db.commit()
    db.refresh(task)

    task.comment_count = 0
    return task

def get_tasks(db: Session, project_id: int, user: models.User):
    project = get_project(db, project_id, user)
    tasks = db.query(models.Task).filter(models.Task.project_id == project.id).all()

    for t in tasks:
        t.comment_count = db.query(func.count(models.Comment.id)).filter(models.Comment.task_id == t.id).scalar()

    return tasks

def get_task(db: Session, task_id: int, user: models.User) -> models.Task:
    task = db.query(models.Task).filter(models.Task.id == task_id).first()

    if not task:
        raise HTTPException(404, "Task not found")

    get_project(db, task.project_id, user)
    return task

def update_task(db: Session, task_id: int, data: schemas.TaskUpdate, user: models.User) -> models.Task:
    task = get_task(db, task_id, user)

    for k, v in data.dict(exclude_none=True).items():
        setattr(task, k, v)

    db.commit()
    db.refresh(task)

    task.comment_count = db.query(func.count(models.Comment.id)).filter(models.Comment.task_id == task.id).scalar()

    return task

def delete_task(db: Session, task_id: int, user: models.User):
    task = get_task(db, task_id, user)
    project = db.query(models.Project).filter(models.Project.id == task.project_id).first()

    role_val = user.role.value if hasattr(user.role, "value") else user.role

    if role_val not in ["admin", "manager"] and project.owner_id != user.id and task.created_by_id != user.id:
        raise HTTPException(403, "Not authorized to delete this task")

    db.delete(task)
    db.commit()

def create_comment(db: Session, task_id: int, data: schemas.CommentCreate, user: models.User) -> models.Comment:
    task = get_task(db, task_id, user)

    comment = models.Comment(
        content=data.content,
        task_id=task.id,
        author_id=user.id
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment

def get_comments(db: Session, task_id: int, user: models.User):
    task = get_task(db, task_id, user)
    return db.query(models.Comment).filter(models.Comment.task_id == task.id).all()

def get_dashboard_stats(db: Session, user: models.User) -> dict:
    role_val = user.role.value if hasattr(user.role, "value") else user.role

    if role_val == "admin":
        projects = db.query(models.Project).all()
    else:
        owned = db.query(models.Project).filter(models.Project.owner_id == user.id).all()
        member_ids = [p.id for p in user.member_projects]
        member_ps = db.query(models.Project).filter(models.Project.id.in_(member_ids)).all()
        seen = {p.id for p in owned}
        projects = owned + [p for p in member_ps if p.id not in seen]

    project_ids = [p.id for p in projects]

    tasks = db.query(models.Task).filter(models.Task.project_id.in_(project_ids)).all() if project_ids else []

    now = datetime.utcnow()
    
    dist = {"todo": 0, "in_progress": 0, "review": 0, "done": 0}
    for t in tasks:
        s = t.status.value if hasattr(t.status, "value") else str(t.status)
        if s in dist:
            dist[s] += 1

    project_dist = {"0-25%": 0, "26-50%": 0, "51-75%": 0, "76-100%": 0}
    for p in projects:
        pct = p.completion_percentage or 0
        if pct <= 25: project_dist["0-25%"] += 1
        elif pct <= 50: project_dist["26-50%"] += 1
        elif pct <= 75: project_dist["51-75%"] += 1
        else: project_dist["76-100%"] += 1

    all_completed_projects = db.query(models.Project).filter(models.Project.status == models.ProjectStatus.completed).all()
    
    if role_val == "admin":
        lifetime_completed = len(all_completed_projects)
    else:
        lifetime_completed = 0
        for p in all_completed_projects:
            if p.owner_id == user.id or any(m.id == user.id for m in p.members):
                lifetime_completed += 1

    return {
        "total_projects": len(projects),
        "active_projects": sum(1 for p in projects if (p.status.value if hasattr(p.status, "value") else p.status) == "active"),
        "total_tasks": len(tasks),
        "completed_tasks": dist["done"],
        "in_progress_tasks": dist["in_progress"],
        "overdue_tasks": sum(1 for t in tasks if t.due_date and t.due_date.replace(tzinfo=None) < now and (t.status.value if hasattr(t.status, "value") else t.status) != "done"),
        "total_members": db.query(func.count(models.User.id)).scalar(),
        "task_status_distribution": dist,
        "project_completion_distribution": project_dist,
        "lifetime_completed_projects": lifetime_completed
    }

def _check_project_access(project: models.Project, user: models.User):
    role_val = user.role.value if hasattr(user.role, "value") else user.role

    if role_val == "admin":
        return

    if project.owner_id == user.id:
        return

    member_ids = [m.id for m in project.members]

    if user.id in member_ids:
        return

    raise HTTPException(403, "Access denied to this project")

def _set_task_count(project: models.Project, db: Session):
    project.task_count = db.query(func.count(models.Task.id)).filter(
        models.Task.project_id == project.id
    ).scalar()