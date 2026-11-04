"""Configuración leída desde el archivo .env."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass
class Config:
    proveedor: str = os.getenv("PROVEEDOR_LLM", "ollama")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_modelo: str = os.getenv("OLLAMA_MODELO", "llama3.2:3b")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_modelo: str = os.getenv("ANTHROPIC_MODELO", "claude-sonnet-5-5")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_modelo: str = os.getenv("OPENAI_MODELO", "gpt-4o-mini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_modelo: str = os.getenv("GEMINI_MODELO", "gemini-3.5-flash-lite")
    top_k: int = int(os.getenv("TOP_K", "4"))
    max_candidatos: int = int(os.getenv("MAX_CANDIDATOS", "30"))
    timeout: int = int(os.getenv("TIMEOUT_SEGUNDOS", "180"))

    def modelo(self, proveedor: str) -> str:
        return {
            "ollama": self.ollama_modelo,
            "claude": self.anthropic_modelo,
            "openai": self.openai_modelo,
            "gemini": self.gemini_modelo,
        }.get(proveedor, "diccionario + reglas")
