"""Respuestas conversacionales para staff con contexto de SirgioBOT."""

import google.generativeai as genai

import config
from services.gemini_evaluator import _generate_with_retry, format_api_error
from services.sirgiobot_knowledge import get_sirgiobot_knowledge

__all__ = ["format_api_error", "reply_to_staff"]


def _load_chat_prompt() -> str:
    path = config.STAFF_CHAT_PROMPT_PATH
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Eres un asistente de staff de Discord."


def _build_system_instruction() -> str:
    knowledge = get_sirgiobot_knowledge()
    base = _load_chat_prompt()
    return f"{base}\n\n## Referencia SirgioBOT\n\n{knowledge[:14000]}"


def reply_to_staff(
    staff_name: str,
    staff_role: str,
    messages: list[str],
    channel_label: str,
) -> str:
    api_key = config.GEMINI_API_KEY_2 or config.GEMINI_API_KEY
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=_build_system_instruction(),
    )

    if len(messages) == 1:
        user_block = messages[0]
    else:
        lines = [f"{i}. {m}" for i, m in enumerate(messages, 1)]
        user_block = "Mensajes del staff (en orden):\n" + "\n".join(lines)

    prompt = f"""Contexto:
- Staff: {staff_name}
- Rol: {staff_role}
- Canal: {channel_label}

Mensaje(s):
{user_block}

Responde al staff en español. Si aplica, sugiere comandos concretos de SirgioBOT."""

    response = _generate_with_retry(
        model,
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.45),
    )
    text = (response.text or "").strip()
    if not text:
        raise ValueError("Gemini devolvió una respuesta vacía")
    return text


def split_discord_message(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()
    return chunks
