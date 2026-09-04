# Lychnia

App de escritorio (Linux, Windows, macOS) para producir las prédicas dominicales de la
Iglesia de Tunja: de tres grabaciones de OBS a video multicámara con versículos, subtítulos,
shorts, miniatura y textos para YouTube y el blog. Funciona sin internet y con el hardware
que haya (usa GPU si existe, degrada a CPU si no).

**Lychnia** (λυχνία, «lik-NÍ-a») es la palabra griega para «candelero», la de Mateo 5:15:
la luz no se pone debajo de un almud «sino sobre el candelero, y alumbra a todos los que
están en casa». La app toma el mensaje predicado y lo pone donde todos lo vean: web,
YouTube y redes.

## Estado

**Fase de diseño (septiembre 2026).** Existe la spec del primer sub-proyecto, el Motor.
No hay código todavía. El pipeline que se va a convertir en app vive y funciona hoy en
`~/Repositorios/multimedia-iglesia-tunja` (Make + scripts Python + Claude Code como
orquestador); Lychnia lo reemplaza con un orquestador propio, una API local y una
interfaz de escritorio.

## Mapa

```
lychnia/
├── CLAUDE.md                      # cómo trabajar en este repo (para Claude Code)
├── README.md                      # esto
├── docs/
│   ├── CONTEXTO.md                # de dónde viene, qué produce, reglas duras, decisiones
│   ├── PIPELINE-ACTUAL.md         # el pipeline hoy: scripts, proyecto.toml, grafo del Makefile
│   ├── BITACORA.md                # memoria entre sesiones
│   ├── spikes/2026-09-03-viabilidad.md   # LLM local, empaquetado, licencia RVR1960
│   └── superpowers/specs/
│       └── 2026-09-04-motor-design.md    # ⭐ spec del Motor (sub-proyecto 1)
├── motor/                         # (próximo) paquete Python `lychnia`: orquestador + API + tareas + recursos de marca
└── app/                           # (después) Tauri + UI web
```

## Sub-proyectos, en orden

1. **Motor**: orquestador Python + API local + tareas migradas del pipeline. Spec lista.
2. **Proveedores de IA**: Transcriptor, Redactor (LLM local por trozos o API), Biblia, Detector.
3. **Cáscara**: Tauri + UI web con los dos Gates como pantallas de revisión.
4. **Distribución**: instaladores por SO, paquete de modelos, detección de hardware.

## Para retomar con Claude Code

Abrir una sesión en esta carpeta. `CLAUDE.md` le dice qué leer.
