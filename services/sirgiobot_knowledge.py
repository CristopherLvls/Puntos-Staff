"""Carga y sincronización del conocimiento de comandos de SirgioBOT."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import config

logger = logging.getLogger("insight_ia.sirgiobot_knowledge")

_cache: str | None = None
_cache_at: datetime | None = None


def _read_local() -> str:
    path = config.SIRGIOBOT_KNOWLEDGE_PATH
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _fetch_remote_readme() -> str:
    url = config.SIRGIOBOT_README_URL
    with urlopen(url, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_sirgiobot_knowledge(force_refresh: bool = False) -> str:
    global _cache, _cache_at

    if _cache and not force_refresh:
        return _cache

    local = _read_local()
    remote = ""

    if config.SIRGIOBOT_SYNC_KNOWLEDGE:
        try:
            remote = _fetch_remote_readme()
            logger.info("README de SirgioBOT sincronizado desde GitHub")
        except Exception as exc:
            logger.warning("No se pudo sincronizar SirgioBOT desde GitHub: %s", exc)

    if remote and len(remote) > 500:
        _cache = f"{local}\n\n---\n\n## README SirgioBOT (GitHub)\n\n{remote[:12000]}"
    else:
        _cache = local

    _cache_at = datetime.now(timezone.utc)
    return _cache


def knowledge_summary() -> str:
    text = get_sirgiobot_knowledge()
    synced = _cache_at.isoformat() if _cache_at else "nunca"
    return f"Caracteres cargados: {len(text)} | Última carga: {synced}"
