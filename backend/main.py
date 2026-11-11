from fastapi import Depends, FastAPI, Query, HTTPException, Response
from pydantic import BaseModel, ConfigDict,Field 
from sqlalchemy import String, ForeignKey
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database import engine, get_session
from models import Document, Project
from ai import summarize_text
from openai import APIError
from kombu.exceptions import OperationalError
from tasks import summarize_document_task, celery_app
from redis.exceptions import RedisError
from uuid import UUID

app = FastAPI()

class ProjectCreate(BaseModel):
    name: str = Field(min_length = 1, max_length = 100)
    description: str | None = Field(default = None, max_length = 1000)

class ProjectUpdate(BaseModel):
    name: str = Field(min_length = 1, max_length = 100)
    description: str | None = Field(default = None, max_length = 1000)

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes = True)
    id: int
    name: str
    description: str | None

class DocumentCreate(BaseModel):
    title : str = Field(min_length = 1, max_length = 200)
    content: str = Field(min_length = 1)

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes = True)
    id: int 
    project_id: int
    title: str
    content: str
    summary: str | None

class DocumentSummaryResponse(BaseModel):
    document_id : int
    summary : str

class SummaryJobResponse(BaseModel):
    task_id: str

class SummaryJobStatusResponse(BaseModel):
    task_id: str
    state: str


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/projects", status_code = 201)
def create_project(project: ProjectCreate, session: Session = Depends(get_session),):
    db_project = Project(name = project.name, description = project.description,)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)

    return {"id": db_project.id, "name": db_project.name, "description": db_project.description,}

@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"status": "ok", "database": "connected"}


@app.get("/projects", response_model =list[ProjectResponse])
def list_projects(
    limit: int = Query(default = 20, ge = 1, le = 100),
    offset: int = Query(default = 0, ge = 0),
    session: Session = Depends(get_session),
): 
    statement = (
        select(Project)
        .order_by(Project.id)
        .limit(limit)
        .offset(offset)
    )

    return session.scalars(statement).all()


@app.get("/project/{project_id}", response_model = ProjectResponse)
def get_project(project_id: int, session: Session = Depends(get_session),):
    project = session.get(Project, project_id)

    if project is None:
        raise HTTPException(status_code = 404, detail = "Project not found")
        
    return project

@app.patch("/project/{project_id}", response_model = ProjectResponse)
def update_project(project_id: int, project_data: ProjectUpdate, session: Session = Depends(get_session),):
    project = session.get(Project, project_id)

    if project is None:
        raise HTTPException(status_code = 404, detail = "Project not found")

    project.name = project_data.name
    updates = project_data.model_dump(exclude_unset = True)
    if "description" in updates:
        project.description = updates["description"]
    session.commit()
    session.refresh(project)

    return project

@app.delete("/project/{project_id}", status_code = 200)
def delete_project(project_id: int, session: Session = Depends(get_session),):
    project = session.get(Project, project_id)

    if project is None:
        raise HTTPException(status_code = 404, detail = "Project not found")
        
    session.delete(project)
    session.commit()

    return Response(status_code = 200, content = "The project has been deleted successfully has been deleted successfully.", media_type = "text/plain")


@app.post("/projects/{project_id}/documents", status_code = 201, response_model = DocumentResponse,)
def create_document(project_id: int, document_data: DocumentCreate, session:Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code = 404, detail = "Project not found")
    
    document = Document(project_id = project_id, title = document_data.title, content = document_data.content,)
    session.add(document)
    session.commit()
    session.refresh(document)

    return document

@app.get("/projects/{project_id}/documents", response_model = list[DocumentResponse],)
def list_documents(project_id: int,limit: int = Query(default = 20, ge = 1, le = 100), offset: int = Query(default = 0, ge = 0),session: Session = Depends(get_session),):
    project = session.get(Project, project_id)

    if project is None:
        raise HTTPException(status_code = 404, detail = "Project not found")
    
    statement = (
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.id)
        .limit(limit)
        .offset(offset)
    )
    return session.scalars(statement).all()

@app.get("/projects/{project_id}/documents/{document_id}", response_model = DocumentResponse)
def get_document(project_id: int, document_id: int, session: Session = Depends(get_session),):
    document = session.get(Document, document_id)

    if document is None or document.project_id != project_id:
        raise HTTPException(status_code = 404, detail = "Document not found")

    return document

@app.post("/projects/{project_id}/documents/{document_id}/summary", response_model = DocumentSummaryResponse,)
def summarize_document(project_id: int, document_id: int, session:Session = Depends(get_session),):
    document = session.get(Document, document_id)

    if document is None or document.project_id != project_id:
        raise HTTPException(status_code = 404, detail = "Document not found")

    try:
        summary = summarize_text(document.content)
    except (APIError, RuntimeError) as exec:
        raise HTTPException(
            status_code = 502,
            detail = "Document summary failed",
        ) from exec

    document.summary = summary
    session.commit()
    session.refresh(document)
    return {"document_id": document.id, "summary": document.summary}

@app.post("/projects/{project_id}/documents/{document_id}/summary-jobs", status_code = 202, response_model = SummaryJobResponse,)
def create_summary_job(project_id: int, document_id: int, session:Session = Depends(get_session)):
    document = session.get(Document, document_id)

    if document is None or document.project_id != project_id:
        raise HTTPException(status_code = 404, detail = "Document not found")

    try:
        job = summarize_document_task.delay(project_id, document_id)
    except OperationalError as exc:
        raise HTTPException(status_code = 503, detail = "Summarize queue unavailable",) from exc

    return {"task_id":job.id}


@app.get("/summary-jobs/{task_id}", response_model=SummaryJobStatusResponse)
def get_summary_job(task_id: UUID):
    job = celery_app.AsyncResult(str(task_id))

    try:
        state = job.state
    except RedisError as exc:
        raise HTTPException(status_code = 503, detail = "Summary result store unavailable") from exc
    return {"task_id": str(task_id), "state":state}
