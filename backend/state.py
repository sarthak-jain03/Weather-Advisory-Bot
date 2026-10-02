from __future__ import annotations

from typing import Any, TypedDict, Annotated
from langchain_core.messages import BaseMessage


def add_messages(left: list[BaseMessage], right: list[BaseMessage]) -> list[BaseMessage]:
    return left + right


class WeatherData(TypedDict, total=False):
    temperature_2m: float
    wind_speed_10m: float
    wind_gusts_10m: float
    precipitation: float
    precipitation_probability: float
    uv_index: float
    visibility: float
    us_aqi: float
    relative_humidity_2m: float
    current_hour: int
    raw_response: dict[str, Any]


class QueryIntent(TypedDict, total=False):
    location: str | None
    latitude: float | None
    longitude: float | None
    activity: str | None
    activity_keywords: list[str]
    question_type: str
    raw_query: str


class MatchedSOP(TypedDict):
    sop_id: str
    title: str
    category: str
    severity: str
    guidance: str
    matched_conditions: list[str]


class BotState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query_intent: QueryIntent
    weather_data: WeatherData
    weather_error: str | None
    matched_sops: list[MatchedSOP]
    selected_sop: MatchedSOP | None
    response_text: str
    cited_sop_id: str | None
    session_facts: list[str]
