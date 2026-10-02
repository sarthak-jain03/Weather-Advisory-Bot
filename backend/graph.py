from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from backend.state import BotState, QueryIntent, MatchedSOP
from backend.weather import geocode_city, fetch_weather
from backend.sop_engine import load_sops, match_sops, format_sops_for_llm


def _get_llm(temperature: float = 0.1) -> ChatOpenAI:
    import os
    api_key = os.getenv("FIREWORKS_API_KEY", "")
    return ChatOpenAI(
        model=os.getenv("FIREWORKS_MODEL", "accounts/fireworks/models/gpt-oss-120b"),
        temperature=temperature,
        openai_api_key=api_key,
        openai_api_base="https://api.fireworks.ai/inference/v1",
    )


async def parse_query(state: BotState) -> dict:
    messages = state["messages"]
    user_msg = messages[-1].content if messages else ""
    session_facts = state.get("session_facts", [])

    session_context = ""
    if session_facts:
        session_context = (
            "\n\nContext from this conversation so far:\n"
            + "\n".join(f"- {f}" for f in session_facts)
        )

    llm = _get_llm(temperature=0.0)

    parse_prompt = f"""You are a query parser for a weather safety bot.  Extract the following from the user's message:

1. location: The city or place name mentioned.  If none is mentioned, check the conversation context below.  If still none, set to null.
2. activity: The specific outdoor activity mentioned (e.g., "cycling", "picnic", "walking the dog").  If none, set to null.
3. activity_keywords: A list of relevant keywords that describe the activity and context.  Include synonyms and related terms.  For example, "bike ride" → ["cycling", "bike", "bike ride", "outdoor exercise"].  Include keywords about vulnerable groups if mentioned (e.g., "my kid" → ["child", "children", "park"]).
4. question_type: One of "safety_check" (is it safe to do X?), "recommendation" (should I do X?), or "general_info" (what's the weather like?).
{session_context}

User message: "{user_msg}"

Respond with ONLY valid JSON, no markdown:
{{"location": "...", "activity": "...", "activity_keywords": ["..."], "question_type": "..."}}"""

    response = await llm.ainvoke([HumanMessage(content=parse_prompt)])

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
    except (json.JSONDecodeError, Exception):
        parsed = {
            "location": None,
            "activity": None,
            "activity_keywords": [],
            "question_type": "general_info",
        }

    query_intent = QueryIntent(
        location=parsed.get("location"),
        latitude=None,
        longitude=None,
        activity=parsed.get("activity"),
        activity_keywords=parsed.get("activity_keywords", []),
        question_type=parsed.get("question_type", "general_info"),
        raw_query=user_msg,
    )

    return {"query_intent": query_intent}


async def fetch_weather_data(state: BotState) -> dict:
    intent = state["query_intent"]
    location = intent.get("location")

    if not location:
        return {
            "weather_data": {},
            "weather_error": "No location could be determined from your message. Please mention a city name so I can check the weather.",
        }

    try:
        coords = await geocode_city(location)
        if coords is None:
            return {
                "weather_data": {},
                "weather_error": f"I couldn't find a location called '{location}'. Could you double-check the city name?",
            }

        lat, lon = coords

        intent_update = dict(intent)
        intent_update["latitude"] = lat
        intent_update["longitude"] = lon

        weather = await fetch_weather(lat, lon)

        return {
            "query_intent": intent_update,
            "weather_data": weather,
            "weather_error": None,
        }

    except Exception as e:
        return {
            "weather_data": {},
            "weather_error": f"The weather service is currently unavailable. I can't provide weather-based advice right now. (Error: {type(e).__name__})",
        }


def route_after_fetch(state: BotState) -> Literal["match_sops", "handle_weather_error"]:
    if state.get("weather_error"):
        return "handle_weather_error"
    return "match_sops"


async def handle_weather_error(state: BotState) -> dict:
    error_msg = state.get("weather_error", "Weather data unavailable.")

    response_text = (
        f"I'm sorry, I can't provide weather-based safety advice right now. "
        f"{error_msg}\n\n"
        f"Please try again shortly, or check your local weather service directly."
    )

    return {
        "response_text": response_text,
        "cited_sop_id": None,
        "matched_sops": [],
        "selected_sop": None,
        "messages": [AIMessage(content=response_text)],
    }


async def match_sops_node(state: BotState) -> dict:
    weather = state.get("weather_data", {})
    intent = state.get("query_intent", {})
    keywords = intent.get("activity_keywords", [])

    all_sops = load_sops()
    matched = match_sops(weather, keywords, all_sops)
    selected = matched[0] if matched else None

    return {
        "matched_sops": matched,
        "selected_sop": selected,
    }


def route_after_match(state: BotState) -> Literal["generate_response", "handle_no_match"]:
    if state.get("matched_sops"):
        return "generate_response"
    return "handle_no_match"


async def handle_no_match(state: BotState) -> dict:
    weather = state.get("weather_data", {})
    intent = state.get("query_intent", {})
    activity = intent.get("activity", "your planned activity")
    location = intent.get("location", "your location")

    weather_summary = _format_weather_summary(weather)

    response_text = (
        f"I checked the current weather for {location}:\n\n"
        f"{weather_summary}\n\n"
        f"However, I don't have a specific safety policy that covers "
        f"'{activity}' under these conditions.  I'd rather be honest "
        f"about that than give you ungrounded advice.\n\n"
        f"For general safety guidance, please consult your local weather "
        f"authority or IMD alerts."
    )

    session_facts = list(state.get("session_facts", []))
    session_facts.append(f"User asked about '{activity}' in {location} — no SOP matched.")

    return {
        "response_text": response_text,
        "cited_sop_id": None,
        "messages": [AIMessage(content=response_text)],
        "session_facts": session_facts,
    }


async def generate_response(state: BotState) -> dict:
    selected_sop = state["selected_sop"]
    all_matched = state.get("matched_sops", [])
    weather = state.get("weather_data", {})
    intent = state.get("query_intent", {})
    messages = state.get("messages", [])
    session_facts = list(state.get("session_facts", []))

    location = intent.get("location", "your location")
    activity = intent.get("activity", "the outdoor activity")

    weather_summary = _format_weather_summary(weather)

    other_sops_text = ""
    if len(all_matched) > 1:
        others = [s for s in all_matched if s["sop_id"] != selected_sop["sop_id"]]
        other_sops_text = "\n\nOther relevant policies (lower priority, mention briefly):\n"
        for s in others[:3]:
            other_sops_text += f"- [{s['sop_id']}] {s['title']} ({s['severity']}): {s['guidance'][:150]}...\n"

    system_prompt = f"""You are a weather safety advisor for MediBuddy.  You MUST follow these rules strictly:

1. Your answer must be based ONLY on the policy guidance provided below.  Do not add advice that isn't in the policy.
2. Cite the policy ID (e.g., "[SOP-001]") at the end of your response.
3. Use ONLY these weather numbers — do not make up or round numbers:
{weather_summary}

4. Be conversational and helpful, but DO NOT invent safety advice beyond what the policy says.
5. If the policy says "avoid" or "do not," relay that clearly — don't soften it into "maybe consider."
6. Keep the response concise (2-3 short paragraphs max).

PRIMARY POLICY TO APPLY:
[{selected_sop['sop_id']}] {selected_sop['title']} (Severity: {selected_sop['severity']})
Guidance: {selected_sop['guidance']}
Matched because: {'; '.join(selected_sop['matched_conditions'])}
{other_sops_text}

The user asked about: {activity} in {location}
"""

    llm = _get_llm(temperature=0.3)

    llm_messages = [SystemMessage(content=system_prompt)]
    for msg in messages[-4:]:
        llm_messages.append(msg)

    response = await llm.ainvoke(llm_messages)
    response_text = response.content

    session_facts.append(
        f"User asked about '{activity}' in {location}. "
        f"Applied {selected_sop['sop_id']} ({selected_sop['title']}). "
        f"Weather: temp={weather.get('temperature_2m')}°C, "
        f"wind={weather.get('wind_speed_10m')}km/h, "
        f"precip={weather.get('precipitation')}mm."
    )

    return {
        "response_text": response_text,
        "cited_sop_id": selected_sop["sop_id"],
        "messages": [AIMessage(content=response_text)],
        "session_facts": session_facts,
    }


def _format_weather_summary(weather: dict) -> str:
    parts = []
    field_labels = {
        "temperature_2m": ("Temperature", "°C"),
        "wind_speed_10m": ("Wind speed", "km/h"),
        "wind_gusts_10m": ("Wind gusts", "km/h"),
        "precipitation": ("Precipitation", "mm"),
        "precipitation_probability": ("Precipitation probability", "%"),
        "uv_index": ("UV Index", ""),
        "relative_humidity_2m": ("Humidity", "%"),
        "visibility": ("Visibility", "m"),
        "us_aqi": ("Air Quality (US AQI)", ""),
    }
    for field, (label, unit) in field_labels.items():
        val = weather.get(field)
        if val is not None:
            parts.append(f"  • {label}: {val}{unit}")
    return "\n".join(parts) if parts else "  (No weather data available)"


def build_graph() -> StateGraph:
    graph = StateGraph(BotState)

    graph.add_node("parse_query", parse_query)
    graph.add_node("fetch_weather", fetch_weather_data)
    graph.add_node("match_sops", match_sops_node)
    graph.add_node("generate_response", generate_response)
    graph.add_node("handle_weather_error", handle_weather_error)
    graph.add_node("handle_no_match", handle_no_match)

    graph.set_entry_point("parse_query")

    graph.add_edge("parse_query", "fetch_weather")

    graph.add_conditional_edges(
        "fetch_weather",
        route_after_fetch,
        {
            "match_sops": "match_sops",
            "handle_weather_error": "handle_weather_error",
        },
    )

    graph.add_conditional_edges(
        "match_sops",
        route_after_match,
        {
            "generate_response": "generate_response",
            "handle_no_match": "handle_no_match",
        },
    )

    graph.add_edge("generate_response", END)
    graph.add_edge("handle_weather_error", END)
    graph.add_edge("handle_no_match", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
