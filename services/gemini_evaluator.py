import json
import re
import google.generativeai as genai

import config

REPUTATION_BY_POINTS = [
    (8, 10, "Excelente"),
    (7, 7, "Estándar"),
    (5, 6, "Bajo"),
    (1, 4, "Mala Reputación"),
    (-5, 0, "Muy Mala Reputación"),
]


def _load_system_prompt() -> str:
    path = config.PROMPT_PATH
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Eres un evaluador de desempeño de staff de Discord."


def _normalize_reputation(points: float, status: str) -> str:
    for low, high, label in REPUTATION_BY_POINTS:
        if low <= points <= high:
            return label
    return status or "Bajo"


def _clamp_points(points: float) -> float:
    return max(-5, min(10, points))


def evaluate_staff(
    staff_name: str,
    staff_discord_id: str,
    role: str,
    logs_summary: str,
    period_days: int,
    log_count: int,
) -> dict:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=_load_system_prompt(),
    )

    user_prompt = f"""Evalúa al siguiente miembro del staff.

Staff: {staff_name} (Discord ID: {staff_discord_id})
Rol en el servidor: {role}
Periodo de evaluación: últimos {period_days} días
Cantidad de logs analizados: {log_count}

--- LOGS DE ACTIVIDAD ---
{logs_summary}
--- FIN LOGS ---

Responde solo con el JSON indicado en las instrucciones del sistema."""

    response = model.generate_content(
        user_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    raw = response.text.strip()
    data = _parse_json(raw)
    points = _clamp_points(float(data.get("points", 5)))
    reputation = _normalize_reputation(points, data.get("reputation_status", ""))

    advice = data.get("advice", [])
    if isinstance(advice, str):
        advice = [advice]
    if len(advice) < 3:
        advice = advice + [
            "Responde más rápido cuando un usuario necesite ayuda.",
            "Mantén un tono respetuoso y empático en cada interacción.",
            "Documenta o cierra los casos hasta confirmar que el problema quedó resuelto.",
        ]
    advice = advice[:5]

    return {
        "staff_name": data.get("staff_name", staff_name),
        "staff_discord_id": str(data.get("staff_discord_id", staff_discord_id)),
        "role": data.get("role", role),
        "points": points,
        "reputation_status": reputation,
        "justification": data.get("justification", "Evaluación basada en logs del periodo."),
        "advice": advice,
    }


def generate_advice_only(
    staff_name: str,
    staff_discord_id: str,
    role: str,
    recent_evaluations: list[dict],
) -> list[str]:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name=config.GEMINI_MODEL)

    history = json.dumps(
        [
            {
                "points": e.get("points"),
                "reputation": e.get("reputation_status"),
                "justification": e.get("justification"),
            }
            for e in recent_evaluations
        ],
        ensure_ascii=False,
    )

    prompt = f"""Eres mentor de staff de Discord. Basándote en el historial de evaluaciones,
da entre 4 y 6 consejos MUY concretos para que {staff_name} ({role}) mejore su puntaje y reputación.

Historial:
{history}

Responde JSON: {{"advice": ["...", "..."]}}"""

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.5,
        ),
    )
    data = _parse_json(response.text.strip())
    advice = data.get("advice", [])
    return advice if isinstance(advice, list) else [str(advice)]


def format_evaluation_text(result: dict) -> str:
    return (
        f"**Staff Evaluado:** {result['staff_name']} (`{result['staff_discord_id']}`)\n"
        f"**Rol:** {result['role']}\n"
        f"**Puntos Asignados:** {result['points']}\n"
        f"**Estatus de Reputación:** {result['reputation_status']}\n"
        f"**Justificación Breve:** {result['justification']}"
    )


def format_advice_text(advice: list[str]) -> str:
    lines = [f"• {a}" for a in advice]
    return "**Consejos para mejorar:**\n" + "\n".join(lines)


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("Gemini no devolvió JSON válido") from None
