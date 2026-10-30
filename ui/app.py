"""Russian Streamlit vertical slice; all data comes from FastAPI over HTTP."""

from collections.abc import Sequence
from typing import Any

import streamlit as st

from ui.api_client import ApiClient, ApiError, UploadInput
from ui.presentation import (
    DOCUMENT_LABELS, FINDING_EXPLANATIONS, FINDING_LABELS, PRIORITY_LABELS,
    RUN_LABELS, UPLOAD_LABELS, current_run_id, findings_with_snapshot,
    remember_run, technical_progress, upload_message, visible_results,
)

MAX_FILES_PER_REQUEST = 20

_DOCUMENT_ERRORS = {
    "resume_not_ready": "Текст документа не был извлечён; анализ не выполнялся.",
    "timeout": "Провайдер не ответил вовремя.",
    "transient_api_error": "Временная ошибка провайдера после повторных попыток.",
    "refusal": "Провайдер отказался обрабатывать документ.",
    "invalid_output": "Провайдер вернул некорректный ответ.",
    "missing_criterion_id": "В ответе отсутствует один из критериев.",
    "invalid_quote": "Цитата не прошла проверку по тексту документа.",
    "internal_error": "Ошибка обработки документа.",
    "interrupted": "Обработка прервана; можно создать новый запуск.",
}


def _selected_vacancy(vacancies: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    current = st.session_state.get("selected_vacancy_id")
    by_id = {item["id"]: item for item in vacancies}
    if current not in by_id:
        current = None
        st.session_state["selected_vacancy_id"] = None
    selected = st.sidebar.selectbox(
        "Вакансия", [None, *by_id],
        index=0 if current is None else list(by_id).index(current) + 1,
        format_func=lambda value: "Выберите вакансию" if value is None else by_id[value]["title"],
    )
    if selected != current:
        st.session_state["vacancy_mode"] = "edit" if selected is not None else "create"
    st.session_state["selected_vacancy_id"] = selected
    return by_id.get(selected)


def _vacancies_page(api: ApiClient, vacancies: list[dict[str, Any]],
                    selected: dict[str, Any] | None) -> None:
    st.header("Вакансии")
    if vacancies:
        st.dataframe(
            [{"ID": item["id"], "Название": item["title"], "Описание": item["description"]}
             for item in vacancies], hide_index=True, width="stretch",
        )
    else:
        st.info("Пока нет вакансий. Создайте первую вакансию ниже.")
    mode = st.session_state.get("vacancy_mode", "edit" if selected else "create")
    if selected is not None and mode != "create":
        if st.button("Новая вакансия"):
            st.session_state["vacancy_mode"] = "create"
            st.rerun()
        with st.form(f"edit_vacancy_{selected['id']}"):
            st.subheader("Редактировать выбранную вакансию")
            edited_title = st.text_input("Название вакансии", value=selected["title"])
            edited_description = st.text_area("Описание вакансии", value=selected["description"])
            save = st.form_submit_button("Сохранить вакансию")
        if save:
            with st.spinner("Сохраняем вакансию…"):
                api.update_vacancy(selected["id"], edited_title, edited_description)
            st.rerun()
        return
    if selected is not None and st.button("Вернуться к вакансии"):
        st.session_state["vacancy_mode"] = "edit"
        st.rerun()
    generation = st.session_state.get("vacancy_form_generation", 0)
    with st.form(f"create_vacancy_{generation}"):
        st.subheader("Новая вакансия")
        title = st.text_input("Название", key=f"new_vacancy_title_{generation}")
        description = st.text_area("Описание", key=f"new_vacancy_description_{generation}")
        create = st.form_submit_button("Создать вакансию")
    if create:
        with st.spinner("Создаём вакансию…"):
            vacancy = api.create_vacancy(title, description)
        st.session_state["vacancy_form_generation"] = generation + 1
        st.session_state["selected_vacancy_id"] = vacancy["id"]
        st.session_state["vacancy_mode"] = "edit"
        st.rerun()


def _criteria_page(api: ApiClient, selected: dict[str, Any] | None) -> None:
    st.header("Критерии")
    if selected is None:
        st.info("Сначала выберите вакансию в боковой панели.")
        return
    criteria = api.list_criteria(selected["id"])
    if criteria:
        st.dataframe(
            [{"ID": item["id"], "Критерий": item["description"],
              "Приоритет": PRIORITY_LABELS.get(item["priority"], item["priority"]),
              "Статус": "Активен" if item["active"] else "Выключен",
              "Порядок": item["display_order"]}
             for item in criteria], hide_index=True, width="stretch",
        )
    else:
        st.info("У этой вакансии пока нет критериев. Добавьте первый ниже.")
    generation = st.session_state.get(f"criterion_form_generation_{selected['id']}", 0)
    with st.form(f"create_criterion_{selected['id']}_{generation}"):
        st.subheader("Добавить критерий")
        description = st.text_input("Описание критерия", key=f"criterion_description_{selected['id']}_{generation}")
        priority = st.selectbox("Приоритет", ["required", "preferred"],
                                format_func=lambda value: PRIORITY_LABELS[value],
                                key=f"criterion_priority_{selected['id']}_{generation}")
        active = st.checkbox("Активен", value=True,
                             key=f"criterion_active_{selected['id']}_{generation}")
        create = st.form_submit_button("Добавить критерий")
    if create:
        with st.spinner("Сохраняем критерий…"):
            api.create_criterion(selected["id"], description, priority, active)
        st.session_state[f"criterion_form_generation_{selected['id']}"] = generation + 1
        st.rerun()
    for item in criteria:
        active_label = "Активен" if item["active"] else "Выключен"
        with st.expander(f"#{item['id']} · {item['description']} · {active_label}"):
            with st.form(f"edit_criterion_{item['id']}"):
                edited_description = st.text_input("Описание", value=item["description"])
                edited_priority = st.selectbox(
                    "Приоритет", ["required", "preferred"],
                    index=0 if item["priority"] == "required" else 1,
                    format_func=lambda value: PRIORITY_LABELS[value],
                )
                edited_active = st.checkbox("Активен", value=item["active"])
                edited_order = st.number_input("Порядок отображения", min_value=0,
                                               value=item["display_order"], step=1)
                save = st.form_submit_button("Сохранить критерий")
            if save:
                with st.spinner("Сохраняем критерий…"):
                    api.update_criterion(
                        item["id"], description=edited_description, priority=edited_priority,
                        active=edited_active, display_order=int(edited_order),
                    )
                st.rerun()
            confirm = st.checkbox("Подтвердить удаление", key=f"confirm_delete_{item['id']}")
            if st.button("Удалить критерий", key=f"delete_criterion_{item['id']}",
                         disabled=not confirm):
                api.delete_criterion(item["id"])
                st.rerun()


def _resumes_page(api: ApiClient, selected: dict[str, Any] | None) -> None:
    st.header("Резюме")
    if selected is None:
        st.info("Сначала выберите вакансию в боковой панели.")
        return
    st.caption("PDF или DOCX; по умолчанию до 10 МБ на файл и до 20 файлов за запрос.")
    generation_key = f"upload_generation_{selected['id']}"
    generation = st.session_state.get(generation_key, 0)
    with st.form(f"upload_{selected['id']}_{generation}"):
        files = st.file_uploader("Выберите файлы", type=["pdf", "docx"],
                                 accept_multiple_files=True,
                                 key=f"files_{selected['id']}_{generation}")
        submit = st.form_submit_button("Загрузить резюме")
    if submit:
        if not files:
            st.warning("Выберите хотя бы один файл.")
        elif len(files) > MAX_FILES_PER_REQUEST:
            st.error("За один запрос можно загрузить не более 20 файлов.")
        else:
            inputs = [UploadInput(file.name, file.getvalue(), file.type or "application/octet-stream")
                      for file in files]
            with st.spinner("Загружаем и проверяем файлы…"):
                outcome = api.upload_resumes(selected["id"], inputs)
            st.session_state.setdefault("last_upload_results", {})[selected["id"]] = outcome.get("results", [])
            st.session_state[generation_key] = generation + 1
            st.rerun()
    outcomes = st.session_state.get("last_upload_results", {}).get(selected["id"], [])
    if outcomes:
        st.subheader("Результаты последней загрузки")
        st.dataframe(
            [{"Файл": item.get("filename", ""),
              "Статус": UPLOAD_LABELS.get(item.get("status"), "Неизвестно"),
              "Дубликат": "Да" if item.get("duplicate") else "Нет",
              "Сообщение": upload_message(item)} for item in outcomes],
            hide_index=True, width="stretch",
        )
    resumes = api.list_resumes(selected["id"])
    if not resumes:
        st.info("У этой вакансии пока нет загруженных резюме.")
        return
    st.subheader("Загруженные резюме")
    st.dataframe(
        [{"ID": item["id"], "Файл": item["filename"],
          "Статус": UPLOAD_LABELS.get(item["status"], item["status"])}
         for item in resumes], hide_index=True, width="stretch",
    )
    by_id = {item["id"]: item for item in resumes}
    delete_generation_key = f"resume_delete_generation_{selected['id']}"
    delete_generation = st.session_state.get(delete_generation_key, 0)
    delete_id = st.selectbox(
        "Удалить ошибочно загруженный документ", [None, *by_id],
        format_func=lambda value: "Выберите документ" if value is None
        else f"#{value} · {by_id[value]['filename']}",
        key=f"resume_to_delete_{selected['id']}_{delete_generation}",
    )
    if delete_id is not None:
        item = by_id[delete_id]
        st.warning(f"Удаление документа #{delete_id} · {item['filename']} нельзя отменить.")
        confirmed = st.checkbox(
            f"Подтверждаю удаление документа #{delete_id}",
            key=f"confirm_resume_delete_{selected['id']}_{delete_id}",
        )
        if st.button("Удалить резюме", disabled=not confirmed,
                     key=f"delete_resume_{selected['id']}_{delete_id}"):
            try:
                api.delete_resume(delete_id)
            except ApiError as error:
                st.error(str(error))
            else:
                st.session_state[delete_generation_key] = delete_generation + 1
                st.rerun()


def _analysis_page(api: ApiClient, selected: dict[str, Any] | None) -> None:
    st.header("Анализ")
    with st.expander("Открыть предыдущий анализ"):
        st.caption("ID выдаётся системой при запуске. Введите его, чтобы восстановить просмотр после обновления браузера.")
        with st.form("open_run"):
            known_id = st.number_input("ID анализа", min_value=1, step=1)
            open_run = st.form_submit_button("Открыть анализ")
        if open_run:
            run = api.get_analysis(int(known_id))
            remember_run(st.session_state, run)
            st.rerun()
    if selected is None:
        st.info("Выберите вакансию или откройте запуск по ID.")
        return
    st.caption("Анализируются активные критерии и загруженные резюме с доступным текстом.")
    if st.button("Запустить анализ", key=f"start_analysis_{selected['id']}"):
        try:
            with st.spinner("Создаём запуск…"):
                run = api.start_analysis(selected["id"])
        except ApiError as error:
            st.error(str(error))
            if error.code == "prohibited_criterion":
                active = [item for item in api.list_criteria(selected["id"]) if item["active"]]
                st.write("Активные критерии для проверки:")
                for item in active:
                    st.write(f"• #{item['id']} · {item['description']}")
        else:
            remember_run(st.session_state, run)
            st.rerun()
    run_id = current_run_id(st.session_state, selected["id"])
    if run_id is None:
        st.info("Запусков в этой сессии нет. Начните анализ или откройте известный ID.")
        return
    run = api.get_analysis(run_id)
    st.subheader(f"Запуск #{run_id}")
    st.write(f"Состояние: {RUN_LABELS.get(run['status'], run['status'])}")
    st.write(
        f"Всего: {run['total']} · Ожидают: {run['pending']} · В работе: {run['running']} · "
        f"Завершены: {run['completed']} · Ошибки: {run['failed']} · Прерваны: {run['interrupted']}"
    )
    progress = technical_progress(run)
    st.progress(progress, text=f"Завершено обработок: {round(progress * 100)}%")
    st.caption("Это только ход обработки документов, не оценка кандидатов.")
    st.button("Обновить", key=f"refresh_run_{run_id}")
    st.caption("Обновление выполняется по нажатию кнопки; автоматического опроса нет.")


def _results_page(api: ApiClient, selected: dict[str, Any] | None) -> None:
    st.header("Результаты")
    if selected is None:
        st.info("Выберите вакансию и откройте запуск в разделе «Анализ».")
        return
    run_id = current_run_id(st.session_state, selected["id"])
    if run_id is None:
        st.info("Укажите ID существующего запуска в разделе «Анализ» или начните новый.")
        return
    run = api.get_analysis(run_id)
    payload = api.get_results(run_id)
    all_results = payload.get("results", [])
    st.caption(f"Запуск #{run_id}. Критерии взяты из snapshot этого запуска.")
    chosen = st.selectbox(
        "Фильтр по фактическому статусу критерия", [None, *FINDING_LABELS],
        format_func=lambda value: "Все резюме" if value is None else FINDING_LABELS[value],
    )
    results = visible_results(all_results, chosen)
    st.caption("Документы с ошибкой или прерванной обработкой остаются видимыми при фильтрации.")
    if not all_results:
        st.info("В этом запуске пока нет результатов.")
        return
    if not results:
        st.info("По выбранному статусу нет результатов.")
    for item in results:
        label = DOCUMENT_LABELS.get(item["status"], item["status"])
        with st.expander(f"{item['filename']} · {label}"):
            if item.get("error"):
                st.warning(_DOCUMENT_ERRORS.get(item["error"], "Не удалось обработать документ."))
            findings = findings_with_snapshot(item, run["criterion_snapshot"])
            if not findings:
                st.info("Сохранённых выводов по критериям нет.")
            for pair in findings:
                criterion, finding = pair["criterion"], pair["finding"]
                st.write(
                    f"{criterion['description']} · {PRIORITY_LABELS.get(criterion['priority'], criterion['priority'])} · "
                    f"{FINDING_LABELS.get(finding['status'], finding['status'])}"
                )
                st.caption(FINDING_EXPLANATIONS.get(finding["status"], "Требуется проверка человеком."))
                if finding.get("evidence_quote"):
                    st.code(finding["evidence_quote"], language=None)
                else:
                    st.caption("Подтверждающая цитата отсутствует.")
                if finding.get("evidence_page") is not None:
                    st.caption(f"Проверенная страница PDF: {finding['evidence_page']}")
                if finding.get("follow_up_question"):
                    st.write(f"Вопрос для уточнения: {finding['follow_up_question']}")
    by_id = {item["resume_id"]: item for item in all_results}
    selected_resume_id = st.selectbox(
        "Открыть извлечённый текст резюме", [None, *by_id],
        format_func=lambda value: "Выберите резюме" if value is None else by_id[value]["filename"],
    )
    if selected_resume_id is not None:
        document = api.get_resume(selected_resume_id)
        if document.get("extracted_text"):
            st.text_area("Исходный извлечённый текст", value=document["extracted_text"],
                         height=300, disabled=True)
        else:
            st.info("Извлечённый текст для этого документа недоступен.")


def main() -> None:
    st.set_page_config(page_title="AI HR Copilot", layout="wide")
    st.title("AI HR Copilot")
    st.caption("Локальный помощник для проверки фактов в резюме. Все выводы проверяет человек.")
    try:
        with ApiClient() as api:
            if not api.health():
                st.error("Сервер вернул неожиданный ответ проверки доступности.")
                return
            st.sidebar.success("Сервер доступен")
            vacancies = api.list_vacancies()
            selected = _selected_vacancy(vacancies)
            page = st.sidebar.radio(
                "Раздел", ["Вакансии", "Критерии", "Резюме", "Анализ", "Результаты"]
            )
            if page == "Вакансии":
                _vacancies_page(api, vacancies, selected)
            elif page == "Критерии":
                _criteria_page(api, selected)
            elif page == "Резюме":
                _resumes_page(api, selected)
            elif page == "Анализ":
                _analysis_page(api, selected)
            else:
                _results_page(api, selected)
    except ApiError as error:
        st.error(str(error))


if __name__ == "__main__":
    main()
