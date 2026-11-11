import os 

from celery import Celery
from sqlalchemy.orm import Session

from ai import summarize_text
from database import engine
from models import Document

celery_app = Celery(
    "tasks",
    broker = os.environ["CELERY_BROKER_URL"],
    backend = os.environ["CELERY_RESULT_BACKEND"]
)

@celery_app.task
def add(x: int, y:int) ->int:
    return x + y

@celery_app.task 
def summarize_document_task(project_id: int, document_id: int) -> dict:
    with Session(engine) as session:
        document = session.get(Document, document_id)

        if document is None or document.project_id != project_id:
            raise ValueError("Document not found")
        summary = summarize_text(document.content)
        document.summary = summary
        session.commit()

    return {"document_id": document_id, "summary": summary}

