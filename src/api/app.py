from fastapi import FastAPI
from pydantic import BaseModel
from agent import root_agent

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

app = FastAPI()

APP_NAME = "chat-agent-api"
USER_ID = "discord-user"
SESSION_ID = "default-session"

# 全局初始化，Cloud Run 复用实例时更省事
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

_session_initialized = False


class AskRequest(BaseModel):
    prompt: str


@app.get("/")
def root():
    return {"status": "ok"}


async def ensure_session():
    global _session_initialized
    if not _session_initialized:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
        _session_initialized = True


@app.post("/ask")
async def ask(req: AskRequest):
    try:
        prompt = req.prompt.strip()
        if not prompt:
            return {"ok": False, "error": "prompt 不能为空"}

        await ensure_session()

        content = types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )

        final_response = None

        events = runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content,
        )

        async for event in events:
            if event.is_final_response():
                if event.content and event.content.parts:
                    texts = []
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            texts.append(part.text)
                    final_response = "\n".join(texts).strip()

        if not final_response:
            return {"ok": False, "error": "没有捕获到最终回复"}

        return {"ok": True, "answer": final_response}

    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}