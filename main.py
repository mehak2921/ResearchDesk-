import sys
import io
import os

print(f"[STARTUP] Python {sys.version}", flush=True)
print("[STARTUP] importing fastapi...", flush=True)
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
print("[STARTUP] fastapi OK", flush=True)
import asyncio
import base64
import json
print("[STARTUP] importing redis...", flush=True)
import redis
print("[STARTUP] redis OK", flush=True)
from urllib.parse import urlparse

# Supabase imports
print("[STARTUP] importing supabase...", flush=True)
from postgrest.exceptions import APIError
from supabase import create_client, Client
print("[STARTUP] supabase OK", flush=True)

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("[STARTUP] importing dotenv...", flush=True)
from dotenv import load_dotenv
print("[STARTUP] dotenv OK", flush=True)

print("[STARTUP] all core imports done! FastAPI ready.", flush=True)

# Create the FastAPI app EARLY so Vercel's static parser can find it
app = FastAPI(title="AI Research Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# crewai is imported lazily inside run_crewai() to avoid native .so crash at startup

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

from supabase.client import ClientOptions

if supabase_url and supabase_key:
    supabase = create_client(
        supabase_url, 
        supabase_key, 
        options=ClientOptions(persist_session=False)
    )
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
def register(request: AuthRequest):
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
def login(request: AuthRequest):
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
def reset_password(request: ResetPasswordRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        supabase.auth.reset_password_email(request.email)
        return {"message": "Password reset email sent"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/update-password")
def update_password(request: UpdatePasswordRequest, user_id: str = Depends(get_current_user)):
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

@app.get("/api/models")
def list_models():
    import httpx
    api_key = os.environ.get("GROQ_API_KEY")
    resp = httpx.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {api_key}"})
    return resp.json()

# --- Existing Endpoints ---
def call_groq(messages: list, model: str = "openai/gpt-oss-120b") -> str:
    import httpx
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "Error: GROQ_API_KEY not set"
    
    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.01,
                "max_tokens": 8000
            },
            timeout=120.0
        )
        if resp.status_code >= 400:
            error_msg = f"Groq API Error {resp.status_code}: {resp.text}"
            print(error_msg)
            raise Exception(error_msg)
            
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq API error with {model}: {e}")
        raise e

def _run_search(query: str) -> str:
    import httpx
    
    # Primary: DuckDuckGo (Free, no API key)
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            ddg_results = list(ddgs.text(query, max_results=8))
        if ddg_results:
            for r in ddg_results:
                results.append(f"**{r.get('title','')}**\n{r.get('body','')}\nURL: {r.get('href','')}")
            return "\n\n".join(results)
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}. Falling back to Serper...")
        
    # Fallback: Serper API
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return "Error: DuckDuckGo failed and SERPER_API_KEY not set for fallback."
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
        # 1. Search the web
        search_results = _run_search(topic)

        # 2. Researcher Agent
        researcher_prompt = (
            f"You are a Senior Researcher with a keen eye for detail.\n"
            f"Your goal is to thoroughly research the topic: {topic}\n\n"
            f"{context_str}"
            f"Conduct comprehensive research on the exact topic based on the user's words.\n"
            f"Gather essential facts, history, relevant details, and the EXACT URLs/sources you used.\n\n"
            f"Here are the search results from the web:\n{search_results}\n\n"
            f"Write a structured report containing the most relevant and accurate facts, context, and details about the topic, including a precise list of the raw URLs used as sources."
        )
        print(f"Running Researcher on {model_name}...")
        research_report = call_groq([{"role": "user", "content": researcher_prompt}], model=model_name)

        # 3. Writer Agent
        writer_prompt = (
            f"You are a Versatile Writer, known for adapting your tone to the subject matter.\n"
            f"Your goal is to write an engaging and highly accurate article based on the provided research.\n\n"
            f"Here is the research report:\n{research_report}\n\n"
            f"Write a well-structured, engaging article about '{topic}' based entirely on the researcher's report. Ensure the tone matches the subject matter. You MUST append a 'References' section at the very end citing the specific sources. Every reference MUST be formatted as a clickable Markdown link using the format: [Source Title](URL). Do not just list the titles; you must include the full URL."
        )
        print(f"Running Writer on {model_name}...")
        final_article = call_groq([{"role": "user", "content": writer_prompt}], model=model_name)
        return final_article

    try:
        return execute("openai/gpt-oss-120b")
    except Exception as e:
        print(f"Primary model failed: {e}. Retrying with fallback.")
        return execute("llama-3.3-70b-versatile")

def run_clarification_check(topic: str):
    def execute(model_name):
        evaluator_prompt = (
            f"You are a Query Evaluator, an expert at understanding user intent.\n"
            f"Your goal is to determine if a user's query is highly ambiguous and needs clarification.\n\n"
            f"Evaluate this query: '{topic}'. If it is highly ambiguous (e.g., a single word with multiple meanings like 'Apple', or gibberish), provide 2-4 specific clarification options. If it is a standard query, return 'CLEAR'. Respond ONLY with valid JSON format: {{\"status\": \"clear\"}} OR {{\"status\": \"clarification_needed\", \"options\": [\"Option 1\", \"Option 2\"]}}"
        )
        result = call_groq([{"role": "user", "content": evaluator_prompt}], model=model_name)
        
        # Extract JSON from potential markdown blocks
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]
        return json.loads(result.strip())
        
    try:
        return execute("openai/gpt-oss-120b")
    except Exception as e:
        print(f"Primary model failed in run_clarification_check: {e}. Retrying with fallback.")
        try:
            return execute("llama-3.3-70b-versatile")
        except Exception:
            return {"status": "clear"} # fallback

def run_revision(topic: str, current_report: str, feedback: str):
    def execute(model_name):
        editor_prompt = (
            f"You are an Expert Editor. You are a skilled editor who can adapt existing content flawlessly to meet new requirements while retaining accuracy.\n"
            f"Your goal is to revise the report based on user feedback.\n\n"
            f"Topic: {topic}\n\n"
            f"Current Report:\n{current_report}\n\n"
            f"User Feedback: {feedback}\n\n"
            f"Rewrite the report to incorporate the user's feedback. Output ONLY the revised markdown content."
        )
        return call_groq([{"role": "user", "content": editor_prompt}], model=model_name)
        
    try:
        return execute("openai/gpt-oss-120b")
    except Exception as e:
        print(f"Primary model failed in run_revision: {e}. Retrying with fallback.")
        return execute("llama-3.3-70b-versatile")

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
