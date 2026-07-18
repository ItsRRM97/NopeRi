"""OpenRouter-backed Q&A for Naukri prescreening questionnaires."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

AI_ANSWER_PROMPT = """
You are an intelligent AI assistant filling out a job application prescreening form.
Respond concisely based on the type of question:

1. If the question asks for years of experience, duration, or numeric value, return only a number (e.g., "6", "3", "0").
2. If the question is a Yes/No question, return only "Yes" or "No".
3. If the question requires a short description, give a single-sentence response.
4. If the question requires a detailed response, provide a well-structured human-like answer under 350 characters.
5. Do not repeat the question in your answer.
6. For multiple choice, return ONLY the exact option label from the provided list (character-for-character match).

User Information:
{user_info}

Job Title: {job_title}
Job Tags/Skills: {job_tags}
Job Description (excerpt):
{job_description}

Question:
{question}
{options_block}
"""


def _ai_config() -> tuple[str, str, str]:
    api_key = os.getenv("OPEN_API_KEY") or os.getenv("OPENROUTER_API_KEY") or ""
    base = os.getenv(
        "OPENAI_API_BASE",
        "https://openrouter.ai/api/v1/chat/completions",
    )
    if not base.rstrip("/").endswith("chat/completions"):
        base = base.rstrip("/") + "/chat/completions"
    model = os.getenv("OPENAI_MODEL", "google/gemini-2.5-flash-lite")
    return api_key, base, model


def ai_answer_question(
    question: str,
    *,
    user_info: str,
    job_title: str = "",
    job_tags: str = "",
    job_description: str = "",
    options: dict[str, str] | None = None,
) -> tuple[str, str]:
    """
    Returns (answer_text, confidence) where confidence is 'high', 'medium', or 'low'.
    """
    api_key, url, model = _ai_config()
    if not api_key:
        logger.warning("No OPEN_API_KEY / OPENROUTER_API_KEY; skipping AI answer")
        return "", "low"

    options_block = ""
    if options:
        labels = [f"- {label}" for label in options.values()]
        options_block = "\nChoose exactly one of these option labels:\n" + "\n".join(labels)

    prompt = AI_ANSWER_PROMPT.format(
        user_info=user_info or "N/A",
        job_title=job_title or "N/A",
        job_tags=job_tags or "N/A",
        job_description=(job_description or "N/A")[:3000],
        question=question,
        options_block=options_block,
    )

    try:
        res = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=60,
        )
        if res.status_code != 200:
            logger.warning("AI HTTP error %s: %s", res.status_code, res.text[:200])
            return "", "low"

        content = res.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^['\"]|['\"]$", "", content)
        return content, "medium"
    except Exception as exc:
        logger.warning("AI answer failed: %s", exc)
        return "", "low"


def match_option_key(options: dict[str, str], answer_text: str) -> tuple[str | None, str]:
    """Map AI/free-text answer to an answerOption key. Returns (key, confidence)."""
    if not options or not answer_text:
        return None, "low"

    normalized = answer_text.strip().lower()
    for key, label in options.items():
        if label.strip().lower() == normalized:
            return key, "high"
    for key, label in options.items():
        if normalized in label.strip().lower() or label.strip().lower() in normalized:
            return key, "medium"
    if normalized in ("yes", "y"):
        for key, label in options.items():
            if "yes" in label.lower():
                return key, "medium"
    if normalized in ("no", "n"):
        for key, label in options.items():
            if "no" in label.lower() and "not" not in label.lower():
                return key, "medium"
    return list(options.keys())[0], "low"
