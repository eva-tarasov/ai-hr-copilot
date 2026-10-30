"""Offline HTTP-client and Streamlit presentation tests for S05."""

import json
import tomllib
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from ui.api_client import ApiClient, ApiError, UploadInput
from ui.presentation import (
    current_run_id, detail_findings, findings_with_snapshot, matrix_rows,
    remember_run, run_label, technical_progress, upload_message, visible_results,
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
        assert api.delete_resume(5) is None
        assert api.start_analysis(7)["id"] == 11
        assert api.get_analysis(11)["status"] == "running"
        assert api.get_results(11) == {"run_id": 11, "results": []}
    assert seen == [
        ("POST", "/vacancies/7/resumes"), ("GET", "/vacancies/7/resumes"),
        ("GET", "/resumes/5"), ("DELETE", "/resumes/5"),
        ("POST", "/vacancies/7/analyses"),
        ("GET", "/analyses/11"), ("GET", "/analyses/11/results"),
    ]


def test_http_client_archive_restore_and_history_routes() -> None:
    seen: list[tuple[str, str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.url.query.decode()))
        if request.url.path.endswith("/analyses"):
            return httpx.Response(200, json=[{"id": 3, "vacancy_id": 7}])
        if request.url.path.endswith("/resumes"):
            return httpx.Response(200, json=[{"id": 5, "archived": True}])
        return httpx.Response(200, json={"id": 5, "archived": request.url.path.endswith("/archive")})

    with ApiClient(transport=httpx.MockTransport(respond)) as api:
        assert api.list_resumes(7, include_archived=True)[0]["archived"] is True
        assert api.archive_resume(5)["archived"] is True
        assert api.restore_resume(5)["archived"] is False
        assert api.list_analyses(7)[0]["id"] == 3
    assert seen == [
        ("GET", "/vacancies/7/resumes", "include_archived=true"),
        ("POST", "/resumes/5/archive", ""),
        ("POST", "/resumes/5/restore", ""),
        ("GET", "/vacancies/7/analyses", ""),
    ]


@pytest.mark.parametrize(("status", "detail", "message"), [
    (404, None, "не найдена"),
    (409, "active_run_exists", "уже выполняется"),
    (422, "no_active_criteria", "активных критериев"),
    (422, "no_ready_resumes", "готовых резюме"),
    (422, "prohibited_criterion", "возраст"),
    (409, "resume_in_analysis", "связан с историей"),
    (409, "active_run_blocks_archive", "архивирование недоступно"),
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
    assert "архиве" in upload_message({"status": "ready", "duplicate": True, "archived": True})
    snapshot = [{"id": 2, "description": "Старый критерий", "priority": "required"}]
    result = {"status": "completed", "findings": [{"criterion_id": 2, "status": "not_found",
                                                     "evidence_quote": None, "evidence_page": None}]}
    paired = findings_with_snapshot(result, snapshot)
    assert paired[0]["criterion"]["description"] == "Старый критерий"
    assert paired[0]["finding"]["evidence_quote"] is None
    assert visible_results([result, {"status": "failed", "findings": []}], "confirmed") == [
        {"status": "failed", "findings": []}
    ]


def test_matrix_four_findings_and_document_failures_keep_original_order() -> None:
    snapshot = [{"id": index, "description": name, "priority": "required"}
                for index, name in enumerate(("Python", "SQL", "Docker", "Linux"), 1)]
    results = [
        {"resume_id": 8, "filename": "first.pdf", "status": "completed", "findings": [
            {"criterion_id": 1, "status": "confirmed", "evidence_quote": "Python"},
            {"criterion_id": 2, "status": "mentioned"},
            {"criterion_id": 3, "status": "not_found"},
            {"criterion_id": 4, "status": "conflicting"},
        ]},
        {"resume_id": 9, "filename": "failed.pdf", "status": "failed", "findings": []},
        {"resume_id": 10, "filename": "pending.pdf", "status": "pending", "findings": []},
        {"resume_id": 11, "filename": "running.pdf", "status": "running", "findings": []},
        {"resume_id": 12, "filename": "interrupted.pdf", "status": "interrupted", "findings": []},
    ]
    rows = matrix_rows(results, snapshot)
    assert [item["Документ"] for item in rows] == [item["filename"] for item in results]
    assert [rows[0][f"{criterion['description']} · #{criterion['id']}"] for criterion in snapshot] == [
        "✅ Подтверждено", "🟡 Упомянуто", "⚪ Не найдено в тексте", "⚠️ Противоречие",
    ]
    for row, expected in zip(rows[1:], ("❌ Ошибка", "⏳ Ожидает", "🔄 Обрабатывается", "⏸️ Прервано")):
        assert all(row[f"{criterion['description']} · #{criterion['id']}"] == expected
                   for criterion in snapshot)
    assert len(detail_findings(results[0], snapshot)) == 4
    assert all(pair["finding"] is None for pair in detail_findings(results[1], snapshot))
    assert visible_results(results, "confirmed") == [results[0], *results[1:]]
    snapshot[0]["description"] = "Исторический Python"
    assert "Исторический Python · #1" in matrix_rows(results[:1], snapshot)[0]


def test_run_labels_use_explicit_utc_even_for_naive_sqlite_timestamp() -> None:
    old = {"id": 7, "status": "completed", "created_at": "2026-10-30T12:00:00"}
    assert run_label(old) == "30.10.2026 12:00 UTC · Завершён · #7"
    assert run_label({**old, "created_at": "2026-10-30T15:00:00+03:00"}) == run_label(old)


def test_streamlit_theme_is_light_and_readable() -> None:
    config = tomllib.loads((APP_PATH.parents[1] / ".streamlit" / "config.toml").read_text())
    assert config["theme"]["base"] == "light"
    assert config["theme"]["baseFontSize"] >= 18
    assert config["theme"]["backgroundColor"] != config["theme"]["textColor"]


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
        self.criterion_create_calls = 0
        self.resumes: list[dict] = []
        self.deleted_resumes: list[int] = []
        self.start_error: ApiError | None = None
        self.upload_error: ApiError | None = None
        self.delete_error: ApiError | None = None
        self.archive_error: ApiError | None = None
        self.runs: list[dict] = []
        self.archive_calls = 0
        self.restore_calls = 0

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
        item = {"id": max((vacancy["id"] for vacancy in self.vacancies), default=6) + 1,
                "title": title, "description": description}
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
        self.criterion_create_calls += 1
        item = {"id": len(self.criteria) + 3, "vacancy_id": vacancy_id, "description": description,
                "priority": priority, "active": active, "display_order": 0}
        self.criteria.append(item)
        return item

    def update_criterion(self, criterion_id, **changes):
        item = next(item for item in self.criteria if item["id"] == criterion_id)
        item.update(changes)
        return item

    def delete_criterion(self, criterion_id):
        self.criteria = [item for item in self.criteria if item["id"] != criterion_id]

    def list_resumes(self, vacancy_id, *, include_archived=False):
        return [item for item in self.resumes if item["vacancy_id"] == vacancy_id
                and (include_archived or not item.get("archived", False))]

    def upload_resumes(self, vacancy_id, files):
        self.upload_calls += 1
        if self.upload_error:
            raise self.upload_error
        results = []
        for file in files:
            item = {"id": len(self.resumes) + 5, "vacancy_id": vacancy_id,
                    "filename": file.name, "status": "ready", "archived": False}
            self.resumes.append(item)
            results.append({"filename": file.name, "status": "ready", "duplicate": False})
        return {"results": results}

    def delete_resume(self, resume_id):
        self.deleted_resumes.append(resume_id)
        if self.delete_error:
            raise self.delete_error
        self.resumes = [item for item in self.resumes if item["id"] != resume_id]

    def archive_resume(self, resume_id):
        self.archive_calls += 1
        if self.archive_error:
            raise self.archive_error
        item = next(item for item in self.resumes if item["id"] == resume_id)
        item["archived"] = True
        return item

    def restore_resume(self, resume_id):
        self.restore_calls += 1
        item = next(item for item in self.resumes if item["id"] == resume_id)
        item["archived"] = False
        return item

    def start_analysis(self, vacancy_id):
        self.start_calls += 1
        if self.start_error:
            raise self.start_error
        item = {"id": max((run["id"] for run in self.runs), default=10) + 1,
                "vacancy_id": vacancy_id, "status": "pending",
                "created_at": "2026-10-30T10:00:00Z", "started_at": None,
                "completed_at": None, "provider": "fake", "model": None}
        self.runs.append(item)
        return item

    def list_analyses(self, vacancy_id):
        return sorted((item for item in self.runs if item["vacancy_id"] == vacancy_id),
                      key=lambda item: item["id"], reverse=True)

    def get_analysis(self, run_id):
        stored = next((item for item in self.runs if item["id"] == run_id), None)
        return {"id": run_id, "vacancy_id": stored["vacancy_id"] if stored else 7,
                "status": "completed_with_errors",
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
        next(item for item in app.selectbox if item.label == "Детали документа из таблицы").set_value(5).run()
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
        app.text_input(key="new_vacancy_title_0").set_value("Инженер")
        app.text_area(key="new_vacancy_description_0").set_value("Синтетическая роль")
        _button(app, "Создать вакансию").click().run()
        assert not app.exception
        assert backend.create_calls == 1
        assert app.session_state["selected_vacancy_id"] == 7
        assert app.session_state["vacancy_form_generation"] == 1
        assert all(item.label != "Создать вакансию" for item in app.button)
        next(item for item in app.text_input if item.label == "Название вакансии").set_value("Старший инженер")
        _button(app, "Сохранить вакансию").click().run()
        assert backend.update_calls == 1
        assert backend.vacancies[0]["title"] == "Старший инженер"
        assert next(item for item in app.text_input if item.label == "Название вакансии").value == "Старший инженер"

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


def test_streamlit_history_reopen_and_upload_outcome_display() -> None:
    backend = FakeUiBackend()
    backend.runs = [{"id": 11, "vacancy_id": 7, "status": "completed",
                     "created_at": "2026-10-30T10:00:00Z", "started_at": None,
                     "completed_at": None, "provider": "fake", "model": None}]
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Анализ").run()
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


def test_streamlit_vacancy_modes_clear_creation_and_do_not_repeat_post() -> None:
    backend = FakeUiBackend()
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        assert not any(item.label == "Создать вакансию" for item in app.button)
        assert any(item.label == "Сохранить вакансию" for item in app.button)
        _button(app, "Новая вакансия").click().run()
        assert any(item.label == "Создать вакансию" for item in app.button)
        assert not any(item.label == "Сохранить вакансию" for item in app.button)
        app.text_input(key="new_vacancy_title_0").set_value("Новая роль")
        app.text_area(key="new_vacancy_description_0").set_value("Синтетическое описание")
        _button(app, "Создать вакансию").click().run()
        assert not app.exception
        assert backend.create_calls == 1
        assert app.session_state["selected_vacancy_id"] == 8
        assert app.session_state["vacancy_form_generation"] == 1
        assert any(item.label == "Сохранить вакансию" for item in app.button)
        app.run()
        assert backend.create_calls == 1
        _button(app, "Новая вакансия").click().run()
        assert app.text_input(key="new_vacancy_title_1").value == ""
        assert app.text_area(key="new_vacancy_description_1").value == ""


def test_streamlit_criterion_form_resets_and_edit_does_not_create() -> None:
    backend = FakeUiBackend()
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Критерии").run()
        app.text_input(key="criterion_description_7_0").set_value("Python")
        next(item for item in app.selectbox if item.label == "Приоритет").set_value("preferred")
        app.checkbox(key="criterion_active_7_0").uncheck()
        _button(app, "Добавить критерий").click().run()
        assert not app.exception
        assert backend.criterion_create_calls == 1
        assert app.text_input(key="criterion_description_7_1").value == ""
        assert app.selectbox(key="criterion_priority_7_1").value == "required"
        assert app.checkbox(key="criterion_active_7_1").value is True
        assert any("Выключен" in item.label for item in app.get("expander"))
        app.run()
        assert backend.criterion_create_calls == 1
        next(item for item in app.text_input if item.label == "Описание").set_value("SQL")
        _button(app, "Сохранить критерий").click().run()
        assert backend.criterion_create_calls == 1
        assert backend.criteria[0]["description"] == "SQL"
        app.text_input(key="criterion_description_7_1").set_value("Docker")
        _button(app, "Добавить критерий").click().run()
        assert backend.criterion_create_calls == 2
        assert len(backend.criteria) == 2


def test_streamlit_upload_clears_picker_and_does_not_repeat_post() -> None:
    backend = FakeUiBackend()
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Резюме").run()
        app.file_uploader[0].upload("first.pdf", b"synthetic first", "application/pdf")
        _button(app, "Загрузить резюме").click().run()
        assert not app.exception
        assert backend.upload_calls == 1
        assert app.session_state["upload_generation_7"] == 1
        assert app.file_uploader[0].key == "files_7_1"
        assert app.file_uploader[0].value == []
        assert app.dataframe[0].value["Файл"].tolist() == ["first.pdf"]
        app.run()
        assert backend.upload_calls == 1
        app.file_uploader[0].upload("second.docx", b"synthetic second", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        _button(app, "Загрузить резюме").click().run()
        assert backend.upload_calls == 2
        assert app.file_uploader[0].key == "files_7_2"
        assert app.file_uploader[0].value == []
        assert app.dataframe[0].value["Файл"].tolist() == ["second.docx"]


def test_streamlit_upload_error_keeps_picker_for_retry() -> None:
    backend = FakeUiBackend()
    backend.upload_error = ApiError("Сервер недоступен. Запустите FastAPI и повторите действие.")
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Резюме").run()
        app.file_uploader[0].upload("retry.pdf", b"synthetic", "application/pdf")
        _button(app, "Загрузить резюме").click().run()
        assert not app.exception
        assert backend.upload_calls == 1
        assert app.file_uploader[0].key == "files_7_0"
        assert len(app.file_uploader[0].value) == 1
        backend.upload_error = None
        _button(app, "Загрузить резюме").click().run()
        assert backend.upload_calls == 2
        assert app.file_uploader[0].key == "files_7_1"
        assert app.file_uploader[0].value == []


@pytest.mark.parametrize("code,phrase", [
    ("prohibited_criterion", "возраст"),
    ("no_active_criteria", "активных критериев"),
    ("no_ready_resumes", "готовых резюме"),
    ("active_run_exists", "уже выполняется"),
])
def test_streamlit_start_error_explains_next_step(code: str, phrase: str) -> None:
    backend = FakeUiBackend()
    backend.criteria = [{"id": 3, "vacancy_id": 7, "description": "Возраст кандидата",
                         "priority": "required", "active": True, "display_order": 0}]
    backend.start_error = ApiError("Нельзя анализировать возраст и другие чувствительные характеристики кандидата. Откройте раздел «Критерии», выключите или удалите запрещённый критерий и повторите запуск." if code == "prohibited_criterion" else {
        "no_active_criteria": "Нет активных критериев. Откройте раздел «Критерии».",
        "no_ready_resumes": "Нет готовых резюме. Откройте раздел «Резюме».",
        "active_run_exists": "Для вакансии уже выполняется анализ. Обновите статус.",
    }[code], status_code=409 if code == "active_run_exists" else 422, code=code)
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Анализ").run()
        _button(app, "Запустить анализ").click().run()
        assert not app.exception
        assert any(phrase in item.value for item in app.error)
        if code == "prohibited_criterion":
            assert any("Возраст кандидата" in item.value for item in app.markdown)
        app.run()
        assert backend.start_calls == 1


def test_streamlit_resume_delete_requires_confirmation_and_scopes_selection() -> None:
    backend = FakeUiBackend()
    backend.resumes = [{"id": 5, "vacancy_id": 7, "filename": "synthetic.pdf", "status": "ready"},
                       {"id": 6, "vacancy_id": 8, "filename": "elsewhere.pdf", "status": "ready"}]
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Резюме").run()
        picker = next(item for item in app.selectbox if item.label == "Выберите документ для действия")
        assert picker.options == ["Выберите документ", "#5 · synthetic.pdf"]
        picker.set_value(5).run()
        assert _button(app, "Удалить навсегда").disabled
        app.checkbox(key="confirm_resume_delete_7_5").check().run()
        _button(app, "Удалить навсегда").click().run()
        assert backend.deleted_resumes == [5]
        assert backend.resumes == [{"id": 6, "vacancy_id": 8,
                                   "filename": "elsewhere.pdf", "status": "ready"}]


def test_streamlit_resume_delete_conflict_explains_history() -> None:
    backend = FakeUiBackend()
    backend.resumes = [{"id": 5, "vacancy_id": 7, "filename": "linked.pdf", "status": "ready"}]
    backend.delete_error = ApiError(
        "Документ связан с историей анализа и не может быть удалён без нарушения сохранённых результатов.",
        status_code=409, code="resume_in_analysis",
    )
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Резюме").run()
        next(item for item in app.selectbox if item.label == "Выберите документ для действия").set_value(5).run()
        app.checkbox(key="confirm_resume_delete_7_5").check().run()
        _button(app, "Удалить навсегда").click().run()
        assert not app.exception
        assert any("связан с историей анализа" in item.value for item in app.error)
        assert len(backend.resumes) == 1


def test_streamlit_history_switches_runs_and_vacancies_without_post() -> None:
    backend = FakeUiBackend()
    backend.vacancies.append({"id": 8, "title": "Другая роль", "description": "Синтетическая"})
    backend.runs = [
        {"id": run_id, "vacancy_id": vacancy_id, "status": "completed",
         "created_at": f"2026-10-30T{hour:02}:00:00Z", "started_at": None,
         "completed_at": None, "provider": "fake", "model": None}
        for run_id, vacancy_id, hour in [(11, 7, 10), (12, 7, 11), (13, 8, 12)]
    ]
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Анализ").run()
        assert app.session_state["run_ids"][7] == 12
        picker = next(item for item in app.selectbox if item.label == "История анализов")
        assert picker.options == ["30.10.2026 11:00 UTC · Завершён · #12",
                                  "30.10.2026 10:00 UTC · Завершён · #11"]
        picker.set_value(11).run()
        assert app.session_state["run_ids"][7] == 11
        app.run()
        assert app.session_state["run_ids"][7] == 11
        app.sidebar.selectbox[0].set_value(8).run()
        assert app.session_state["run_ids"][8] == 13
        assert "#11" not in str(next(item for item in app.selectbox if item.label == "История анализов").options)
        app.sidebar.selectbox[0].set_value(7).run()
        assert app.session_state["run_ids"][7] == 11
        assert backend.start_calls == 0

        fresh = AppTest.from_file(APP_PATH).run()
        fresh.sidebar.selectbox[0].set_value(7).run()
        fresh.sidebar.radio[0].set_value("Анализ").run()
        assert fresh.session_state["run_ids"][7] == 12
        assert backend.start_calls == 0


def test_streamlit_archive_restore_and_active_run_conflict() -> None:
    backend = FakeUiBackend()
    backend.resumes = [{"id": 5, "vacancy_id": 7, "filename": "linked.pdf",
                        "status": "ready", "archived": False}]
    with patch("ui.api_client.ApiClient", lambda: backend):
        app = AppTest.from_file(APP_PATH).run()
        app.sidebar.selectbox[0].set_value(7).run()
        app.sidebar.radio[0].set_value("Резюме").run()
        next(item for item in app.selectbox if item.label == "Выберите документ для действия").set_value(5).run()
        backend.archive_error = ApiError("Пока анализ выполняется, архивирование недоступно.",
                                         status_code=409, code="active_run_blocks_archive")
        _button(app, "Архивировать").click().run()
        assert any("архивирование недоступно" in item.value for item in app.error)
        assert backend.resumes[0]["archived"] is False
        backend.archive_error = None
        _button(app, "Архивировать").click().run()
        assert backend.resumes[0]["archived"] is True
        assert backend.archive_calls == 2
        app.run()
        assert backend.archive_calls == 2
        next(item for item in app.radio if item.label == "Список резюме").set_value("Архив").run()
        next(item for item in app.selectbox if item.label == "Выберите документ для действия").set_value(5).run()
        _button(app, "Восстановить в активный список").click().run()
        assert backend.resumes[0]["archived"] is False
        assert backend.restore_calls == 1
        assert backend.deleted_resumes == []
