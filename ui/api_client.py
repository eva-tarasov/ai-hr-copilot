"""Small HTTP-only client for the local FastAPI backend."""

from collections.abc import Sequence
from dataclasses import dataclass
import os
from typing import Any

import httpx


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"

_SAFE_DETAILS = {
    "active_run_exists": "Для этой вакансии уже выполняется анализ.",
    "no_active_criteria": "Добавьте хотя бы один активный критерий.",
    "no_ready_resumes": "Загрузите хотя бы одно обработанное резюме.",
    "prohibited_criterion": "Критерий содержит недопустимые персональные признаки.",
}


class ApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
            if response.status_code == 422:
                try:
                    body = response.json()
                    detail = body.get("detail") if isinstance(body, dict) else None
                except ValueError:
                    pass
            if response.status_code == 404:
                message = "Запись не найдена. Обновите данные и попробуйте снова."
            elif response.status_code == 409:
                message = "Для этой вакансии уже выполняется анализ. Обновите статус запуска."
            elif response.status_code == 422:
                message = _SAFE_DETAILS.get(detail, "Проверьте введённые данные.") if isinstance(detail, str) else "Проверьте введённые данные."
            elif response.status_code >= 500:
                message = "Ошибка сервера. Повторите действие позже."
            else:
                message = "Не удалось выполнить запрос. Проверьте данные."
            raise ApiError(message, status_code=response.status_code)
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

    def list_resumes(self, vacancy_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/vacancies/{vacancy_id}/resumes", kind=list)

    def get_resume(self, resume_id: int) -> dict[str, Any]:
        return self._request("GET", f"/resumes/{resume_id}")

    def start_analysis(self, vacancy_id: int) -> dict[str, Any]:
        return self._request("POST", f"/vacancies/{vacancy_id}/analyses")

    def get_analysis(self, run_id: int) -> dict[str, Any]:
        return self._request("GET", f"/analyses/{run_id}")

    def get_results(self, run_id: int) -> dict[str, Any]:
        return self._request("GET", f"/analyses/{run_id}/results")
