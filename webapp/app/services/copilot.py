"""Copiloto SRE: le pide a Claude que interprete las métricas en lenguaje natural."""
import json
import logging

import anthropic

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres el copiloto SRE de OpsCenter, una app Flask detrás de Nginx con MySQL, \
monitoreada con Prometheus, Node Exporter y Grafana, todo en Docker Compose.

Recibes una instantánea de métricas reales, las alertas activas y una evaluación previa \
hecha por un motor de reglas. Tu trabajo es explicar el estado del sistema a un estudiante \
de servicios telemáticos y proponer acciones concretas.

Responde en español y en Markdown con exactamente estas secciones:
## Diagnóstico
## Riesgos
## Acciones recomendadas

Usa comandos reales cuando ayuden (docker compose, consultas PromQL). Basa cada afirmación \
en los datos recibidos: si una métrica es null, dilo en vez de suponer su valor. \
Si el usuario hace una pregunta, respóndela primero dentro del diagnóstico. \
Mantén la respuesta por debajo de 250 palabras."""


class CopilotUnavailable(RuntimeError):
    pass


def ask_claude(api_key, model, effort, snapshot, health, question=""):
    """Devuelve (markdown, modelo_que_respondió). Lanza CopilotUnavailable si falla."""
    payload = {
        "metricas": snapshot.get("metrics", {}),
        "alertas": snapshot.get("alerts", []),
        "evaluacion_reglas": health,
    }
    content = "Instantánea del sistema:\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
    if question:
        content += f"\n\nPregunta del usuario: {question}"

    client = anthropic.Anthropic(api_key=api_key, timeout=90.0, max_retries=2)
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            output_config={"effort": effort},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            # Si el modelo declina, la API reintenta con el respaldo recomendado.
            extra_body={"fallbacks": "default"},
        )
    except anthropic.AuthenticationError as exc:
        raise CopilotUnavailable("La clave de Anthropic no es válida.") from exc
    except anthropic.RateLimitError as exc:
        raise CopilotUnavailable("Límite de uso de la API alcanzado, intenta más tarde.") from exc
    except anthropic.APIStatusError as exc:
        log.warning("Error de la API de Claude (%s): %s", exc.status_code, exc.message)
        raise CopilotUnavailable(f"La API de Claude respondió {exc.status_code}.") from exc
    except anthropic.APIConnectionError as exc:
        raise CopilotUnavailable("No hay conexión con la API de Claude.") from exc

    if response.stop_reason == "refusal":
        raise CopilotUnavailable("El modelo declinó responder esta solicitud.")

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise CopilotUnavailable("El modelo no devolvió texto.")
    return text, response.model
