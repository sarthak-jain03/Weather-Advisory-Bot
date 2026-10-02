from __future__ import annotations

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from langchain_core.messages import HumanMessage

from backend.graph import get_graph
from backend.state import BotState

load_dotenv()

app = FastAPI(
    title="MediBuddy Weather Advisory Bot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: dict[str, dict] = {}


def _get_or_create_session(session_id: str | None) -> tuple[str, dict]:
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]

    new_id = session_id or str(uuid.uuid4())
    _sessions[new_id] = {
        "messages": [],
        "query_intent": {},
        "weather_data": {},
        "weather_error": None,
        "matched_sops": [],
        "selected_sop": None,
        "response_text": "",
        "cited_sop_id": None,
        "session_facts": [],
    }
    return new_id, _sessions[new_id]


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    cited_sop_id: str | None = None
    matched_sops: list[dict] = []
    weather_data: dict = {}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id, session_state = _get_or_create_session(req.session_id)

    input_state: BotState = {
        "messages": session_state["messages"] + [HumanMessage(content=req.message)],
        "query_intent": session_state.get("query_intent", {}),
        "weather_data": {},
        "weather_error": None,
        "matched_sops": [],
        "selected_sop": None,
        "response_text": "",
        "cited_sop_id": None,
        "session_facts": session_state.get("session_facts", []),
    }

    try:
        graph = get_graph()
        result = await graph.ainvoke(input_state)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred processing your request: {str(e)}",
        )

    _sessions[session_id] = {
        "messages": result.get("messages", []),
        "query_intent": result.get("query_intent", {}),
        "weather_data": result.get("weather_data", {}),
        "weather_error": result.get("weather_error"),
        "matched_sops": result.get("matched_sops", []),
        "selected_sop": result.get("selected_sop"),
        "response_text": result.get("response_text", ""),
        "cited_sop_id": result.get("cited_sop_id"),
        "session_facts": result.get("session_facts", []),
    }

    weather_for_response = {
        k: v for k, v in result.get("weather_data", {}).items()
        if k != "raw_response" and v is not None
    }

    return ChatResponse(
        response=result.get("response_text", "I'm sorry, something went wrong."),
        session_id=session_id,
        cited_sop_id=result.get("cited_sop_id"),
        matched_sops=result.get("matched_sops", []),
        weather_data=weather_for_response,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "weather-advisory-bot"}


_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
async def serve_frontend():
    return FileResponse(str(_frontend_dir / "index.html"))


app.mount("/", StaticFiles(directory=str(_frontend_dir)), name="static")
