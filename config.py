import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

MONGODB_READONLY_URI = os.getenv("MONGODB_READONLY_URI", "")
MONGODB_READONLY_DB = os.getenv("MONGODB_READONLY_DB", "sirgiobot")
MONGODB_LOGS_COLLECTION = os.getenv("MONGODB_LOGS_COLLECTION", "logs")

MONGODB_WRITE_URI = os.getenv("MONGODB_WRITE_URI", "")
MONGODB_WRITE_DB = os.getenv("MONGODB_WRITE_DB", "insight_ia")

ADMIN_ROLE_IDS = {
    int(r.strip())
    for r in os.getenv("ADMIN_ROLE_IDS", "").split(",")
    if r.strip().isdigit()
}

ROLE_HELPER_ID = int(os.getenv("ROLE_HELPER_ID", "1522373412880646288"))
ROLE_MODERATOR_ID = int(os.getenv("ROLE_MODERATOR_ID", "1510511672563994674"))
ROLE_TESTER_ID = int(os.getenv("ROLE_TESTER_ID", "1522373488990752869"))

STAFF_ROLE_MAP: dict[int, str] = {
    ROLE_HELPER_ID: "Helper",
    ROLE_MODERATOR_ID: "Moderador",
    ROLE_TESTER_ID: "Tester",
}

STAFF_ROLE_IDS = set(STAFF_ROLE_MAP.keys())
_extra_staff_ids = os.getenv("STAFF_ROLE_IDS", "")
if _extra_staff_ids:
    STAFF_ROLE_IDS.update(
        int(r.strip()) for r in _extra_staff_ids.split(",") if r.strip().isdigit()
    )

# Fallback por nombre si los IDs de env no coinciden con el servidor
STAFF_ROLE_NAMES = {name.lower() for name in STAFF_ROLE_MAP.values()} | {"mod"}

PROMPT_PATH = BASE_DIR / "prompts" / "staff_evaluator.md"
MAX_LOGS_FOR_AI = int(os.getenv("MAX_LOGS_FOR_AI", "150"))
MAX_LOG_TEXT_CHARS = int(os.getenv("MAX_LOG_TEXT_CHARS", "28000"))


def get_staff_role_name(member) -> str:
    """Devuelve el rol de staff más alto según prioridad: Mod > Tester > Helper."""
    role_ids = {r.id for r in member.roles}
    if ROLE_MODERATOR_ID in role_ids:
        return "Moderador"
    if ROLE_TESTER_ID in role_ids:
        return "Tester"
    if ROLE_HELPER_ID in role_ids:
        return "Helper"

    for role in member.roles:
        name = role.name.lower()
        if name in ("moderador", "mod"):
            return "Moderador"
        if name == "tester":
            return "Tester"
        if name == "helper":
            return "Helper"

    return "Staff"


def member_has_staff_role(member) -> bool:
    role_ids = {r.id for r in member.roles}
    if role_ids & STAFF_ROLE_IDS:
        return True
    return any(r.name.lower() in STAFF_ROLE_NAMES for r in member.roles)


def validate_config() -> list[str]:
    errors = []
    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN")
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY")
    if not MONGODB_READONLY_URI:
        errors.append("MONGODB_READONLY_URI")
    if not MONGODB_WRITE_URI:
        errors.append("MONGODB_WRITE_URI")
    return errors
