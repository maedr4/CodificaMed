"""Clientes de modelos de lenguaje. El proveedor se elige en la configuración."""
import time

import requests

from .config import Config


class ErrorLLM(Exception):
    pass


def _ollama(cfg: Config, sistema: str, prompt: str) -> str:
    respuesta = requests.post(
        f"{cfg.ollama_url}/api/chat",
        json={
            "model": cfg.ollama_modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=cfg.timeout,
    )
    respuesta.raise_for_status()
    return respuesta.json()["message"]["content"]


def _claude(cfg: Config, sistema: str, prompt: str) -> str:
    if not cfg.anthropic_api_key:
        raise ErrorLLM("Falta ANTHROPIC_API_KEY en el archivo .env")
    respuesta = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": cfg.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": cfg.anthropic_modelo,
            "max_tokens": 1024,
            "system": sistema,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=cfg.timeout,
    )
    if respuesta.status_code != 200:
        raise ErrorLLM(f"Claude respondió {respuesta.status_code}: {respuesta.text[:300]}")
    return "".join(b.get("text", "") for b in respuesta.json()["content"] if b.get("type") == "text")


def _formato_openai(nombre, url, clave, modelo, timeout, sistema, prompt, formato_json=True) -> str:
    """Cliente para cualquier servicio con el formato de chat de OpenAI."""
    cuerpo = {
        "model": modelo,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": prompt}],
        "temperature": 0,
    }
    if formato_json:
        cuerpo["response_format"] = {"type": "json_object"}
    # Los planes gratuitos responden 429 o 503 cuando hay mucha demanda; se reintenta con espera creciente
    for intento in range(4):
        respuesta = requests.post(
            f"{url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {clave}"},
            json=cuerpo,
            timeout=timeout,
        )
        # Un límite diario agotado no se recupera esperando unos segundos
        if respuesta.status_code not in (429, 503) or "per day" in respuesta.text:
            break
        time.sleep(10 * (intento + 1))
    if respuesta.status_code != 200:
        raise ErrorLLM(f"{nombre} respondió {respuesta.status_code}: {respuesta.text[:300]}")
    return respuesta.json()["choices"][0]["message"]["content"] or ""


def _openai(cfg: Config, sistema: str, prompt: str) -> str:
    if not cfg.openai_api_key:
        raise ErrorLLM("Falta OPENAI_API_KEY en el archivo .env")
    return _formato_openai(
        "OpenAI", "https://api.openai.com/v1", cfg.openai_api_key, cfg.openai_modelo, cfg.timeout, sistema, prompt
    )


def _gemini(cfg: Config, sistema: str, prompt: str) -> str:
    if not cfg.gemini_api_key:
        raise ErrorLLM("Falta GEMINI_API_KEY en el archivo .env")
    # Google ofrece Gemini con el mismo formato de chat de OpenAI
    return _formato_openai(
        "Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", cfg.gemini_api_key, cfg.gemini_modelo,
        cfg.timeout, sistema, prompt,
    )


PROVEEDORES = {"ollama": _ollama, "claude": _claude, "openai": _openai, "gemini": _gemini}


def generar(proveedor: str, cfg: Config, sistema: str, prompt: str) -> str:
    if proveedor not in PROVEEDORES:
        raise ErrorLLM(f"Proveedor desconocido: {proveedor}")
    try:
        return PROVEEDORES[proveedor](cfg, sistema, prompt)
    except requests.RequestException as e:
        raise ErrorLLM(f"No se pudo conectar con {proveedor}: {e}") from e
