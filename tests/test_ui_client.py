"""Offline HTTP-client and Streamlit presentation tests for S05."""

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from ui.api_client import ApiClient, ApiError, UploadInput
from ui.presentation import (
    current_run_id, findings_with_snapshot, remember_run, technical_progress,
    upload_message, visible_results,
)

APP_PATH = Path(__file__).resolve().parents[1] / "ui" / "app.py"


def test_http_client_vacancy_and_criterion_crud() -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"id": 7, **(body or {})})

    with ApiClient(transport=httpx.MockTransport(respond)) as api:
        assert api.list_vacancies() == []
        assert api.create_vacancy("Аналитик", "Роль")["title"] == "Аналитик"
        assert api.update_vacancy(7, "Ведущий аналитик", "Роль")["title"] == "Ведущий аналитик"
        assert api.list_criteria(7) == []
        assert api.create_criterion(7, "Python", "required", True)["priority"] == "required"
        assert api.update_criterion(9, description="SQL", priority="preferred",
                                    active=False, display_order=2)["display_order"] == 2
        assert api.delete_criterion(9) is None
    assert [(method, path) for method, path, _ in calls] == [
        ("GET", "/vacancies"), ("POST", "/vacancies"), ("PATCH", "/vacancies/7"),
        ("GET", "/vacancies/7/criteria"), ("POST", "/vacancies/7/criteria"),
        ("PATCH", "/criteria/9"), ("DELETE", "/criteria/9"),
    ]
    assert calls[5][2] == {"description": "SQL", "priority": "preferred",
                           "active": False, "display_order": 2}


def test_http_client_multipart_upload_and_run_reads() -> None:
    seen: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.url.path.endswith("/resumes") and request.method == "POST":
            assert "multipart/form-data" in request.headers["content-type"]
            assert b'filename="one.pdf"' in request.content
            assert b'filename="two.docx"' in request.content
            assert b"synthetic-pdf" in request.content
            return httpx.Response(200, json={"results": [
                {"filename": "one.pdf", "status": "ready", "duplicate": True, "error": None},
                {"filename": "two.docx", "status": "parse_error", "duplicate": False, "error": "invalid_docx"},
            ]})
        if request.url.path.endswith("/resumes"):
            return httpx.Response(200, json=[])
        if request.url.path == "/resumes/5":
            return httpx.Response(200, json={"id": 5, "extracted_text": "synthetic text"})
        if request.method == "POST":
            return httpx.Response(202, json={"id": 11, "vacancy_id": 7, "status": "pending"})
        if request.url.path.endswith("/results"):
            return httpx.Response(200, json={"run_id": 11, "results": []})
        return httpx.Response(200, json={"id": 11, "vacancy_id": 7, "status": "running",
                                         "total": 2, "pending": 1, "running": 1,
                                         "completed": 0, "failed": 0, "interrupted": 0})

    with ApiClient(transport=httpx.MockTransport(respond)) as api:
        upload = api.upload_resumes(7, [UploadInput("one.pdf", b"synthetic-pdf", "application/pdf"),
                                        UploadInput("two.docx", b"synthetic-docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")])
        assert [item["status"] for item in upload["results"]] == ["ready", "parse_error"]
        assert api.list_resumes(7) == []
        assert api.get_resume(5)["extracted_text"] == "synthetic text"
        assert api.start_analysis(7)["id"] == 11
        assert api.get_analysis(11)["status"] == "running"
        assert api.get_results(11) == {"run_id": 11, "results": []}
    assert seen == [
        ("POST", "/vacancies/7/resumes"), ("GET", "/vacancies/7/resumes"),
        ("GET", "/resumes/5"), ("POST", "/vacancies/7/analyses"),
        ("GET", "/analyses/11"), ("GET", "/analyses/11/results"),
    ]


@pytest.mark.parametrize(("status", "detail", "message"), [
    (404, None, "не найдена"),
    (409, "active_run_exists", "уже выполняется"),
    (422, "no_active_criteria", "активный критерий"),
    (422, [{"msg": "sensitive input"}], "Проверьте"),
    (500, "private traceback", "Ошибка сервера"),
])
def test_http_client_safe_http_errors(status: int, detail: object, message: str) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, json={"detail": detail}))
    with ApiClient(transport=transport) as api, pytest.raises(ApiError) as error:
        api.start_analysis(7)
    assert error.value.status_code == status
    assert message in str(error.value)
    assert "sensitive input" not in str(error.value)
    assert "private traceback" not in str(error.value)


@pytest.mark.parametrize("failure", [
    httpx.ConnectError("private network detail"),
    httpx.ReadTimeout("private timeout detail"),
])
def test_http_client_network_failure_is_safe(failure: Exception) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        failure.request = request
        raise failure

    with ApiClient(transport=httpx.MockTransport(fail)) as api, pytest.raises(ApiError) as error:
        api.health()
    assert "private" not in str(error.value)


def test_http_client_rejects_malformed_response() -> None:
    with ApiClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))) as api:
        with pytest.raises(ApiError, match="некорректный ответ"):
            api.list_vacancies()


def test_backend_url_is_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:9999/base/")
    seen: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"status": "ok"})

    with ApiClient(transport=httpx.MockTransport(respond)) as api:
        assert api.health()
    assert seen == ["http://127.0.0.1:9999/base/health"]


def test_upload_messages_and_snapshot_findings() -> None:
    assert upload_message({"status": "ready", "duplicate": True}) == "Файл уже был загружен"
    assert "извлечь" in upload_message({"status": "parse_error", "error": "raw private detail"})
    assert "raw private detail" not in upload_message({"status": "parse_error", "error": "raw private detail"})
    assert "лимит" in upload_message({"status": "rejected", "error": "File exceeds 100 byte limit"})
    snapshot = [{"id": 2, "description": "Старый критерий", "priority": "required"}]
    result = {"status": "completed", "findings": [{"criterion_id": 2, "status": "not_found",
                                                     "evidence_quote": None, "evidence_page": None}]}
    paired = findings_with_snapshot(result, snapshot)
    assert paired[0]["criterion"]["description"] == "Старый критерий"
    assert paired[0]["finding"]["evidence_quote"] is None
    assert visible_results([result, {"status": "failed", "findings": []}], "confirmed") == [
        {"status": "failed", "findings": []}
    ]


def test_technical_progress_and_run_state_survive_rerun() -> None:
    state: dict = {}
    run = {"id": 11, "vacancy_id": 7, "total": 4, "completed": 1,
           "failed": 1, "interrupted": 1}
    remember_run(state, run)
    assert current_run_id(state, 7) == 11
    assert technical_progress(run) == 0.75
    assert technical_progress({"total": 0}) == 0
    assert state["selected_vacancy_id"] == 7


class FakeUiBackend:
    def __init__(self) -> None:
        self.vacancies = [{"id": 7, "title": "Аналитик", "description": "Синтетическая роль"}]
        self.criteria: list[dict] = []
        self.start_calls = 0
        self.result_calls = 0
        self.create_calls = 0
        self.update_calls = 0
        self.upload_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def health(self):
        return True

    def list_vacancies(self):
        return self.vacancies

    def create_vacancy(self, title, description):
        self.create_calls += 1
        item = {"id": 7, "title": title, "description": description}
        self.vacancies.append(item)
        return item

    def update_vacancy(self, vacancy_id, title, description):
        self.update_calls += 1
        item = next(item for item in self.vacancies if item["id"] == vacancy_id)
        item.update(title=title, description=description)
        return item

    def list_criteria(self, vacancy_id):
        return self.criteria

    def create_criterion(self, vacancy_id, description, priority, active):
        item = {"id": 3, "vacancy_id": vacancy_id, "description": description,
                "priority": priority, "active": active, "display_order": 0}
        self.criteria.append(item)
        return item

    def update_criterion(self, criterion_id, **changes):
        item = next(item for item in self.criteria if item["id"] == criterion_id)
        item.update(changes)
        return item

    def delete_criterion(self, criterion_id):
        self.criteria = [item for item in self.criteria if item["id"] != criterion_id]

    def list_resumes(self, vacancy_id):
        return []

    def start_analysis(self, vacancy_id):
        self.start_calls += 1
        return {"id": 11, "vacancy_id": vacancy_id, "status": "pending"}

    def get_analysis(self, run_id):
        return {"id": run_id, "vacancy_id": 7, "status": "completed_with_errors",
                "total": 2, "pending": 0, "running": 0, "completed": 1,
                "failed": 1, "interrupted": 0,
                "criterion_snapshot": [
                    {"id": 3, "description": "Исторический Python", "priority": "required"},
                    {"id": 4, "description": "Исторический SQL", "priority": "preferred"},
                ]}

    def get_results(self, run_id):
        self.result_calls += 1
        return {"run_id": run_id, "results": [
            {"resume_id": 5, "filename": "synthetic.pdf", "status": "completed",
             "error": None, "findings": [
                 {"criterion_id": 3, "status": "confirmed", "evidence_quote": "Experience: Python",
                  "evidence_page": 1, "follow_up_question": None},
                 {"criterion_id": 4, "status": "not_found", "evidence_quote": None,
                  "evidence_page": None, "follow_up_question": "Уточнить опыт"},
             ]},
            {"resume_id": 6, "filename": "broken.pdf", "status": "failed",
             "error": "resume_not_ready", "findings": []},
        ]}

    def get_resume(self, resume_id):
        return {"id": resume_id, "extracted_text": "Синтетический исходный текст"}


def test_streamlit_start_rerun_results_snapshot_and_no_repeat_post() -> None:
    backend = FakeUiBackend()
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        assert not app.exception
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Анализ").run()
        assert not app.exception
        app.button(key="start_analysis_7").click().run()
        assert not app.exception
        assert backend.start_calls == 1
        assert app.session_state["run_ids"][7] == 11
        app.run()
        assert backend.start_calls == 1
        assert any("ход обработки" in item.value for item in app.caption)
        app.sidebar.radio[0].set_value("Результаты").run()
        assert not app.exception
        assert backend.result_calls >= 1
        assert any("Исторический Python" in item.value for item in app.markdown)
        assert any("цитата отсутствует" in item.value.lower() for item in app.caption)
        assert any("Проверенная страница PDF: 1" in item.value for item in app.caption)
        assert any("Experience: Python" in item.value for item in app.get("code"))
        assert all("пригодности" not in item.value.lower() for item in app.markdown)
        next(item for item in app.selectbox if item.label == "Открыть извлечённый текст резюме").set_value(5).run()
        assert any(item.value == "Синтетический исходный текст" for item in app.text_area)


def test_streamlit_backend_unavailable_has_safe_empty_state() -> None:
    class Offline(FakeUiBackend):
        def health(self):
            raise ApiError("Сервер недоступен. Запустите FastAPI и повторите действие.")

    with patch("ui.api_client.ApiClient", lambda: Offline()):
        app = AppTest.from_file(APP_PATH).run()
    assert not app.exception
    assert any("Сервер недоступен" in item.value for item in app.error)


def _button(app: AppTest, label: str):
    return next(item for item in app.button if item.label == label)


def test_streamlit_vacancy_and_criterion_crud_buttons() -> None:
    backend = FakeUiBackend()
    backend.vacancies = []
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        assert any("Пока нет вакансий" in item.value for item in app.info)
        app.text_input(key="new_vacancy_title").set_value("Инженер")
        app.text_area(key="new_vacancy_description").set_value("Синтетическая роль")
        _button(app, "Создать вакансию").click().run()
        assert not app.exception
        assert backend.create_calls == 1
        assert app.session_state["selected_vacancy_id"] == 7
        next(item for item in app.text_input if item.label == "Название вакансии").set_value("Старший инженер")
        _button(app, "Сохранить вакансию").click().run()
        assert backend.update_calls == 1
        assert backend.vacancies[0]["title"] == "Старший инженер"

        app.sidebar.radio[0].set_value("Критерии").run()
        next(item for item in app.text_input if item.label == "Описание критерия").set_value("Python")
        next(item for item in app.selectbox if item.label == "Приоритет").set_value("preferred")
        _button(app, "Добавить критерий").click().run()
        assert not app.exception
        assert backend.criteria[0]["priority"] == "preferred"
        next(item for item in app.text_input if item.label == "Описание").set_value("SQL")
        _button(app, "Сохранить критерий").click().run()
        assert backend.criteria[0]["id"] == 3
        assert backend.criteria[0]["description"] == "SQL"
        app.checkbox(key="confirm_delete_3").check().run()
        app.button(key="delete_criterion_3").click().run()
        assert backend.criteria == []


def test_streamlit_manual_run_reopen_and_upload_outcome_display() -> None:
    backend = FakeUiBackend()
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.radio[0].set_value("Анализ").run()
        next(item for item in app.number_input if item.label.startswith("Открыть существующий")).set_value(11)
        _button(app, "Открыть запуск").click().run()
        assert not app.exception
        assert app.session_state["run_ids"][7] == 11
        assert backend.start_calls == 0
        app.sidebar.radio[0].set_value("Резюме").run()
        app.session_state["last_upload_results"] = {7: [
            {"filename": "same.pdf", "status": "ready", "duplicate": True},
            {"filename": "bad.docx", "status": "parse_error", "duplicate": False,
             "error": "private parsing detail"},
        ]}
        app.run()
        assert not app.exception
        table = app.dataframe[0].value
        assert table["Дубликат"].tolist() == ["Да", "Нет"]
        assert table["Статус"].tolist() == ["Готово", "Ошибка извлечения текста"]
        assert "private parsing detail" not in table.to_string()
        assert backend.upload_calls == 0
