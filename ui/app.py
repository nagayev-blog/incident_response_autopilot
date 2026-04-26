"""Streamlit UI для Incident Response Autopilot.

Стримингово-прогрессивный UI: каждый узел графа отображается по мере готовности.
Использует graph.stream(stream_mode="updates") + st.status() для live-обновлений.

Стадии сессии:
  idle             — начальный экран
  running          — граф стримится в реальном времени
  awaiting_approval — ждём Approve/Reject (CRITICAL)
  resuming         — продолжаем граф после апрува
  done             — всё завершено
  rejected         — отклонено инженером
"""

import json
import uuid
from typing import Any

import streamlit as st

from src.graph.state import IncidentState
from src.graph.workflow import graph

# ── Константы ─────────────────────────────────────────────────────────────────

SEV_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "LOW": "🟡"}

SAMPLE_ALERTS = {
    "CRITICAL — DB down": {
        "id": "alert-001",
        "service": "payments-db",
        "message": "DB connection pool exhausted, 0 connections available, 500 errors/sec",
    },
    "HIGH — Latency spike": {
        "id": "alert-002",
        "service": "checkout-service",
        "message": "Error rate 35%, p99 latency 8000ms, partial outage in EU region",
    },
    "LOW — Disk usage": {
        "id": "alert-003",
        "service": "storage-01",
        "message": "Disk usage at 78%, warning threshold",
    },
}

NODE_LABELS = {
    "triage":         "Шаг 1 — Triage",
    "diagnosis":      "Diagnosis",
    "history":        "History",
    "response":       "Шаг 3 — Response Plan",
    "suggestion":     "Шаг 3 — Suggestion",
    "postmortem":     "Шаг 4 — Postmortem",
}

# ── session_state ──────────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults: dict[str, Any] = {
        "stage": "idle",          # idle|running|awaiting_approval|resuming|done|rejected
        "thread_id": None,
        "pending_alert": None,    # алерт ожидающий запуска
        "completed": {},          # node_name → output dict
        "final_state": {},        # итоговый state графа
        "error": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset() -> None:
    for k in ["stage", "thread_id", "pending_alert", "completed", "final_state", "error"]:
        st.session_state.pop(k, None)
    st.rerun()

# ── Вспомогательные рендеры ────────────────────────────────────────────────────

def _render_triage_content(output: dict[str, Any]) -> None:
    sev = output.get("severity", "—")
    typ = output.get("incident_type", "—")
    icon = SEV_ICON.get(sev, "⚪")
    m = output.get("metrics", {}).get("triage", {})
    st.markdown(f"**Severity:** {icon} `{sev}`  &nbsp;&nbsp;  **Type:** `{typ}`")
    if m:
        st.caption(f"⏱ {m.get('latency_s', '?')}s · {m.get('input_tokens', '-')}/{m.get('output_tokens', '-')} tok")


def _render_diagnosis_content(output: dict[str, Any]) -> None:
    st.markdown(output.get("diagnosis", ""))
    m = output.get("metrics", {}).get("diagnosis", {})
    if m:
        st.caption(f"⏱ {m.get('latency_s', '?')}s · {m.get('input_tokens', '-')}/{m.get('output_tokens', '-')} tok")


def _render_history_content(output: dict[str, Any]) -> None:
    incidents = output.get("similar_incidents", [])
    if not incidents:
        st.caption("Похожих инцидентов не найдено")
    for inc in incidents:
        st.markdown(
            f"**{inc.get('id', '?')}** — {inc.get('title', '')}"
            f"  \n_Score: {inc.get('score', 0):.2f}_ · {inc.get('resolution', '')}"
        )
    m = output.get("metrics", {}).get("history", {})
    if m and m.get("latency_s"):
        st.caption(f"⏱ {m.get('latency_s')}s")


def _render_response_content(output: dict[str, Any]) -> None:
    st.markdown(output.get("response_plan", ""))
    m = output.get("metrics", {}).get("response", {})
    if m:
        st.caption(f"⏱ {m.get('latency_s', '?')}s · {m.get('input_tokens', '-')}/{m.get('output_tokens', '-')} tok")


def _render_postmortem_content(output: dict[str, Any]) -> None:
    st.code(output.get("postmortem", ""), language="markdown")
    m = output.get("metrics", {}).get("postmortem", {})
    if m:
        st.caption(f"⏱ {m.get('latency_s', '?')}s · {m.get('input_tokens', '-')}/{m.get('output_tokens', '-')} tok")


def _render_suggestion_content(output: dict[str, Any]) -> None:
    st.markdown(output.get("response_plan", ""))
    m = output.get("metrics", {}).get("suggestion", {})
    if m:
        st.caption(f"⏱ {m.get('latency_s', '?')}s · {m.get('input_tokens', '-')}/{m.get('output_tokens', '-')} tok")


# ── Статические результаты (для stage != running) ──────────────────────────────

def _render_completed_steps(completed: dict[str, Any], stage: str) -> None:
    """Рендерит уже завершённые шаги как закрытые expander-ы."""

    if "triage" in completed:
        sev = completed["triage"].get("severity", "?")
        icon = SEV_ICON.get(sev, "⚪")
        with st.expander(f"✅ Шаг 1 — Triage: {icon} {sev}", expanded=False):
            _render_triage_content(completed["triage"])

    severity = completed.get("triage", {}).get("severity", "")

    if severity in ("CRITICAL", "HIGH") and ("diagnosis" in completed or "history" in completed):
        with st.expander("✅ Шаг 2 — Diagnosis + History (параллельно)", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Diagnosis")
                if "diagnosis" in completed:
                    _render_diagnosis_content(completed["diagnosis"])
            with c2:
                st.subheader("History")
                if "history" in completed:
                    _render_history_content(completed["history"])

    elif severity == "LOW" and "history" in completed:
        with st.expander("✅ Шаг 2 — History", expanded=False):
            _render_history_content(completed["history"])

    if "response" in completed:
        with st.expander("✅ Шаг 3 — Response Plan", expanded=False):
            _render_response_content(completed["response"])

    if "suggestion" in completed:
        with st.expander("✅ Шаг 3 — Suggestion", expanded=False):
            _render_suggestion_content(completed["suggestion"])

    if stage == "done" and "postmortem" in completed:
        with st.expander("✅ Шаг 4 — Postmortem", expanded=True):
            _render_postmortem_content(completed["postmortem"])


# ── Стриминговый запуск графа ──────────────────────────────────────────────────

def _stream_graph(alert: dict[str, Any], thread_id: str, resume: bool = False) -> None:
    """Запускает или возобновляет граф и обновляет UI в реальном времени."""
    config = {"configurable": {"thread_id": thread_id}}
    completed: dict[str, Any] = dict(st.session_state.completed)

    # ── Плейсхолдеры для live-обновлений ──────────────────────────────────────
    ph_step1 = st.empty()
    ph_step2 = st.empty()
    ph_step3 = st.empty()
    ph_approval = st.empty()
    ph_step4 = st.empty()

    # Ссылки на status-контейнеры второго шага (для fan-in)
    step2_status: Any = None
    step2_diag_ph: Any = None
    step2_hist_ph: Any = None
    step2_done: set[str] = set()

    if resume:
        # Показываем уже завершённые шаги компактно
        _render_completed_steps(completed, stage="resuming")
        ph_step4.status("⏳ Шаг 4 — Postmortem", state="running", expanded=True).write(
            "Формирую финальный постмортем..."
        )
    else:
        # Первый запуск: показываем шаг 1 как запущенный
        s1 = ph_step1.status("⏳ Шаг 1 — Triage", state="running", expanded=True)
        s1.write("Анализирую алерт, определяю severity...")

    # ── Стрим ─────────────────────────────────────────────────────────────────
    input_state = None if resume else IncidentState(alert=alert)
    try:
        for chunk in graph.stream(input_state, config, stream_mode="updates"):
            node_name = list(chunk.keys())[0]
            output: dict[str, Any] = chunk[node_name]
            completed[node_name] = output

            if node_name == "triage":
                sev = output.get("severity", "?")
                icon = SEV_ICON.get(sev, "⚪")
                s1 = ph_step1.status(
                    f"✅ Шаг 1 — Triage: {icon} {sev}",
                    state="complete", expanded=False,
                )
                with ph_step1.status(f"✅ Шаг 1 — Triage: {icon} {sev}", state="complete", expanded=False):
                    _render_triage_content(output)

                if sev in ("CRITICAL", "HIGH"):
                    step2_status = ph_step2.status(
                        "⏳ Шаг 2 — Diagnosis + History (параллельно ↕)",
                        state="running", expanded=True,
                    )
                    step2_status.write("🔀 Запущено параллельно:")
                    step2_diag_ph = step2_status.empty()
                    step2_hist_ph = step2_status.empty()
                    step2_diag_ph.write("⏳ **Diagnosis** — запрос к LLM...")
                    step2_hist_ph.write("⏳ **History** — поиск похожих инцидентов...")
                else:
                    ph_step2.status(
                        "⏳ Шаг 2 — History", state="running", expanded=True,
                    ).write("Ищу похожие инциденты...")

            elif node_name == "diagnosis":
                step2_done.add("diagnosis")
                if step2_diag_ph:
                    step2_diag_ph.write("✅ **Diagnosis** готов")
                if step2_hist_ph and "history" in step2_done:
                    _finalize_step2(ph_step2, step2_status, completed, ph_step3)

            elif node_name == "history":
                step2_done.add("history")
                severity = completed.get("triage", {}).get("severity", "")
                if severity in ("CRITICAL", "HIGH"):
                    if step2_hist_ph:
                        n = len(output.get("similar_incidents", []))
                        step2_hist_ph.write(f"✅ **History** — найдено {n} похожих инцидентов")
                    if "diagnosis" in step2_done:
                        _finalize_step2(ph_step2, step2_status, completed, ph_step3)
                else:
                    with ph_step2.status("✅ Шаг 2 — History", state="complete", expanded=False):
                        _render_history_content(output)
                    ph_step3.status("⏳ Шаг 3 — Suggestion", state="running", expanded=True).write(
                        "Формирую рекомендации..."
                    )

            elif node_name == "response":
                with ph_step3.status("✅ Шаг 3 — Response Plan", state="complete", expanded=False):
                    _render_response_content(output)

            elif node_name == "suggestion":
                with ph_step3.status("✅ Шаг 3 — Suggestion", state="complete", expanded=False):
                    _render_suggestion_content(output)

            elif node_name == "postmortem":
                with ph_step4.status("✅ Шаг 4 — Postmortem", state="complete", expanded=True):
                    _render_postmortem_content(output)

    except Exception as exc:
        st.session_state.error = str(exc)
        st.session_state.stage = "idle"
        return

    # ── После стрима: определяем следующую стадию ──────────────────────────────
    st.session_state.completed = completed
    snapshot = graph.get_state(config)

    if snapshot.next and "human_approval" in snapshot.next:
        st.session_state.stage = "awaiting_approval"
        with ph_approval.container():
            st.divider()
            st.warning("### ⚠️ Human Approval Required")
            st.markdown(
                "Проверьте план реагирования выше. Если план корректен и вы готовы его применить — "
                "подтвердите. После этого система зафиксирует инцидент в постмортеме."
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ План корректен, фиксируем", type="primary", use_container_width=True, key="approve_live"):
                    graph.update_state(config, {"human_approved": True})
                    st.session_state.stage = "resuming"
                    st.rerun()
            with col2:
                if st.button("❌ Reject", type="secondary", use_container_width=True, key="reject_live"):
                    st.session_state.stage = "rejected"
                    st.rerun()
    else:
        st.session_state.stage = "done"
        st.rerun()


def _finalize_step2(ph_step2: Any, step2_status: Any, completed: dict, ph_step3: Any) -> None:
    """Закрывает шаг 2 и открывает шаг 3 когда оба параллельных узла готовы."""
    with ph_step2.status("✅ Шаг 2 — Diagnosis + History", state="complete", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Diagnosis")
            if "diagnosis" in completed:
                _render_diagnosis_content(completed["diagnosis"])
        with c2:
            st.subheader("History")
            if "history" in completed:
                _render_history_content(completed["history"])
    ph_step3.status("⏳ Шаг 3 — Response Plan", state="running", expanded=True).write(
        "Агрегирую диагноз и историю, формирую план..."
    )


# ── Главный UI ─────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()

    st.set_page_config(
        page_title="Incident Response Autopilot",
        page_icon="🚨",
        layout="wide",
    )
    st.title("🚨 Incident Response Autopilot")

    stage = st.session_state.stage

    # ── Боковая панель ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Alert Input")

        if stage != "idle":
            if st.button("🔄 Сбросить", use_container_width=True):
                _reset()

        preset = st.selectbox(
            "Пресет", ["— кастомный —", *SAMPLE_ALERTS.keys()],
            disabled=(stage not in ("idle",)),
        )
        default_json = json.dumps(
            SAMPLE_ALERTS.get(preset, {
                "id": "alert-000", "service": "my-service",
                "message": "Something went wrong",
            }),
            ensure_ascii=False, indent=2,
        )
        alert_json = st.text_area(
            "Alert JSON", value=default_json, height=220,
            disabled=(stage not in ("idle",)),
        )

        run_clicked = st.button(
            "▶ Run Analysis", type="primary",
            use_container_width=True,
            disabled=(stage not in ("idle",)),
        )
        if run_clicked:
            try:
                alert = json.loads(alert_json)
            except json.JSONDecodeError as exc:
                st.error(f"Невалидный JSON: {exc}")
                st.stop()
            st.session_state.pending_alert = alert
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.completed = {}
            st.session_state.stage = "running"
            st.rerun()

    # ── Основная панель ────────────────────────────────────────────────────────
    if st.session_state.error:
        st.error(f"Ошибка: {st.session_state.error}")
        if st.button("Сбросить"):
            _reset()
        st.stop()

    if stage == "idle":
        st.info("Выберите алерт в боковой панели и нажмите **▶ Run Analysis**.")
        st.stop()

    if stage == "running":
        st.caption("⚙️ Граф запущен — обновления в реальном времени")
        _stream_graph(
            alert=st.session_state.pending_alert,
            thread_id=st.session_state.thread_id,
            resume=False,
        )
        st.stop()

    if stage == "resuming":
        st.caption("⚙️ Возобновляю граф после апрува...")
        _stream_graph(
            alert=st.session_state.pending_alert,
            thread_id=st.session_state.thread_id,
            resume=True,
        )
        st.stop()

    if stage == "awaiting_approval":
        _render_completed_steps(st.session_state.completed, stage="awaiting_approval")
        st.divider()
        st.warning("### ⚠️ Human Approval Required")
        st.markdown(
            "Проверьте план реагирования выше. Если план корректен и вы готовы его применить — "
            "подтвердите. После этого система зафиксирует инцидент в постмортеме."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ План корректен, фиксируем", type="primary", use_container_width=True):
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                graph.update_state(config, {"human_approved": True})
                st.session_state.stage = "resuming"
                st.rerun()
        with col2:
            if st.button("❌ Reject", type="secondary", use_container_width=True):
                st.session_state.stage = "rejected"
                st.rerun()
        st.stop()

    if stage == "done":
        _render_completed_steps(st.session_state.completed, stage="done")
        completed = st.session_state.completed
        metrics: dict[str, Any] = {}
        for output in completed.values():
            metrics.update(output.get("metrics", {}))
        if metrics:
            st.divider()
            st.caption("**Latency per agent (s)**")
            cols = st.columns(len(metrics))
            for col, (agent, m) in zip(cols, metrics.items()):
                if isinstance(m, dict):
                    col.metric(agent, f"{m.get('latency_s', '?')}s")
        st.stop()

    if stage == "rejected":
        _render_completed_steps(st.session_state.completed, stage="rejected")
        st.error("Инцидент отклонён инженером. Постмортем не создан.")
        st.stop()


if __name__ == "__main__":
    main()
