# Insight IA — Bot de evaluación de staff

Bot de Discord en Python que lee logs de **SirgioBOT** (solo lectura), evalúa el desempeño del staff con **Gemini** y guarda puntuaciones en **MongoDB Cluster0**. Pensado para desplegarse en **Render** como Background Worker.

## Roles de staff (configurados)

| Rol | ID de Discord |
|-----|----------------|
| Helper | `1522373412880646288` |
| Moderador | `1510511672563994674` |
| Tester | `1522373488990752869` |

## Comandos

| Comando | Quién | Descripción |
|---------|-------|-------------|
| `/evaluar` | Admin | Evalúa a un staff (logs + IA + guarda en Cluster0) |
| `/puntos` | Staff / Admin | Promedio y reputación acumulada |
| `/historial` | Staff / Admin | Últimas evaluaciones |
| `/consejos` | Staff / Admin | Consejos para mejorar puntaje |

## Configuración local

1. Crea un bot en [Discord Developer Portal](https://discord.com/developers/applications) y copia el token.
2. Obtén API key gratis en [Google AI Studio](https://aistudio.google.com/apikey).
3. Copia `.env.example` a `.env` y completa:

```bash
cp .env.example .env
```

Variables obligatorias:

- `DISCORD_TOKEN`
- `DISCORD_GUILD_ID` — ID de tu servidor (sync rápido de slash)
- `GEMINI_API_KEY`
- `MONGODB_READONLY_URI` — URI de SirgioBOT (usuario solo lectura recomendado)
- `MONGODB_WRITE_URI` — URI de Cluster0
- `ADMIN_ROLE_IDS` — IDs de roles que pueden `/evaluar`, separados por coma

4. Inspecciona el esquema de logs de SirgioBOT:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/inspect_sirgio_schema.py
```

Si la colección de logs no se llama `logs`, ajusta `MONGODB_LOGS_COLLECTION` en `.env`.

5. Ejecuta el bot:

```bash
python bot.py
```

## Despliegue en Render

1. Sube el proyecto a GitHub.
2. En Render: **New → Blueprint** o **Background Worker**.
3. Conecta el repo; Render usará `render.yaml`.
4. Añade las variables secretas en **Environment** (mismas que `.env`).
5. En MongoDB Atlas, permite acceso desde cualquier IP (`0.0.0.0/0`) o las IPs de Render.
6. Invita el bot con scope `bot` + `applications.commands`.

## Seguridad

- No subas `.env` al repositorio.
- Usa un usuario de Atlas **solo lectura** para SirgioBOT.
- Si expusiste credenciales en chat, **rótalas** en Atlas.

## Estructura

```
bot.py              # Entrada principal
config.py           # Env y mapa de roles
commands/           # Slash commands
services/           # Mongo, logs, Gemini
prompts/            # Prompt del evaluador
scripts/            # Inspección de BD SirgioBOT
render.yaml         # Deploy Render
```
# Puntos-Staff
