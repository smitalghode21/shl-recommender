import os, json, re
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from catalog import SHL_CATALOG, TEST_TYPE_LABELS

app = FastAPI(title="SHL Assessment Recommender")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
gemini = genai.GenerativeModel("gemini-1.5-flash")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]

class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str

class ChatResponse(BaseModel):
    reply: str
    recommendations: list[Recommendation]
    end_of_conversation: bool

CATALOG_TEXT = "\n".join([
    f"- {i['name']} | Type:{i['test_type']}({TEST_TYPE_LABELS.get(i['test_type'],'')}) | URL:{i['url']} | {i['description']} | keywords:{','.join(i['keywords'])}"
    for i in SHL_CATALOG
])

SYSTEM = f"""You are an SHL Assessment Recommender agent helping hiring managers find assessments.

CATALOG (ONLY recommend from this list, never invent URLs or names):
{CATALOG_TEXT}

TYPE CODES: A=Ability/Aptitude  P=Personality  B=Behavioral  K=Knowledge/Skills  S=Simulation

BEHAVIOR:
- CLARIFY if vague (no role given). Ask ONE question at a time. Do NOT recommend yet.
- RECOMMEND 1-10 items once you know role + at least one more detail (level/skill/industry).
- REFINE shortlist when user adds or removes constraints mid-conversation.
- COMPARE using catalog data only when user asks differences between assessments.
- REFUSE off-topic (legal, salary, non-SHL). Say: I only help with SHL assessment recommendations.
- end_of_conversation=true only when user says done or goodbye.

OUTPUT: Strict JSON only. No markdown. No extra text.
{{"reply":"...","recommendations":[{{"name":"exact name","url":"exact url","test_type":"letter"}}],"end_of_conversation":false}}
recommendations=[] when clarifying/refusing. 1-10 items when recommending.
"""

CATALOG_BY_URL = {{i["url"]: i for i in SHL_CATALOG}}
CATALOG_BY_NAME = {{i["name"].lower(): i for i in SHL_CATALOG}}

def match_rec(name, url):
    if url in CATALOG_BY_URL:
        return CATALOG_BY_URL[url]
    nl = name.lower()
    if nl in CATALOG_BY_NAME:
        return CATALOG_BY_NAME[nl]
    for cn, ci in CATALOG_BY_NAME.items():
        if nl in cn or cn in nl:
            return ci
    return None

@app.get("/health")
async def health():
    return {{"status": "ok"}}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.messages:
        return ChatResponse(reply="Hello! What role are you hiring for?", recommendations=[], end_of_conversation=False)
    try:
        prompt = SYSTEM + "\n\nCONVERSATION:\n"
        for m in req.messages:
            prompt += f"{'User' if m.role=='user' else 'Assistant'}: {m.content}\n"
        prompt += "\nAssistant (JSON only):"
        resp = gemini.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.2, max_output_tokens=1000))
        raw = re.sub(r"^```json\s*|^```\s*|\s*```$", "", resp.text.strip()).strip()
        data = json.loads(raw)
        recs = []
        for r in data.get("recommendations", []):
            item = match_rec(r.get("name",""), r.get("url",""))
            if item:
                recs.append(Recommendation(name=item["name"], url=item["url"], test_type=item["test_type"]))
            if len(recs) >= 10:
                break
        return ChatResponse(reply=data.get("reply","How can I help?"), recommendations=recs, end_of_conversation=data.get("end_of_conversation",False))
    except Exception as e:
        return ChatResponse(reply="Could you rephrase that? I want to find the right assessments for you.", recommendations=[], end_of_conversation=False)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
