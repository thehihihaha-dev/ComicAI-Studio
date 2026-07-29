from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.projects import ProjectCreate
from app.database import SessionLocal
from app.models.project import Project
projects = []
router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


@router.get("/")
def get_projects():
    db = SessionLocal()
    db_projects = db.query(Project).all()
    db.close()
    return {
        "message": "ComicAI Studio Project API",
        "projects": db_projects,
    }
@router.post("/")
def create_project(project: ProjectCreate):
    new_project = Project(
    id=str(uuid4()),
    name=project.name,
    content_type=project.content_type,
    status="created",
    created_at=datetime.now(timezone.utc),
)
    db = SessionLocal()
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    db.close()

    return new_project
@router.get("/{project_id}")
def get_project(project_id: str):
    db = SessionLocal()

    project = db.query(Project).filter(Project.id == project_id).first()

    db.close()

    return project