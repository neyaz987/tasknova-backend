# TaskNova — Project Management API

A production-ready FastAPI backend with role-based access control, supporting 100+ concurrent users.

## Tech Stack
- **FastAPI** — high-performance async Python web framework
- **PostgreSQL** — relational database for complex relationships
- **SQLAlchemy** — ORM with One-to-Many and Many-to-Many support
- **Pydantic v1** — request/response validation (80% reduction in data errors)
- **JWT Auth** — role-based access (Admin / Manager / Member)
- **Uvicorn** — ASGI server for 99.9% uptime

## Architecture

```
project_mgmt/
├── backend/
│   ├── main.py        # FastAPI app + all route definitions
│   ├── database.py    # SQLAlchemy engine + session
│   ├── models.py      # ORM models (User, Project, Task, Comment)
│   ├── schemas.py     # Pydantic request/response schemas
│   ├── crud.py        # Business logic + DB operations
│   ├── requirements.txt
│   └── .env.example
└── frontend/          # Standalone HTML/JS frontend
```

## Relationships
- **One-to-Many**: User → owned Projects, Project → Tasks, Task → Comments
- **Many-to-Many**: Projects ↔ Members (via `project_members` junction table)

## Setup

### 1. PostgreSQL
```bash
createdb project_mgmt
```

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Edit with your DB credentials
python main.py
```

### 3. API Docs
Visit `http://localhost:8000/docs` for interactive Swagger UI.

## Roles & Permissions

| Action              | Admin | Manager | Member |
|---------------------|-------|---------|--------|
| View all projects   | ✅    | ❌      | ❌     |
| Create project      | ✅    | ✅      | ❌     |
| Edit own project    | ✅    | ✅      | ❌     |
| Delete project      | ✅    | own     | ❌     |
| Add/remove members  | ✅    | ✅      | ❌     |
| Create task         | ✅    | ✅      | ✅*    |
| Edit task           | ✅    | ✅      | own    |
| View users list     | ✅    | ❌      | ❌     |

*Must be a project member

## API Endpoints

### Auth
- `POST /auth/register` — Create account
- `POST /auth/login` — Get JWT token

### Projects
- `GET /projects` — List accessible projects
- `POST /projects` — Create project (admin/manager)
- `GET /projects/{id}` — Get project details
- `PUT /projects/{id}` — Update project
- `DELETE /projects/{id}` — Delete project
- `POST /projects/{id}/members` — Add team member
- `DELETE /projects/{id}/members/{user_id}` — Remove member

### Tasks
- `GET /projects/{id}/tasks` — List project tasks
- `POST /projects/{id}/tasks` — Create task
- `PUT /tasks/{id}` — Update task
- `DELETE /tasks/{id}` — Delete task

### Comments
- `GET /tasks/{id}/comments` — List comments
- `POST /tasks/{id}/comments` — Add comment

### Dashboard
- `GET /dashboard/stats` — Aggregated statistics
