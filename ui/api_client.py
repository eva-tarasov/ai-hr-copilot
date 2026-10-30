"""Small HTTP-only client for the local FastAPI backend."""

from collections.abc import Sequence
from dataclasses import dataclass
import os
from typing import Any

import httpx


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"

_SAFE_DETAILS = {
    "active_run_exists": "Для вакансии уже выполняется анализ. Откройте текущий запуск и обновите его статус.",
    "no_active_criteria": "Нет активных критериев. Откройте раздел «Критерии», добавьте или включите профессиональный критерий и повторите запуск.",
    "no_ready_resumes": "Нет готовых резюме. Откройте раздел «Резюме», загрузите PDF/DOCX с доступным текстом и повторите запуск.",
    "prohibited_criterion": "Нельзя анализировать возраст и другие чувствительные характеристики кандидата. Откройте раздел «Критерии», выключите или удалите запрещённый критерий и повторите запуск.",
    "resume_in_analysis": "Документ связан с историей анализа и не может быть удалён без нарушения сохранённых результатов.",
    "active_run_blocks_archive": "Пока анализ выполняется, архивирование недоступно. Дождитесь завершения и повторите действие.",
}


class ApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None,
                 code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class UploadInput:
    name: str
    data: bytes
    content_type: str


class ApiClient:
    def __init__(
        self, base_url: str | None = None, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        url = (base_url or os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL)).rstrip("/")
        try:
            self._http = httpx.Client(base_url=url, timeout=5.0, transport=transport)
        except ValueError:
            raise ApiError("Некорректный адрес backend в BACKEND_URL.") from None

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *args: object) -> None:
        self._http.close()

    def _request(self, method: str, path: str, *, kind: type = dict, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise ApiError("Сервер не ответил вовремя. Повторите действие.") from None
        except httpx.RequestError:
            raise ApiError("Сервер недоступен. Запустите FastAPI и повторите действие.") from None
        if response.is_error:
            detail = None
            if response.status_code in (409, 422):
                try:
                    body = response.json()
                    detail = body.get("detail") if isinstance(body, dict) else None
                except ValueError:
                    pass
            if response.status_code == 404:
                message = "Запись не найдена. Обновите данные и попробуйте снова."
            elif response.status_code == 409:
                message = _SAFE_DETAILS.get(detail, "Конфликт данных. Обновите страницу и повторите действие.") if isinstance(detail, str) else "Конфликт данных. Обновите страницу и повторите действие."
            elif response.status_code == 422:
                message = _SAFE_DETAILS.get(detail, "Проверьте введённые данные.") if isinstance(detail, str) else "Проверьте введённые данные."
            elif response.status_code >= 500:
                message = "Ошибка сервера. Повторите действие позже."
            else:
                message = "Не удалось выполнить запрос. Проверьте данные."
            code = detail if isinstance(detail, str) and detail in _SAFE_DETAILS else None
            raise ApiError(message, status_code=response.status_code, code=code)
        if response.status_code == 204:
            return None
        try:
            payload = response.json()
        except ValueError:
            raise ApiError("Сервер вернул некорректный ответ.") from None
        if not isinstance(payload, kind):
            raise ApiError("Сервер вернул некорректный ответ.")
        return payload

    def health(self) -> bool:
        return self._request("GET", "/health") == {"status": "ok"}

    def list_vacancies(self) -> list[dict[str, Any]]:
        return self._request("GET", "/vacancies", kind=list)

    def create_vacancy(self, title: str, description: str) -> dict[str, Any]:
        return self._request("POST", "/vacancies", json={"title": title, "description": description})

    def update_vacancy(self, vacancy_id: int, title: str, description: str) -> dict[str, Any]:
        return self._request("PATCH", f"/vacancies/{vacancy_id}", json={"title": title, "description": description})

    def list_criteria(self, vacancy_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/vacancies/{vacancy_id}/criteria", kind=list)

    def create_criterion(self, vacancy_id: int, description: str, priority: str,
                         active: bool, display_order: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"description": description, "priority": priority, "active": active}
        if display_order is not None:
            payload["display_order"] = display_order
        return self._request("POST", f"/vacancies/{vacancy_id}/criteria", json=payload)

    def update_criterion(self, criterion_id: int, *, description: str, priority: str,
                         active: bool, display_order: int) -> dict[str, Any]:
        return self._request("PATCH", f"/criteria/{criterion_id}", json={
            "description": description, "priority": priority, "active": active,
            "display_order": display_order,
        })

    def delete_criterion(self, criterion_id: int) -> None:
        self._request("DELETE", f"/criteria/{criterion_id}")

    def upload_resumes(self, vacancy_id: int, files: Sequence[UploadInput]) -> dict[str, Any]:
        parts = [("files", (item.name, item.data, item.content_type)) for item in files]
        return self._request("POST", f"/vacancies/{vacancy_id}/resumes",
                             files=parts, timeout=60.0)

    def list_resumes(self, vacancy_id: int, *, include_archived: bool = False) -> list[dict[str, Any]]:
        return self._request("GET", f"/vacancies/{vacancy_id}/resumes",
                             params={"include_archived": "true"} if include_archived else None,
                             kind=list)

    def get_resume(self, resume_id: int) -> dict[str, Any]:
        return self._request("GET", f"/resumes/{resume_id}")

    def delete_resume(self, resume_id: int) -> None:
        self._request("DELETE", f"/resumes/{resume_id}")

    def archive_resume(self, resume_id: int) -> dict[str, Any]:
        return self._request("POST", f"/resumes/{resume_id}/archive")

    def restore_resume(self, resume_id: int) -> dict[str, Any]:
        return self._request("POST", f"/resumes/{resume_id}/restore")

    def start_analysis(self, vacancy_id: int) -> dict[str, Any]:
        return self._request("POST", f"/vacancies/{vacancy_id}/analyses")

    def get_analysis(self, run_id: int) -> dict[str, Any]:
        return self._request("GET", f"/analyses/{run_id}")

    def list_analyses(self, vacancy_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/vacancies/{vacancy_id}/analyses", kind=list)

    def get_results(self, run_id: int) -> dict[str, Any]:
        return self._request("GET", f"/analyses/{run_id}/results")
