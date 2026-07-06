# SirgioBOT — Referencia de comandos y módulos

Fuente: https://github.com/CristopherAFK/SirgioBOT01

SirgioBOT es el bot principal del servidor de Sirgio. Incluye tickets (LagSupport), moderación, sugerencias, autoroles, bienvenidas, YouTube RSS, auditoría y automod.

## Prefijo `!` — Staff

| Comando | Uso |
|---------|-----|
| `!Tpanel` | Publica el panel interactivo de tickets LagSupport en el canal actual |
| `!cerrar` | Cierra el ticket actual: envía valoración al usuario y guarda transcripción |
| `!autoroles` | Publica los 4 paneles de autoroles con banners y reacciones (país, género, juegos, notificaciones) |

## Slash — Todos los miembros

| Comando | Descripción |
|---------|-------------|
| `/sugerir` | Enviar una sugerencia al servidor (con votos; el staff la revisa) |
| `/help` | Lista resumida de comandos de SirgioBOT |
| `/avatar [usuario]` | Ver avatar de un usuario |
| `/banner [usuario]` | Ver banner de un usuario |
| `/userinfo [usuario]` | Información del usuario (warns, roles, fechas) |
| `/serverinfo` | Información del servidor |

## Slash — Solo staff

### Moderación

| Comando | Parámetros | Descripción |
|---------|------------|-------------|
| `/sancion` | usuario, tipo (warn/mute/ban), razón (categoría), detalle, tiempo (10m/1h/7d), pruebas | Aplica warn, mute o ban con caso en MongoDB |
| `/removemute` | usuario | Quita el mute a un usuario |
| `/unban` | usuario | Desbanea a un usuario |
| `/warnlist` | usuario | Ver advertencias activas del usuario |
| `/removewarn` | usuario, cantidad (opcional) | Remover warns del usuario |
| `/historial` | usuario | Historial de sanciones (últimos casos) |
| `/case` | id (ej. 0042) | Detalle de un caso por ID |
| `/limpiarwarns` | usuario | Elimina todos los warns de un usuario |

**Formato de tiempo en `/sancion`:** `10m`, `1h`, `2d`, etc. Obligatorio para mute y ban.

### Mensajes y embeds

| Comando | Descripción |
|---------|-------------|
| `/say` | Envía texto a un canal (abre modal para escribir el mensaje) |
| `/saydm` | Envía texto por DM a un usuario (modal) |
| `/embed` | Embed personalizado en un canal: título, descripción, color hex (#FF5500), imagen URL (modal) |
| `/embeddm` | Embed personalizado por DM (modal) |
| `/staffcmds` | Ayuda de comandos de mensajes y autoroles |

### Guías

| Comando | Descripción |
|---------|-------------|
| `/guia` | Guía completa del staff (tickets, autoroles, sanciones, automod, auditoría) |

## Tickets (LagSupport)

1. Staff publica `!Tpanel` en el canal de tickets.
2. El usuario abre ticket eligiendo categoría.
3. Staff puede pulsar **Atender** en el ticket.
4. Al cerrar con `!cerrar`, el usuario recibe valoración (estrellas) y se guarda transcripción en MongoDB (`ticketreviews`, `pendingreviews`).

## Autoroles (`!autoroles`)

Publica 4 paneles:
1. **Países** — un solo país a la vez (exclusivo)
2. **Género** — una opción a la vez (exclusivo)
3. **Videojuegos** — varios roles permitidos
4. **Notificaciones** — varios roles permitidos

Los usuarios reaccionan con emoji para obtener o quitar roles.

## Sugerencias

- Usuarios: `/sugerir` en el canal designado.
- Staff revisa en canal de staff: Aprobar / Rechazar / Pendiente con respuesta personalizada.

## Automod

- Filtra palabras prohibidas, spam (+5 mensajes), flood (+7 líneas) y enlaces (excepto GIFs permitidos).
- 3 warns automáticos → mute progresivo (10m → 2h máximo).
- Los usuarios pueden apelar sanciones desde MD.

## Colecciones MongoDB (para métricas)

| Colección | Contenido |
|-----------|-----------|
| `auditlogs` | Timeline: auditoría, comandos, tickets, sugerencias, automod, acciones staff (`actorId`, `action`, `at`) |
| `modcases` | Sanciones warn/mute/ban (`moderatorId`, `createdAt`) |
| `ticketreviews` | Tickets cerrados y valorados (`closedBy`, `attendedBy`) |
| `suggestions` | Sugerencias (`modId` del staff que respondió) |

## Insight IA (este bot)

Comandos propios del bot de evaluación:
- `/evaluar` — Evalúa desempeño de staff con IA (solo admins)
- `/puntos` — Puntos y reputación acumulada
- `/historial` — Últimas evaluaciones de Insight IA
- `/consejos` — Consejos de mejora con IA
- `/diagnostico_logs` — Diagnóstico de conexión a logs SirgioBOT (admins)
