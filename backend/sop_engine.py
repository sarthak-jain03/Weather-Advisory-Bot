from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from backend.state import MatchedSOP, WeatherData

_SOP_DIR = Path(__file__).resolve().parent.parent / "sops"
_SOP_FILE = _SOP_DIR / "policies.yaml"


def load_sops(sop_path: str | Path | None = None) -> list[dict]:
    path = Path(sop_path) if sop_path else _SOP_FILE
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("sops", [])


def _evaluate_condition(condition: dict, weather: dict) -> tuple[bool, str]:
    field = condition.get("field", "")
    op = condition.get("operator", "")
    value = condition.get("value")
    values = condition.get("values", [])

    if field.startswith("_fuzzy"):
        return True, f"{field}: delegated to holistic LLM assessment"

    actual = weather.get(field)
    if actual is None:
        return False, f"{field}: data not available"

    try:
        actual = float(actual)
    except (ValueError, TypeError):
        return False, f"{field}: non-numeric value '{actual}'"

    matched = False
    explanation = ""

    if op == "gte":
        matched = actual >= float(value)
        explanation = f"{field} = {actual} (threshold: ≥ {value})"
    elif op == "gt":
        matched = actual > float(value)
        explanation = f"{field} = {actual} (threshold: > {value})"
    elif op == "lte":
        matched = actual <= float(value)
        explanation = f"{field} = {actual} (threshold: ≤ {value})"
    elif op == "lt":
        matched = actual < float(value)
        explanation = f"{field} = {actual} (threshold: < {value})"
    elif op == "eq":
        matched = actual == float(value)
        explanation = f"{field} = {actual} (threshold: = {value})"
    elif op == "between":
        low, high = float(values[0]), float(values[1])
        matched = low <= actual <= high
        explanation = f"{field} = {actual} (threshold: between {low} and {high})"
    elif op == "any":
        matched = True
        explanation = f"{field}: any value accepted"
    else:
        return False, f"{field}: unknown operator '{op}'"

    return matched, explanation


SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "moderate": 2,
    "low": 1,
}


def match_sops(
    weather: dict,
    activity_keywords: list[str],
    all_sops: list[dict] | None = None,
) -> list[MatchedSOP]:
    if all_sops is None:
        all_sops = load_sops()

    matched: list[MatchedSOP] = []

    for sop in all_sops:
        conditions = sop.get("conditions", [])
        sop_keywords = [k.lower() for k in sop.get("activity_keywords", [])]

        keyword_match = False
        if not sop_keywords:
            keyword_match = True
        else:
            for user_kw in activity_keywords:
                user_kw_lower = user_kw.lower()
                for sop_kw in sop_keywords:
                    if user_kw_lower in sop_kw or sop_kw in user_kw_lower:
                        keyword_match = True
                        break
                if keyword_match:
                    break

        if not keyword_match:
            continue

        all_conditions_met = True
        matched_explanations = []

        for cond in conditions:
            met, explanation = _evaluate_condition(cond, weather)
            if met:
                matched_explanations.append(explanation)
            else:
                all_conditions_met = False
                break

        if all_conditions_met and conditions:
            guidance = sop.get("guidance", "")
            try:
                guidance = guidance.format(**weather)
            except (KeyError, ValueError):
                pass

            matched.append(
                MatchedSOP(
                    sop_id=sop["id"],
                    title=sop["title"],
                    category=sop.get("category", "general"),
                    severity=sop.get("severity", "low"),
                    guidance=guidance,
                    matched_conditions=matched_explanations,
                )
            )

    matched.sort(key=lambda s: SEVERITY_RANK.get(s["severity"], 0), reverse=True)
    return matched


def get_sop_by_id(sop_id: str, all_sops: list[dict] | None = None) -> dict | None:
    if all_sops is None:
        all_sops = load_sops()
    for sop in all_sops:
        if sop["id"] == sop_id:
            return sop
    return None


def format_sops_for_llm(sops: list[dict]) -> str:
    lines = []
    for sop in sops:
        lines.append(f"[{sop['id']}] {sop['title']} (severity: {sop.get('severity', 'unknown')}, category: {sop.get('category', 'unknown')})")
        kws = sop.get("activity_keywords", [])
        if kws:
            lines.append(f"  Keywords: {', '.join(kws)}")
        else:
            lines.append("  Keywords: ALL outdoor activities")
        for cond in sop.get("conditions", []):
            field = cond.get("field", "?")
            op = cond.get("operator", "?")
            val = cond.get("value", cond.get("values", "?"))
            lines.append(f"  Condition: {field} {op} {val}")
        lines.append(f"  Guidance: {sop.get('guidance', '').strip()[:200]}...")
        lines.append("")
    return "\n".join(lines)
