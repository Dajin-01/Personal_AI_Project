from fastapi.testclient import TestClient
from main import app

import os 
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import get_session
from unittest.mock import Mock, patch
from models import Base, Project
from contextlib import contextmanager

def test_health():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_project_name_is_rejected():
    with TestClient(app) as client:
        response = client.post("/projects", json={"name": ""})

    assert response.status_code == 422

def test_project_list_in_test_database():
    with database_test_client() as client:
        response = client.get("/projects")

        assert response.status_code == 200
        assert response.json() == []
    

def test_get_project_uses_provided_session():
    test_session = Mock(spec = Session)
    test_session.get.return_value = Project(id = 123456, name = "세션 연결 확인",)

    def override_get_session():
        return test_session

    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as client:
            response = client.get("/project/123456")
        
        assert response.status_code == 200
        assert response.json() == {"id": 123456, "name": "세션 연결 확인", "description" : None,}

    finally:
        app.dependency_overrides.pop(get_session, None)

def test_create_and_read_project():
    with database_test_client() as client:
        response = client.post("/projects", json = {"name": "자동 테스트 프로젝트", "description": "FastAPI 학습용 프로젝트"},)

        assert response.status_code == 201
        create_project = response.json()
        assert create_project["name"] == "자동 테스트 프로젝트"
        assert create_project["description"] == "FastAPI 학습용 프로젝트"

        project_id = create_project["id"]
        response = client.get(f"/project/{project_id}")

        assert response.status_code == 200
        assert response.json() == create_project

def test_update_and_delete_project():
    # 수정할 프로젝트 생성
    with database_test_client() as client:
        response = client.post(
            "/projects",
            json = {"name": "수정 전 이름"}
        )
        assert response.status_code == 201
        project_id = response.json()["id"]

        # 이름 수정
        
        response = client.patch(
            f"/project/{project_id}",
            json = {"name": "수정 후 이름"}
        )
        assert response.status_code == 200
        assert response.json() == {
            "id": project_id,
            "name": "수정 후 이름",
            "description" : None,
        }

        # 다시 조회해서 저장 여부 확인
        response = client.get(f'/project/{project_id}')
        assert response.status_code == 200
        assert response.json()["name"] == "수정 후 이름"

        # 프로젝트 삭제
        response = client.delete(f'/project/{project_id}')
        assert response.status_code == 200
        
        # 삭제한 프로젝트 조회
        response = client.get(f'/project/{project_id}')
        assert response.status_code == 404

        #  이미 삭제한 프로젝트 다시 삭제 시도 
        response = client.delete(f'/project/{project_id}')
        assert response.status_code == 404

def test_update_project_description():
    with database_test_client() as client:
        response = client.post(
            "/projects",
            json = {"name": "설명 테스트", "description": "기존 설명"}
        )
        assert response.status_code == 201
        project_id = response.json()["id"]
        url = f"/project/{project_id}"

        # 설명 수정
        response = client.patch(
            url,
            json = {"name": "설명 테스트", "description": "새 설명"}
        )
        assert response.status_code == 200
        assert response.json()["description"] == "새 설명"

        # 설명을 생략하면 기존 설명 유지
        response = client.patch(
            url,
            json = {"name": "이름만 수정"}
        )
        assert response.status_code ==200
        assert response.json()["description"] == "새 설명"

        # None을 보내면 설명 삭제

        response = client.patch(
            url,
            json = {"name": "이름만 수정", "description" : None}
        )
        assert response.status_code == 200
        assert response.json()["description"] is None

        # 다시 조회하여 저장 결과 확인
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()["description"] is None

@contextmanager
def database_test_client():
    test_engine = create_engine(os.environ["TEST_DATABASE_URL"])

    if test_engine.url.database != "knowledge_test":
        raise RuntimeError("Test database is not set to knowledge_test")
    
    try:
        Base.metadata.create_all(test_engine)

        with test_engine.connect() as connection:
            transaction = connection.begin()

            def override_get_session():
                with Session(
                    bind = connection,
                    join_transaction_mode = "create_savepoint",
                ) as session:
                    yield session
            
            app.dependency_overrides[get_session] = override_get_session

            try:
                with TestClient(app) as client:
                    yield client
            finally:
                app.dependency_overrides.pop(get_session, None)
                transaction.rollback()
    finally:
        test_engine.dispose()


def test_create_document():
    with database_test_client() as client:
        response = client.post("/projects", json = {"name": "문서 테스트"})
        assert response.status_code == 201
        project_id = response.json()["id"]


        response = client.post(
            f"/projects/{project_id}/documents",
            json = {
                "title": "FASTAPI 학습",
                "content": "FASTAPI로 문서 저장 API를 만들었습니다."
            },
        )

        assert response.status_code == 201
        document = response.json()
        assert isinstance(document["id"], int)
        assert document["project_id"] == project_id
        assert document["title"] == "FASTAPI 학습"
        assert document["content"] == "FASTAPI로 문서 저장 API를 만들었습니다."

        response = client.get(f"/projects/{project_id}/documents")
        assert response.status_code == 200
        assert response.json() == [document]

        response = client.post(
            "/projects",
            json = {"name": "문서 없는 프로젝트"}
        )

        assert response.status_code == 201
        other_project_id = response.json()["id"]

        response = client.get(f"/projects/{other_project_id}/documents")
        assert response.status_code == 200
        assert response.json() == []

        document_id = document["id"]

        # 문서 하나 조회
        response = client.get(f"/projects/{project_id}/documents/{document_id}")
        assert response.status_code == 200
        assert response.json() == document

        # 다른 프로젝트 주소로 같은 문서를 요청하면 실패 
        response = client.get(f"/projects/{other_project_id}/documents/{document_id}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}

        # 존재하지 않는 문서를 검색하면 실패 
        response = client.get(f"/projects/{project_id}/documents/0")
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}

def test_create_document_requires_existing_project():
    with database_test_client() as client:
        response = client.post(
            "/projects/99999/documents",
            json = {"title": "테스트 문서", "content": "테스트 원문"}
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found"}

def test_list_documents_requires_existing_project():
    with database_test_client() as client:
        response = client.get("/projects/99999/documents")

        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found"}


def test_deleting_project_also_deletes_documents():
    with database_test_client() as client:
        # 프로젝트 생성
        response = client.post("/projects", json = {"name": "연관 삭제 테스트"})

        assert response.status_code == 201
        project_id = response.json()["id"]

        # 프로젝트에 문서 생성
        response = client.post(f"/projects/{project_id}/documents", json = {"title": "테스트 문서", "content": "테스트 본문"},)
        assert response.status_code == 201
        document_id = response.json()["id"]

        # 프로젝트 삭제
        response = client.delete(f"/project/{project_id}")
        assert response.status_code == 200

        # 소속 문서가 삭제되었는지 확인
        response = client.get(f"/projects/{project_id}/documents/{document_id}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}


def test_summarize_document():
    with database_test_client() as client:
        response = client.post(
            "/projects",
            json={"name": "요약 테스트"},
        )
        assert response.status_code == 201
        project_id = response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/documents",
            json={"title": "테스트 문서", "content": "테스트 본문"},
        )
        assert response.status_code == 201
        document_id = response.json()["id"]
        url = f"/projects/{project_id}/documents/{document_id}/summary"

        with patch("main.summarize_text", return_value="테스트 요약") as fake:
            # 정상 요약
            response = client.post(url)
            assert response.status_code == 200
            assert response.json() == {
                "document_id": document_id,
                "summary": "테스트 요약",
            }
            fake.assert_called_once_with("테스트 본문")

            # 다시 조회하여 요약이 저장됐는지 확인
            response = client.get(f"/projects/{project_id}/documents/{document_id}")
            assert response.status_code == 200
            assert response.json()['summary'] == "테스트 요약"

            # 요약 실패
            fake.side_effect = RuntimeError("요약 실패")
            response = client.post(url)
            assert response.status_code == 502
            assert response.json() == {"detail": "Document summary failed"}

            # 재요약에 실패해도 기존 요약 유지
            response = client.get(f"/projects/{project_id}/documents/{document_id}")
            assert response.status_code == 200
            assert response.json()['summary'] == "테스트 요약"

            # 존재하지 않는 문서
            response = client.post(
                f"/projects/{project_id}/documents/0/summary"
            )
            assert response.status_code == 404

            # 다른 프로젝트의 주소로 요청
            response = client.post(
                f"/projects/0/documents/{document_id}/summary"
            )
            assert response.status_code == 404


def test_create_summary_job():
    from kombu.exceptions import OperationalError

    with database_test_client() as client:
        response = client.post("/projects", json = {"name": "작업 접수 테스트"})
        assert response.status_code == 201
        project_id = response.json()["id"]

        response = client.post(f"/projects/{project_id}/documents", json = {"title":"테스트 문서","content":"테스트 본문"},)
        assert response.status_code == 201
        document_id = response.json()["id"]

        url = f'/projects/{project_id}/documents/{document_id}/summary-jobs'

        with patch("main.summarize_document_task.delay") as fake_delay:
            fake_delay.return_value = Mock(id="test-job-123")

            response = client.post(url)

            assert response.status_code == 202
            assert response.json() == {"task_id":"test-job-123"}
            fake_delay.assert_called_once_with(project_id, document_id)

            fake_delay.reset_mock()

            response = client.post(f"/projects/0/documents/{document_id}/summary-jobs")
            assert response.status_code == 404
            fake_delay.assert_not_called()

            fake_delay.side_effect = OperationalError("Redis unavailable")
            response = client.post(url)
            assert response.status_code == 503

def test_get_summary_job():
    from redis.exceptions import RedisError

    task_id = "344593cd-903c-44a2-931a-395117153ca8"
    url = f'/summary-jobs/{task_id}'

    with patch("main.celery_app.AsyncResult") as fake_result:
        with TestClient(app) as client:
            for state in ("PENDING", "SUCCESS", "FAILURE"):
                fake_result.return_value.state = state

                response = client.get(url)

                assert response.status_code == 200
                assert response.json() == {
                    "task_id": task_id,
                    "state": state,
                }
                fake_result.assert_called_with(task_id)
            fake_result.side_effect = None
            del fake_result.return_value.state

            # 상태를 읽는 순간 Redis 연결 오류가 발생하는 상황
            from unittest.mock import PropertyMock

            type(fake_result.return_value).state = PropertyMock(
                side_effect=RedisError("Redis unavailable")
            )

            response = client.get(url)
            assert response.status_code == 503