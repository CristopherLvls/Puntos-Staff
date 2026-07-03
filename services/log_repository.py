"""Consulta flexible de logs de staff en SirgioBOT (solo lectura)."""

from datetime import datetime, timezone
from typing import Any

import config
from services.mongo_read import get_logs_collection, get_read_db

# Campos planos donde puede aparecer el ID del staff que actuó
STAFF_ID_FIELDS = (
    "staffId",
    "staff_id",
    "moderatorId",
    "moderator_id",
    "executorId",
    "executor_id",
    "modId",
    "mod_id",
    "authorId",
    "author_id",
    "actorId",
    "actor_id",
    "performerId",
    "performer_id",
    "adminId",
    "admin_id",
    "handlerId",
    "handler_id",
    "memberId",
    "member_id",
    "discordId",
    "discord_id",
    "userId",
    "user_id",
    "performedBy",
    "performed_by",
)

NESTED_ACTOR_PATHS = (
    "staff",
    "moderator",
    "mod",
    "executor",
    "author",
    "actor",
    "performer",
    "by",
    "user",
    "admin",
    "handler",
    "data",
    "metadata",
)

NESTED_ID_KEYS = (
    "id",
    "userId",
    "user_id",
    "discordId",
    "discord_id",
    "discordID",
    "staffId",
    "staff_id",
)

TIMESTAMP_FIELDS = ("timestamp", "createdAt", "created_at", "date", "time", "loggedAt")


def _extra_staff_fields() -> tuple[str, ...]:
    return tuple(f.strip() for f in config.LOG_STAFF_ID_FIELDS.split(",") if f.strip())


def _staff_id_query(staff_discord_id: str) -> dict:
    sid = str(staff_discord_id)
    or_clauses: list[dict] = []

    all_fields = STAFF_ID_FIELDS + _extra_staff_fields()
    for field in all_fields:
        or_clauses.append({field: sid})
        if sid.isdigit():
            or_clauses.append({field: int(sid)})

    for path in NESTED_ACTOR_PATHS:
        for key in NESTED_ID_KEYS:
            dotted = f"{path}.{key}"
            or_clauses.append({dotted: sid})
            if sid.isdigit():
                or_clauses.append({dotted: int(sid)})

    return {"$or": or_clauses}


def _parse_timestamp(doc: dict) -> datetime | None:
    for field in TIMESTAMP_FIELDS:
        if field not in doc:
            continue
        val = doc[field]
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        if isinstance(val, (int, float)):
            ts = val / 1000 if val > 1e12 else val
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _doc_contains_id(doc: dict, sid: str) -> bool:
    def walk(obj: Any) -> bool:
        if isinstance(obj, dict):
            return any(walk(v) for v in obj.values())
        if isinstance(obj, list):
            return any(walk(v) for v in obj)
        return str(obj) == sid

    return walk(doc)


def _filter_by_since(docs: list[dict], since: datetime) -> list[dict]:
    since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
    filtered: list[dict] = []
    for doc in docs:
        ts = _parse_timestamp(doc)
        if ts and ts < since_aware:
            continue
        filtered.append(doc)
    return filtered


def _scan_recent_for_staff(staff_discord_id: str, since: datetime, limit: int) -> list[dict]:
    """Fallback: busca el ID en cualquier campo de documentos recientes."""
    col = get_logs_collection()
    sid = str(staff_discord_id)
    scan_limit = min(limit * 15, 3000)
    cursor = col.find({}).sort("_id", -1).limit(scan_limit)

    matches: list[dict] = []
    for doc in cursor:
        if not _doc_contains_id(doc, sid):
            continue
        matches.append(doc)
        if len(matches) >= limit * 3:
            break

    return _filter_by_since(matches, since)[:limit]


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
    query = _staff_id_query(staff_discord_id)

    cursor = col.find(query).sort("_id", -1).limit(limit * 3)
    results = _filter_by_since(list(cursor), since)[:limit]

    if not results:
        results = _scan_recent_for_staff(staff_discord_id, since, limit)

    return results


def diagnose_empty_logs(staff_discord_id: str | None, since: datetime) -> str:
    """Información útil cuando no hay logs para un staff."""
    db = get_read_db()
    col_name = config.MONGODB_LOGS_COLLECTION
    lines = [f"BD: `{config.MONGODB_READONLY_DB}` | Colección: `{col_name}`"]
    if staff_discord_id:
        lines.append(f"Discord ID buscado: `{staff_discord_id}`")

    try:
        collections = db.list_collection_names()
        lines.append(f"Colecciones en la BD: {', '.join(collections) or '(ninguna)'}")
    except Exception as exc:
        lines.append(f"No se pudo listar colecciones: {exc}")
        return "\n".join(lines)

    if col_name not in collections:
        lines.append(
            f"La colección `{col_name}` **no existe**. "
            "Revisa `MONGODB_LOGS_COLLECTION` en Render."
        )
        if collections:
            lines.append(f"Prueba con una de estas: {', '.join(collections)}")
        return "\n".join(lines)

    col = get_logs_collection()
    try:
        total = col.count_documents({})
        lines.append(f"Documentos en `{col_name}`: {total}")
    except Exception as exc:
        lines.append(f"No se pudo contar documentos: {exc}")
        total = 0

    if total == 0:
        lines.append(
            "La colección está vacía o `MONGODB_READONLY_URI` apunta al cluster equivocado "
            "(debe ser el de SirgioBOT, no el de Insight IA)."
        )
        return "\n".join(lines)

    sample = col.find_one(sort=[("_id", -1)])
    if sample:
        keys = [k for k in sample.keys() if k != "_id"]
        lines.append(f"Campos del último log: `{', '.join(keys[:12])}`")

    if not staff_discord_id:
        return "\n".join(lines)

    sid = str(staff_discord_id)
    structured = col.count_documents(_staff_id_query(sid))
    lines.append(f"Logs con consulta estructurada para este ID: {structured}")

    scan_matches = _scan_recent_for_staff(sid, since, limit=5)
    lines.append(f"Logs encontrados por escaneo reciente: {len(scan_matches)}")

    if structured == 0 and not scan_matches:
        lines.append(
            "Sugerencia: verifica que `MONGODB_READONLY_URI` sea el cluster de **SirgioBOT**, "
            "aumenta los días de búsqueda, o define `LOG_STAFF_ID_FIELDS` con el campo correcto."
        )

    return "\n".join(lines)


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
