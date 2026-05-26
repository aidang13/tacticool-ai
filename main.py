from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import json
import os
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Load product catalog
PRODUCTS_FILE = os.path.join(os.path.dirname(__file__), "products.json")
try:
    with open(PRODUCTS_FILE) as f:
        products = json.load(f)
    print(f"Loaded {len(products)} products")
except FileNotFoundError:
    products = []
    print("No products.json found — catalog is empty")


SYSTEM_PROMPT = """You are a knowledgeable and friendly assistant for Tacti-Cool Gun, a firearm accessories and gear retailer.

Your job is to help customers:
- Find the right products for their needs (holsters, optics, ammo, magazines, accessories, etc.)
- Answer questions about firearms, compatibility, specifications, and gear
- Explain policies (shipping, FFL transfers, returns)
- Recommend products based on their specific gun, use case, or budget

Tone: Direct, knowledgeable, no-nonsense but approachable — like talking to an expert at a gun counter.

Rules:
- Always recommend specific products from the catalog when relevant, including their price and URL
- If you don't have a product that fits, say so honestly and suggest what to look for
- Do not provide advice on illegal modifications, converting semi-auto to full-auto, or bypassing background checks
- Do not give legal advice on state-specific laws — tell them to check their local regulations
- Keep responses concise — 2-4 sentences unless more detail is genuinely needed
"""


def find_relevant_products(query: str, max_results: int = 6) -> list:
    """Simple keyword-based product search — fast, no embeddings needed."""
    if not products:
        return []

    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    stopwords = {"a", "an", "the", "is", "it", "in", "on", "for", "to", "and", "or", "what", "which", "best", "good"}
    query_words -= stopwords

    scored = []
    for p in products:
        score = 0
        name = p.get("name", "").lower()
        desc = (p.get("short_description", "") + " " + p.get("description", "")).lower()
        cats = " ".join(c.get("name", "") for c in p.get("categories", [])).lower()
        tags = " ".join(t.get("name", "") for t in p.get("tags", [])).lower()
        attrs = " ".join(
            " ".join(str(v) for v in a.get("options", []))
            for a in p.get("attributes", [])
        ).lower()

        for word in query_words:
            if len(word) < 3:
                continue
            if word in name:
                score += 5
            if word in cats:
                score += 3
            if word in tags:
                score += 2
            if word in attrs:
                score += 2
            if word in desc:
                score += 1

        # Boost in-stock items
        if p.get("stock_status") == "instock":
            score += 1

        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:max_results]]


def format_product_context(relevant_products: list) -> str:
    if not relevant_products:
        return ""
    lines = ["\n\nRELEVANT PRODUCTS FROM OUR CATALOG:"]
    for p in relevant_products:
        price = p.get("price", "")
        name = p.get("name", "Unknown")
        url = p.get("permalink", "")
        short_desc = p.get("short_description", "")
        stock = "In Stock" if p.get("stock_status") == "instock" else "Out of Stock"
        # Strip HTML tags from short description
        short_desc = re.sub(r'<[^>]+>', '', short_desc).strip()
        lines.append(f"• {name} — ${price} ({stock})\n  {short_desc}\n  Link: {url}")
    return "\n".join(lines)


class ChatRequest(BaseModel):
    message: str
    history: list = []  # list of {"role": "user"/"assistant", "content": "..."}


class ChatResponse(BaseModel):
    reply: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    relevant = find_relevant_products(req.message)
    product_context = format_product_context(relevant)

    system = SYSTEM_PROMPT + product_context

    messages = [{"role": "system", "content": system}]
    # Include last 10 turns of history
    for turn in req.history[-10:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": req.message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=600,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(reply=reply)


@app.get("/health")
async def health():
    return {"status": "ok", "products_loaded": len(products)}
