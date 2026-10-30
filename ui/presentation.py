"""UI-only labels and projections of existing HTTP responses."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any


RUN_LABELS = {
    "pending": "Ожидает запуска",
    "running": "Обрабатывается",
    "completed": "Завершён",
    "completed_with_errors": "Завершён с ошибками",
    "failed": "Завершился ошибкой",
    "interrupted": "Прерван",
}
DOCUMENT_LABELS = {
    "pending": "Ожидает",
    "running": "Обрабатывается",
    "completed": "Обработано",
    "failed": "Ошибка",
    "interrupted": "Прервано",
}
FINDING_LABELS = {
    "confirmed": "Подтверждено цитатой",
    "mentioned": "Упомянуто",
    "not_found": "Не найдено в резюме",
    "conflicting": "Противоречивые сведения",
}
FINDING_EXPLANATIONS = {
    "confirmed": "В тексте есть прямая цитата по критерию. Вывод требует проверки человеком.",
    "mentioned": "Критерий упомянут, но опыт не подтверждён.",
    "not_found": "В документе не найдено подтверждение. Это не означает отсутствие навыка.",
    "conflicting": "В документе есть противоречивые сведения; их следует уточнить.",
}
UPLOAD_LABELS = {
    "ready": "Готово",
    "unsupported": "Не поддерживается",
    "parse_error": "Ошибка извлечения текста",
    "rejected": "Отклонено",
}
PRIORITY_LABELS = {"required": "Обязательный", "preferred": "Желательный"}
MATRIX_FINDING_LABELS = {
    "confirmed": "✓ Подтверждено",
    "mentioned": "≈ Упомянуто",
    "not_found": "— Не найдено в тексте",
    "conflicting": "! Противоречие",
}


def run_label(run: Mapping[str, Any]) -> str:
    created = datetime.fromisoformat(run["created_at"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)  # SQLite stores utc_now() without tzinfo.
    created = created.astimezone(UTC)
    return f"{created:%d.%m.%Y %H:%M} UTC · {RUN_LABELS.get(run['status'], run['status'])} · #{run['id']}"


def matrix_column(criterion: Mapping[str, Any]) -> str:
    return f"{criterion['description']} · #{criterion['id']}"


def matrix_rows(
    results: Sequence[dict[str, Any]], snapshot: Sequence[dict[str, Any]]
) -> list[dict[str, str]]:
    rows = []
    for result in results:
        row = {
            "Документ": result["filename"],
            "Статус обработки": DOCUMENT_LABELS.get(result["status"], result["status"]),
        }
        findings = {item["criterion_id"]: item for item in result.get("findings", [])}
        for criterion in snapshot:
            if result["status"] != "completed":
                value = DOCUMENT_LABELS.get(result["status"], result["status"])
            elif criterion["id"] not in findings:
                value = "Нет результата"
            else:
                status = findings[criterion["id"]]["status"]
                value = MATRIX_FINDING_LABELS.get(status, status)
            row[matrix_column(criterion)] = value
        rows.append(row)
    return rows


def detail_findings(
    result: Mapping[str, Any], snapshot: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {item.get("criterion_id"): item for item in result.get("findings", [])}
    return [{"criterion": item, "finding": by_id.get(item["id"])} for item in snapshot]


def technical_progress(run: Mapping[str, Any]) -> float:
    total = run.get("total", 0)
    if not isinstance(total, int) or total <= 0:
        return 0.0
    done = sum(int(run.get(key, 0)) for key in ("completed", "failed", "interrupted"))
    return min(1.0, max(0.0, done / total))


def visible_results(results: Sequence[dict[str, Any]], finding_status: str | None) -> list[dict[str, Any]]:
    if finding_status is None:
        return list(results)
    return [
        result for result in results
        if result.get("status") != "completed"
        or any(item.get("status") == finding_status for item in result.get("findings", []))
    ]


def findings_with_snapshot(
    result: Mapping[str, Any], snapshot: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {item.get("criterion_id"): item for item in result.get("findings", [])}
    return [
        {"criterion": criterion, "finding": by_id[criterion["id"]]}
        for criterion in snapshot if criterion.get("id") in by_id
    ]


def upload_message(item: Mapping[str, Any]) -> str:
    status = item.get("status")
    if item.get("archived"):
        return "Файл уже хранится в архиве; восстановите его для нового анализа"
    if status == "ready":
        return "Файл уже был загружен" if item.get("duplicate") else "Текст извлечён"
    if status == "unsupported":
        return "Формат не поддерживается или в документе нет доступного текста"
    if status == "parse_error":
        return "Не удалось извлечь текст из файла"
    if status == "rejected":
        error = item.get("error")
        return "Превышен лимит размера файла" if isinstance(error, str) and error.startswith("File exceeds") else "Не удалось принять или сохранить файл"
    return "Неизвестный статус файла"


def remember_run(state: dict[str, Any], run: Mapping[str, Any]) -> None:
    vacancy_id = int(run["vacancy_id"])
    run_id = int(run["id"])
    state.setdefault("run_ids", {})[vacancy_id] = run_id
    state["selected_vacancy_id"] = vacancy_id


def current_run_id(state: Mapping[str, Any], vacancy_id: int) -> int | None:
    value = state.get("run_ids", {}).get(vacancy_id)
    return value if isinstance(value, int) and value > 0 else None
