"""Consulta flexible de logs de staff en SirgioBOT (solo lectura)."""

from datetime import datetime, timezone
from typing import Any

import config
from services.mongo_read import get_logs_collection

# Campos donde puede aparecer el ID del staff que actuó
STAFF_ID_FIELDS = (
    "staffId",
    "staff_id",
    "moderatorId",
    "moderator_id",
    "executorId",
    "executor_id",
    "userId",
    "user_id",
    "modId",
    "mod_id",
    "authorId",
    "author_id",
    "targetId",
    "target_id",
)

TIMESTAMP_FIELDS = ("timestamp", "createdAt", "created_at", "date", "time", "loggedAt")


def _staff_id_query(staff_discord_id: str) -> dict:
    sid = str(staff_discord_id)
    or_clauses = [{field: sid} for field in STAFF_ID_FIELDS]
    if sid.isdigit():
        or_clauses.extend([{field: int(sid)} for field in STAFF_ID_FIELDS])
    # Algunos bots guardan el ID anidado
    or_clauses.extend(
        [
            {"staff.id": sid},
            {"moderator.id": sid},
            {"executor.id": sid},
            {"user.id": sid},
        ]
    )
    if sid.isdigit():
        for nested in ("staff.id", "moderator.id", "executor.id", "user.id"):
            or_clauses.append({nested: int(sid)})
    return {"$or": or_clauses}


def _parse_timestamp(doc: dict) -> datetime | None:
    for field in TIMESTAMP_FIELDS:
        if field not in doc:
            continue
        val = doc[field]
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        if isinstance(val, (int, float)):
            # ms o segundos
            ts = val / 1000 if val > 1e12 else val
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def find_staff_logs(
    staff_discord_id: str,
    since: datetime,
    limit: int | None = None,
) -> list[dict]:
    """
    Busca logs donde el staff aparece como actor.
    Filtra por fecha en Python si el campo de tiempo varía entre documentos.
    """
    limit = limit or config.MAX_LOGS_FOR_AI
    col = get_logs_collection()

    query: dict[str, Any] = _staff_id_query(staff_discord_id)

    # Intento filtrar en Mongo si existe timestamp conocido
    since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
    cursor = col.find(query).sort("_id", -1).limit(limit * 3)

    results: list[dict] = []
    for doc in cursor:
        ts = _parse_timestamp(doc)
        if ts and ts < since_aware:
            continue
        if not ts:
            # Sin fecha: incluir en ventana reciente por _id
            results.append(doc)
        else:
            results.append(doc)
        if len(results) >= limit:
            break

    return results


def summarize_logs_for_ai(logs: list[dict]) -> str:
    """Convierte logs a texto compacto para Gemini."""
    lines: list[str] = []
    total_chars = 0

    for i, doc in enumerate(logs, 1):
        ts = _parse_timestamp(doc)
        ts_str = ts.isoformat() if ts else "sin_fecha"
        action = (
            doc.get("action")
            or doc.get("type")
            or doc.get("event")
            or doc.get("logType")
            or "evento"
        )
        content = (
            doc.get("content")
            or doc.get("message")
            or doc.get("description")
            or doc.get("reason")
            or doc.get("details")
            or ""
        )
        extra = {k: v for k, v in doc.items() if k not in ("_id", "content", "message")}
        line = f"[{i}] {ts_str} | {action} | {content} | meta={_compact(extra)}"
        if total_chars + len(line) > config.MAX_LOG_TEXT_CHARS:
            lines.append(f"... ({len(logs) - i + 1} logs omitidos por límite de contexto)")
            break
        lines.append(line)
        total_chars += len(line)

    if not lines:
        return "(No se encontraron logs para este periodo.)"
    return "\n".join(lines)


def _compact(obj: dict, max_len: int = 200) -> str:
    text = str(obj)
    return text[:max_len] + "..." if len(text) > max_len else text
