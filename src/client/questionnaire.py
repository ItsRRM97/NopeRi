"""JD-aware prescreening answer builder for Naukri questionnaires."""

from __future__ import annotations

import logging
import re
from typing import Any

from config.profile_loader import load_application_profile, load_questionnaire_overrides
from src.ai.questionnaire_ai import ai_answer_question, match_option_key

logger = logging.getLogger(__name__)


def _is_lacs_unit(question_text: str) -> bool:
    """True when the form expects CTC in lacs/LPA, not raw INR."""
    text = question_text.lower()
    if "month" in text:
        return False
    return bool(re.search(r"\b(lacs?|lakhs?|lpa)\b", text))


def _format_ctc(value_lpa: int, question_text: str) -> str:
    text = question_text.lower()
    if "month" in text:
        return str(int(value_lpa * 100000 / 12))
    if _is_lacs_unit(question_text):
        if value_lpa == int(value_lpa):
            return str(int(value_lpa))
        return f"{value_lpa:.2f}".rstrip("0").rstrip(".")
    if value_lpa == 0:
        return "0"
    return str(value_lpa * 100000)


def _extract_job_context(job_details: dict[str, Any] | None) -> tuple[str, str, str]:
    if not job_details:
        return "", "", ""

    job = job_details.get("job") or job_details
    title = job.get("title") or job.get("jobTitle") or ""
    tags_raw = job.get("tagsAndSkills") or job.get("keywords") or ""
    if isinstance(tags_raw, list):
        tags = ", ".join(tags_raw)
    else:
        tags = str(tags_raw)
    description = (
        job.get("jobDescription")
        or job.get("description")
        or job_details.get("jobDescription")
        or ""
    )
    return title, tags, description


def build_smart_answers(
    questionnaire: list[dict],
    profile: dict[str, Any] | None = None,
    job_details: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict], bool]:
    """
    Build questionnaire answers using yaml profile + optional JD context + AI fallback.

    Returns (answers_dict, qa_log, low_confidence).
    """
    profile = profile or load_application_profile()
    overrides = load_questionnaire_overrides()
    answers: dict[str, Any] = {}
    qa_log: list[dict] = []
    low_confidence = False

    job_title, job_tags, job_description = _extract_job_context(job_details)
    user_info = profile.get("user_information_all", "")

    def lookup_override(qid: str, qtext: str) -> tuple[Any | None, str | None]:
        by_id = overrides.get("by_question_id") or {}
        if qid in by_id:
            entry = by_id[qid]
            return entry.get("answer"), entry.get("source", "user_override")
        qlower = qtext.lower()
        for pattern, entry in (overrides.get("by_question_contains") or {}).items():
            if pattern.lower() in qlower:
                return entry.get("answer"), entry.get("source", "user_override")
        return None, None

    def pick_yes(options: dict[str, str]) -> str:
        for key, label in options.items():
            if "yes" in label.lower():
                return key
        return list(options.keys())[0]

    def pick_notice(options: dict[str, str], notice_days: int) -> str:
        if notice_days <= 0:
            for key, label in options.items():
                val = label.lower()
                if any(x in val for x in ("immediate", "0 day", "0 days", "no notice")):
                    return key
        for key, label in options.items():
            val = label.lower()
            if "15" in val and notice_days <= 15:
                return key
            if "1 month" in val and notice_days <= 30:
                return key
            if "2 month" in val and notice_days <= 60:
                return key
        return list(options.keys())[0]

    for q in questionnaire:
        qid = q["questionId"]
        qtext_raw = q.get("questionName") or ""
        qtext = qtext_raw.lower()
        qtype = (q.get("questionType") or "").lower()
        options = q.get("answerOption") or {}

        source = "static"
        confidence = "high"
        ans: Any = None

        override_ans, override_source = lookup_override(qid, qtext_raw)
        if override_ans is not None:
            ans = override_ans
            source = override_source or "user_override"
            confidence = "high"
            answers[qid] = ans
            qa_log.append({
                "question_id": qid,
                "question": qtext_raw,
                "answer": ans,
                "source": source,
                "confidence": confidence,
            })
            logger.info(
                "Q&A [%s/%s] %s -> %s",
                source,
                confidence,
                qtext_raw[:80],
                ans,
            )
            continue

        if qtype == "text box":
            if "current ctc" in qtext or "current salary" in qtext:
                ans = _format_ctc(profile["current_ctc_lpa"], qtext_raw)
            elif "expected ctc" in qtext or "expected salary" in qtext or "desired ctc" in qtext:
                ans = _format_ctc(profile["expected_ctc_lpa"], qtext_raw)
            elif "notice" in qtext:
                if "month" in qtext and profile["notice_days"] > 0:
                    ans = str(max(0, profile["notice_days"] // 30))
                elif "week" in qtext and profile["notice_days"] > 0:
                    ans = str(max(0, profile["notice_days"] // 7))
                else:
                    ans = str(profile["notice_days"])
            elif "product" in qtext and "management" in qtext and "experience" in qtext:
                ans = profile["exp_product"]
            elif "b2c" in qtext and ("experience" in qtext or "years" in qtext):
                ans = profile.get("exp_b2c", "3")
            elif ("e-commerce" in qtext or "ecommerce" in qtext) and (
                "experience" in qtext or "years" in qtext
            ):
                ans = profile.get("exp_ecommerce", "3")
            elif "npd" in qtext and ("experience" in qtext or "years" in qtext):
                ans = profile.get("exp_npd", "3")
            elif "pricing" in qtext and "strategy" in qtext:
                ans = profile.get("exp_pricing_strategy", "0")
            elif "marketing" in qtext and "strategy" in qtext:
                ans = profile.get("exp_marketing_strategy", "0")
            elif "packaging" in qtext and ("development" in qtext or "experience" in qtext):
                ans = profile.get("exp_packaging", "0")
            elif "marketing" in qtext and (
                "experience" in qtext or "years" in qtext or "hands-on" in qtext
            ):
                ans = profile.get("exp_marketing", "0")
            elif "product" in qtext and "experience" in qtext:
                ans = profile["exp_product"]
            elif "experience" in qtext or "years" in qtext or "yoe" in qtext:
                ans = profile["exp_total"]
            elif "about yourself" in qtext or "tell us about" in qtext:
                ans = profile["tell_me_about_yourself"][:350]
            elif "gap" in qtext or "break" in qtext or "reason for leaving" in qtext:
                ans = profile["gap_reason_screening"][:350]
            elif "email" in qtext:
                ans = profile["email"]
            elif "phone" in qtext or "mobile" in qtext:
                ans = profile["phone"]
            elif "relocate" in qtext or "relocation" in qtext:
                ans = "Yes"
            elif (
                "residing" in qtext
                or "current city" in qtext
                or ("which city" in qtext and "prefer" not in qtext)
            ):
                ans = profile.get("city", "Hyderabad")
            elif "location" in qtext or "city" in qtext:
                ans = profile.get("city", "Hyderabad")
            else:
                ai_text, ai_conf = ai_answer_question(
                    qtext_raw,
                    user_info=user_info,
                    job_title=job_title,
                    job_tags=job_tags,
                    job_description=job_description,
                )
                source = "ai"
                confidence = ai_conf
                ans = ai_text or profile["exp_total"]
                if confidence == "low":
                    low_confidence = True

        elif options:
            matched_static = False
            if "notice" in qtext:
                key = pick_notice(options, profile["notice_days"])
                ans = [key]
                matched_static = True
            elif ("relocate" in qtext or "relocation" in qtext) and profile.get(
                "willing_to_relocate", True
            ):
                key = pick_yes(options)
                ans = [key]
                matched_static = True
            elif any(skill in qtext for skill in profile["skills"]):
                key = pick_yes(options)
                ans = [key]
                matched_static = True
            elif any(x in qtext for x in ("immediate", "join", "availability")):
                key = pick_notice(options, profile["notice_days"])
                ans = [key]
                matched_static = True
            elif re.search(r"\b(do you|have you|are you|willing)\b", qtext):
                ai_text, ai_conf = ai_answer_question(
                    qtext_raw,
                    user_info=user_info,
                    job_title=job_title,
                    job_tags=job_tags,
                    job_description=job_description,
                    options=options,
                )
                key, match_conf = match_option_key(options, ai_text)
                source = "ai"
                confidence = "low" if match_conf == "low" or ai_conf == "low" else match_conf
                ans = [key] if key else [pick_yes(options)]
                if confidence == "low":
                    low_confidence = True
                matched_static = True
            elif any(x in qtext for x in ("experience", "ctc", "salary", "lpa")):
                key = list(options.keys())[0]
                ans = [key]
                matched_static = True

            if not matched_static:
                ai_text, ai_conf = ai_answer_question(
                    qtext_raw,
                    user_info=user_info,
                    job_title=job_title,
                    job_tags=job_tags,
                    job_description=job_description,
                    options=options,
                )
                key, match_conf = match_option_key(options, ai_text)
                source = "ai"
                confidence = "low" if match_conf == "low" or ai_conf == "low" else match_conf
                ans = [key] if key else [list(options.keys())[0]]
                if confidence == "low":
                    low_confidence = True
        else:
            ans = profile["exp_total"]

        answers[qid] = ans
        qa_log.append({
            "question_id": qid,
            "question": qtext_raw,
            "answer": ans,
            "source": source,
            "confidence": confidence,
        })
        logger.info(
            "Q&A [%s/%s] %s -> %s",
            source,
            confidence,
            qtext_raw[:80],
            ans,
        )

    return answers, qa_log, low_confidence
