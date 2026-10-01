"""Fabrique du modèle de langage (Kimi-K2.6 via un endpoint Azure AI compatible OpenAI)."""

from __future__ import annotations
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

import os


def get_llm():
    """Retourne un client `ChatOpenAI` pointé sur l'endpoint Azure AI (Kimi-K2.6 par défaut).

    Configuration : `AZURE_AI_ENDPOINT`, `AZURE_AI_API_KEY`, `AZURE_AI_MODEL` (optionnel).
    Aucun module du cœur n'importe celui-ci : l'orchestration reste testable sans réseau.
    """

    return ChatOpenAI(
        base_url=os.environ["AZURE_AI_ENDPOINT"],
        api_key=SecretStr(os.environ["AZURE_AI_API_KEY"]),
        model=os.environ.get("AZURE_AI_MODEL", "Kimi-K2.6"),
    )
