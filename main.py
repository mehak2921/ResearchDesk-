import sys
import io
import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import base64
import json
import redis
from urllib.parse import urlparse

# Supabase imports
from postgrest.exceptions import APIError
from supabase import create_client, Client

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv

# ── Serverless compatibility stubs ──────────────────────────────────────────
# crewai transitively imports chromadb → onnxruntime (native .so).
# These compiled extensions crash Vercel's Lambda environment.
# We stub them in sys.modules BEFORE importing crewai so Python never
# loads the real packages. Safe because we never use memory=True in Crew().
import types as _types

class _Stub:
    """Absorbs any attribute access or call — a safe no-op placeholder."""
    def __init__(self, *a, **kw): pass
    def __call__(self, *a, **kw): return _Stub()
    def __getattr__(self, k): return _Stub()
    def __iter__(self): return iter([])
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def __bool__(self): return False

def _stub_pkg(name, **attrs):
    if name not in sys.modules:
        m = _types.ModuleType(name)
        m.__dict__.update({k: v for k, v in attrs.items()})
        sys.modules[name] = m

# onnxruntime and submodules
for _m in ['onnxruntime', 'onnxruntime.capi', 'onnxruntime.capi._pybind_state',
           'onnxruntime.backend', 'onnxruntime.tools', 'onnxruntime.quantization']:
    _stub_pkg(_m, InferenceSession=_Stub, SessionOptions=_Stub,
              GraphOptimizationLevel=_Stub(), ExecutionMode=_Stub(),
              OrtValue=_Stub, OrtDevice=_Stub)

# chromadb and submodules
for _m in ['chromadb', 'chromadb.config', 'chromadb.api', 'chromadb.api.types',
           'chromadb.types', 'chromadb.db', 'chromadb.errors', 'chromadb.utils',
           'chromadb.segment', 'chromadb.telemetry', 'chromadb.ingest']:
    _stub_pkg(_m, EphemeralClient=_Stub, PersistentClient=_Stub,
              HttpClient=_Stub, AsyncHttpClient=_Stub, Client=_Stub,
              Settings=_Stub, Collection=_Stub, configure=lambda **kw: None,
              DEFAULT_TENANT='default_tenant', DEFAULT_DATABASE='default_database')

# tokenizers (Rust compiled — crashes Lambda)
for _m in ['tokenizers', 'tokenizers.implementations', 'tokenizers.models',
           'tokenizers.pre_tokenizers', 'tokenizers.decoders', 'tokenizers.processors']:
    _stub_pkg(_m, Tokenizer=_Stub, Encoding=_Stub, AddedToken=_Stub)

# lancedb + lance (compiled Arrow/Rust extensions)
for _m in ['lancedb', 'lancedb.table', 'lancedb.index', 'lancedb.query',
           'lance', 'lance.dataset', 'lance_namespace', 'lance_namespace_urllib3_client']:
    _stub_pkg(_m, connect=_Stub, LanceDataset=_Stub, LanceTable=_Stub)

# pyarrow (C extension — may be pulled in by lancedb)
for _m in ['pyarrow', 'pyarrow.lib', 'pyarrow.compute', 'pyarrow.fs']:
    _stub_pkg(_m, Table=_Stub, Schema=_Stub, array=_Stub(), field=_Stub(),
              int64=_Stub(), float32=_Stub(), string=_Stub(), list_=_Stub())

# grpcio (C extension — pulled in by chromadb/opentelemetry)
for _m in ['grpc', 'grpc._channel', 'grpc.aio']:
    _stub_pkg(_m, Channel=_Stub, insecure_channel=_Stub, secure_channel=_Stub,
              ssl_channel_credentials=_Stub)

# kubernetes client (pulled in by chromadb)
for _m in ['kubernetes', 'kubernetes.client', 'kubernetes.config']:
    _stub_pkg(_m, client=_Stub, config=_Stub)
# ── End stubs ────────────────────────────────────────────────────────────────

from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
from typing import Type
from pydantic import Field

# Lightweight SerperDevTool — replaces crewai-tools to avoid 300MB+ of unused deps
class SerperSearchInput(BaseModel):
    query: str = Field(description="Search query to look up on the internet")

class SerperDevTool(BaseTool):
    name: str = "Internet Search"
    description: str = "Search the internet for current, accurate information about any topic"
    args_schema: Type[BaseModel] = SerperSearchInput

    def _run(self, query: str) -> str:
        import httpx
        api_key = os.environ.get("SERPER_API_KEY", "")
        if not api_key:
            return "Error: SERPER_API_KEY not set"
        try:
            resp = httpx.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 10},
                timeout=30,
            )
            data = resp.json()
            results = []
            for r in data.get("organic", [])[:8]:
                results.append(f"**{r.get('title','')}**\n{r.get('snippet','')}\nURL: {r.get('link','')}")
            return "\n\n".join(results) or "No results found"
        except Exception as e:
            return f"Search error: {e}"
try:
    import crewai.llms.cache as _crewai_cache
    _crewai_cache.mark_cache_breakpoint = lambda msg: msg
except (ImportError, AttributeError):
    pass  # crewai internal cache module not available on this platform

load_dotenv()

RESEARCH_HISTORY_TABLE = "research_history"

def get_jwt_payload(token: str | None) -> dict:
    if not token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}

def get_jwt_role(token: str | None) -> str | None:
    return get_jwt_payload(token).get("role")

def get_supabase_project_ref(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc
    if not host.endswith(".supabase.co"):
        return None
    return host.split(".", 1)[0]

def describe_database_error(error: Exception) -> str:
    if isinstance(error, APIError):
        message = getattr(error, "message", None)
        code = getattr(error, "code", None)
        details = getattr(error, "details", None)
        hint = getattr(error, "hint", None)
        full_error = " ".join(str(part) for part in (message, details, hint) if part)
        if "Invalid API key" in full_error:
            return "Supabase rejected the API key. Check that SUPABASE_SERVICE_ROLE_KEY belongs to the same project as SUPABASE_URL."
        if code == "PGRST205":
            return f"Supabase table '{RESEARCH_HISTORY_TABLE}' was not found. Run the SQL in supabase_schema.sql in your Supabase project."
        if message:
            return f"Supabase error: {message}"
    return f"Database error: {error}"

# Initialize Supabase
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
supabase_key_payload = get_jwt_payload(supabase_key)
supabase_key_role = supabase_key_payload.get("role")
supabase_key_ref = supabase_key_payload.get("ref")
supabase_project_ref = get_supabase_project_ref(supabase_url)
supabase: Client | None = None

if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
    print("Supabase client initialized.")
else:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not found in environment. History will not be saved.")

redis_url = os.environ.get("REDIS_URL")
redis_client = None
if redis_url:
    try:
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        print("Redis client initialized.")
    except Exception as e:
        print(f"Warning: Failed to connect to Redis: {e}")
        redis_client = None


app = FastAPI(title="AI Research Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class ResearchRequest(BaseModel):
    topic: str
    conversation_id: str | None = None

class ReviseRequest(BaseModel):
    topic: str
    current_report: str
    feedback: str

class AuthRequest(BaseModel):
    email: str
    password: str

class ResetPasswordRequest(BaseModel):
    email: str

class UpdatePasswordRequest(BaseModel):
    new_password: str

# --- Dependencies ---
def get_current_user(authorization: str = Header(None)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase is not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.split(" ")[1]
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid token or user not found")
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# --- Auth Endpoints ---
@app.post("/api/auth/register")
async def register(request: AuthRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        res = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password
        })
        return {"user": res.user, "session": res.session}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
async def login(request: AuthRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        res = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        return {"user": res.user, "session": res.session}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        supabase.auth.reset_password_email(request.email)
        return {"message": "Password reset email sent"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/update-password")
async def update_password(request: UpdatePasswordRequest, user_id: str = Depends(get_current_user)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        supabase.auth.admin.update_user_by_id(user_id, {"password": request.new_password})
        return {"message": "Password updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

CONTEXT_MESSAGES_LIMIT = int(os.environ.get("CONTEXT_MESSAGES_LIMIT", 10))

def create_conversation(user_id: str, title: str) -> str | None:
    if not supabase: return None
    try:
        res = supabase.table("conversations").insert({
            "user_id": user_id,
            "title": title
        }).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        print(f"Error creating conversation: {e}")
        return None

def save_message(conversation_id: str, role: str, message_type: str, content: str):
    if not supabase or not conversation_id: return
    try:
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "message_type": message_type,
            "content": content
        }).execute()
        supabase.table("conversations").update({
            "updated_at": "now()"
        }).eq("id", conversation_id).execute()
    except Exception as e:
        print(f"Error saving message: {e}")

def get_last_messages(conversation_id: str, limit: int = CONTEXT_MESSAGES_LIMIT) -> list:
    if not supabase or not conversation_id: return []
    try:
        res = supabase.table("messages")\
            .select("*")\
            .eq("conversation_id", conversation_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        # Reverse to get chronological order
        return list(reversed(res.data))
    except Exception as e:
        print(f"Error getting messages: {e}")
        return []

# --- Existing Endpoints ---
def run_crewai(topic: str, context_messages: list = None):
    context_str = ""
    if context_messages:
        context_str = "Conversation Summary:\n"
        for msg in context_messages:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            action = "asked about:" if msg["message_type"] == "user" else "summarized:"
            context_str += f"{role_name} {action}\n{msg['content']}\n\n"
        context_str += f"Current Question: {topic}\n\n"

    def execute(model_name):
        llm = LLM(
            model=model_name,
            temperature=0.01
        )
        search_tool = SerperDevTool()

        researcher = Agent(
            role="Senior Researcher",
            goal=f"Thoroughly research the topic: {topic}",
            backstory="You are an expert researcher with a keen eye for detail. You are careful to understand the true context of a query (e.g., distinguishing between a company and a general concept). You provide accurate, comprehensive, and unbiased information.",
            llm=llm,
            tools=[search_tool],
            verbose=True
        )

        writer = Agent(
            role="Versatile Writer",
            goal="Write an engaging and highly accurate article based on the provided research",
            backstory="You are a master communicator and writer, known for adapting your tone to the subject matter. Whether writing about history, science, language, or technology, you make complex topics accessible and fascinating.",
            llm=llm,
            verbose=True
        )

        research_task = Task(
            description=f"{context_str}Conduct comprehensive research on the exact topic: '{topic}'. Make sure you are researching the correct context of the topic based on the user's words. Gather essential facts, history, relevant details, and the EXACT URLs/sources you used.",
            expected_output="A structured report containing the most relevant and accurate facts, context, and details about the topic, including a precise list of the raw URLs used as sources.",
            agent=researcher
        )

        write_task = Task(
            description=f"Write a well-structured, engaging article about '{topic}' based entirely on the researcher's report. Ensure the tone matches the subject matter. You MUST append a 'References' section at the very end citing the specific sources. Every reference MUST be formatted as a clickable Markdown link using the format: [Source Title](URL). Do not just list the titles; you must include the full URL.",
            expected_output="A multi-paragraph, beautifully formatted Markdown article exploring the topic in depth. The article MUST end with a 'References' section containing bullet points of clickable Markdown links (e.g., [Wikipedia](https://wikipedia.org)).",
            agent=writer,
            context=[research_task]
        )

        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, write_task],
            verbose=True
        )

        result = crew.kickoff()
        return str(result)
        
    try:
        return execute("groq/llama-3.3-70b-versatile")
    except Exception as e:
        print(f"Primary model failed in run_crewai: {e}. Retrying with fallback.")
        return execute("groq/llama-3.1-8b-instant")

def run_clarification_check(topic: str):
    def execute(model_name):
        llm = LLM(model=model_name, temperature=0.1)
        evaluator = Agent(
            role="Query Evaluator",
            goal="Determine if a user's query is highly ambiguous and needs clarification.",
            backstory="You are an expert at understanding user intent.",
            llm=llm,
            verbose=False
        )
        eval_task = Task(
            description=f"Evaluate this query: '{topic}'. If it is highly ambiguous (e.g., a single word with multiple meanings like 'Apple', or gibberish), provide 2-4 specific clarification options. If it is a standard query, return 'CLEAR'. Respond ONLY with valid JSON format: {{\"status\": \"clear\"}} OR {{\"status\": \"clarification_needed\", \"options\": [\"Option 1\", \"Option 2\"]}}",
            expected_output="JSON output containing the evaluation status.",
            agent=evaluator
        )
        crew = Crew(agents=[evaluator], tasks=[eval_task], verbose=False)
        result = str(crew.kickoff())
        # Extract JSON from potential markdown blocks
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]
        return json.loads(result.strip())
        
    try:
        return execute("groq/llama-3.3-70b-versatile")
    except Exception as e:
        print(f"Primary model failed in run_clarification_check: {e}. Retrying with fallback.")
        try:
            return execute("groq/llama-3.1-8b-instant")
        except Exception:
            return {"status": "clear"} # fallback

def run_revision(topic: str, current_report: str, feedback: str):
    def execute(model_name):
        llm = LLM(model=model_name, temperature=0.1)
        editor = Agent(
            role="Expert Editor",
            goal="Revise the report based on user feedback.",
            backstory="You are a skilled editor who can adapt existing content flawlessly to meet new requirements while retaining accuracy.",
            llm=llm,
            verbose=True
        )
        revise_task = Task(
            description=f"Topic: {topic}\n\nCurrent Report:\n{current_report}\n\nUser Feedback: {feedback}\n\nRewrite the report to incorporate the user's feedback. Output ONLY the revised markdown content.",
            expected_output="A complete, revised Markdown article.",
            agent=editor
        )
        crew = Crew(agents=[editor], tasks=[revise_task], verbose=True)
        return str(crew.kickoff())
        
    try:
        return execute("groq/llama-3.3-70b-versatile")
    except Exception as e:
        print(f"Primary model failed in run_revision: {e}. Retrying with fallback.")
        return execute("groq/llama-3.1-8b-instant")

@app.post("/api/research")
async def research_topic(request: ResearchRequest, user_id: str = Depends(get_current_user)):
    try:
        # Step 1: Clarification check
        eval_result = await asyncio.to_thread(run_clarification_check, request.topic)
        if eval_result.get("status") == "clarification_needed":
            return {"status": "clarification_needed", "options": eval_result.get("options", [])}

        # Step 2: Handle Conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = create_conversation(user_id, request.topic)
        
        # Save user message
        if conversation_id:
            save_message(conversation_id, "user", "user", request.topic)

        # Step 3: Check Cache
        cache_key = f"research:{request.topic.strip().lower()}"
        cached_result = None
        if redis_client:
            try:
                cached_result = redis_client.get(cache_key)
            except Exception as e:
                print(f"Redis cache get error: {e}")
        
        history_saved = False
        history_error = None

        if cached_result:
            result = cached_result
            print(f"Cache hit for topic: {request.topic}")
            if conversation_id:
                short_summary = (result[:300] + '...') if len(result) > 300 else result
                save_message(conversation_id, "assistant", "research_summary", short_summary)
        else:
            # Step 4: Run Research with context
            print(f"Cache miss for topic: {request.topic}. Running research...")
            context_messages = get_last_messages(conversation_id) if conversation_id else []
            result = await asyncio.to_thread(run_crewai, request.topic, context_messages)
            
            # Step 5: Save to Cache and Conversation
            if redis_client:
                try:
                    redis_client.setex(cache_key, 86400, result)
                except Exception as e:
                    print(f"Redis cache set error: {e}")
            
            if conversation_id:
                short_summary = (result[:300] + '...') if len(result) > 300 else result
                save_message(conversation_id, "assistant", "research_summary", short_summary)
        
        # Step 6: Save to History
        if supabase:
            try:
                supabase.table(RESEARCH_HISTORY_TABLE).insert({
                    "user_id": user_id,
                    "topic": request.topic,
                    "report": result,
                    "conversation_id": conversation_id
                }).execute()
                history_saved = True
            except Exception as e:
                history_error = describe_database_error(e)
                print(history_error)
        else:
            history_error = "Supabase is not configured."

        return {
            "status": "success", 
            "result": result, 
            "historySaved": history_saved, 
            "historyError": history_error,
            "conversation_id": conversation_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/revise")
async def revise_report(request: ReviseRequest, user_id: str = Depends(get_current_user)):
    try:
        # Run revision
        result = await asyncio.to_thread(run_revision, request.topic, request.current_report, request.feedback)
        history_saved = False
        history_error = None
        
        if supabase:
            try:
                # Insert as a BRAND NEW history entry
                supabase.table(RESEARCH_HISTORY_TABLE).insert({
                    "user_id": user_id,
                    "topic": f"{request.topic} (Revised)",
                    "report": result
                }).execute()
                history_saved = True
            except Exception as e:
                history_error = describe_database_error(e)
                print(history_error)
        else:
            history_error = "Supabase is not configured."

        return {"status": "success", "result": result, "historySaved": history_saved, "historyError": history_error}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history(user_id: str = Depends(get_current_user)):
    if not supabase:
        return {"data": [], "error": "Supabase is not configured."}
    
    try:
        # Filter by user_id
        response = supabase.table(RESEARCH_HISTORY_TABLE).select("*").eq("user_id", user_id).order('created_at', desc=True).limit(20).execute()
        return {"data": response.data}
    except Exception as e:
        error_message = describe_database_error(e)
        print(error_message)
        return {"data": [], "error": error_message}

# Mount static files (guarded — Vercel serves these via CDN, directory may not exist in serverless)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass  # static/ not present in serverless environment; Vercel CDN handles it

@app.delete("/api/history/{item_id}")
async def delete_history(item_id: str, user_id: str = Depends(get_current_user)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase is not configured.")
    try:
        # Delete only if it belongs to the user
        response = supabase.table(RESEARCH_HISTORY_TABLE).delete().eq("id", item_id).eq("user_id", user_id).execute()
        return {"message": "Deleted successfully"}
    except Exception as e:
        error_message = describe_database_error(e)
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)



@app.get("/")
async def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"status": "ok", "message": "ResearchDesk API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
