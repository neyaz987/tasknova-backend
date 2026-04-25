from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    member = "member"

class ProjectStatus(str, Enum):
    active = "active"
    completed = "completed"
    on_hold = "on_hold"
    archived = "archived"
    review = "review"

class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    review = "review"
    done = "done"

class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.member

    @validator("name")
    def name_must_not_be_blank(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be blank")
        return v.strip()

    @validator("password")
    def password_strength(cls, v):
        if len(v.encode("utf-8")) > 1024:
            raise ValueError("Password is too long (max 1024 bytes)")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserPfpUpdate(BaseModel):
    profile_picture: str

class UserProfileUpdate(BaseModel):
    bio: Optional[str] = None
    personal_notes: Optional[str] = None
    extra_data: Optional[str] = None

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    avatar_color: str
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    personal_notes: Optional[str] = None
    extra_data: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.active
    deadline: Optional[datetime] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    deadline: Optional[datetime] = None
    completion_percentage: Optional[int] = None
    completion_image: Optional[str] = None

class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: ProjectStatus
    deadline: Optional[datetime]
    owner: UserOut
    members: List[UserOut] = []
    task_count: Optional[int] = 0
    completion_percentage: int
    completion_image: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

    @validator("task_count", pre=True, always=True)
    def compute_task_count(cls, v, values):
        return v or 0

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    due_date: Optional[datetime] = None
    assignee_id: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=300)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    assignee_id: Optional[int] = None

class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[datetime]
    project_id: int
    assignee: Optional[UserOut]
    created_by: Optional[UserOut]
    comment_count: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentOut(BaseModel):
    id: int
    content: str
    task_id: Optional[int]
    project_id: Optional[int]
    author: UserOut
    created_at: datetime

    class Config:
        from_attributes = True

class TeamMemberAdd(BaseModel):
    user_id: int

class DashboardStats(BaseModel):
    total_projects: int
    active_projects: int
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    total_members: int
    task_status_distribution: dict
    project_completion_distribution: dict
    lifetime_completed_projects: int
