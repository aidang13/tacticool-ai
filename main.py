from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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


WIDGET_JS = r"""
(function(){
  var API="https://tacticool-ai.onrender.com";
  var hist=[],isOpen=false,typing=false;
  var s=document.createElement("style");
  s.textContent=[
    "#tcw *{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}",
    "#tcw{position:fixed;bottom:24px;right:24px;z-index:999999}",
    "#tcb{width:56px;height:56px;border-radius:50%;background:#1a1a1a;border:2px solid #c8a84b;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.35);transition:transform .2s}",
    "#tcb:hover{transform:scale(1.08)}",
    "#tcb svg{width:26px;height:26px;fill:#c8a84b}",
    "#tcp{position:absolute;bottom:68px;right:0;width:360px;max-height:520px;background:#fff;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,.22);display:flex;flex-direction:column;overflow:hidden;opacity:0;pointer-events:none;transform:translateY(12px) scale(.97);transition:opacity .22s,transform .22s}",
    "#tcp.on{opacity:1;pointer-events:all;transform:translateY(0) scale(1)}",
    "#tch{background:#1a1a1a;color:#c8a84b;padding:14px 16px;font-weight:700;font-size:15px;display:flex;justify-content:space-between;align-items:center}",
    "#tcx{cursor:pointer;font-size:20px;color:#aaa}#tcx:hover{color:#fff}",
    "#tcm{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;max-height:360px;background:#f7f7f7}",
    ".tm{max-width:82%;padding:9px 12px;border-radius:12px;font-size:13.5px;line-height:1.45}",
    ".tm.b{background:#fff;color:#111;border-bottom-left-radius:4px;align-self:flex-start;box-shadow:0 1px 4px rgba(0,0,0,.08)}",
    ".tm.u{background:#1a1a1a;color:#fff;border-bottom-right-radius:4px;align-self:flex-end}",
    ".tm a{color:#c8a84b}",
    "#tcd{display:flex;gap:4px;padding:9px 12px;background:#fff;border-radius:12px;border-bottom-left-radius:4px;align-self:flex-start}",
    "#tcd span{width:7px;height:7px;background:#bbb;border-radius:50%;animation:tb 1.1s infinite}",
    "#tcd span:nth-child(2){animation-delay:.18s}#tcd span:nth-child(3){animation-delay:.36s}",
    "@keyframes tb{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}",
    "#tcr{display:flex;padding:10px 12px;gap:8px;background:#fff;border-top:1px solid #eee}",
    "#tci{flex:1;border:1px solid #ddd;border-radius:20px;padding:8px 14px;font-size:13.5px;outline:none}",
    "#tci:focus{border-color:#c8a84b}",
    "#tcs{background:#1a1a1a;color:#c8a84b;border:none;border-radius:20px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer}",
    "#tcs:disabled{opacity:.5;cursor:default}",
    "#tcf{text-align:center;font-size:10px;color:#bbb;padding:4px 0 8px;background:#fff}",
    "@media(max-width:420px){#tcp{width:calc(100vw - 32px)}}"
  ].join("");
  document.head.appendChild(s);
  var w=document.createElement("div");w.id="tcw";document.body.appendChild(w);
  var p=document.createElement("div");p.id="tcp";w.appendChild(p);
  var h=document.createElement("div");h.id="tch";
  h.innerHTML="<span>⚡ Tacti-Cool</span><span id='tcx'>✕</span>";
  p.appendChild(h);
  var m=document.createElement("div");m.id="tcm";p.appendChild(m);
  var r=document.createElement("div");r.id="tcr";p.appendChild(r);
  var inp=document.createElement("input");inp.id="tci";inp.type="text";
  inp.placeholder="Ask about guns, gear, ammo...";inp.maxLength=400;r.appendChild(inp);
  var snd=document.createElement("button");snd.id="tcs";snd.textContent="Send";r.appendChild(snd);
  var f=document.createElement("div");f.id="tcf";f.textContent="Powered by AI";p.appendChild(f);
  var b=document.createElement("div");b.id="tcb";b.title="Chat with Tacti-Cool";
  b.innerHTML="<svg viewBox='0 0 24 24'><path d='M20 2H4C2.9 2 2 2.9 2 4v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z'/></svg>";
  w.appendChild(b);
  function addMsg(txt,role){
    var d=document.getElementById("tcd");if(d)d.remove();
    var el=document.createElement("div");el.className="tm "+role;
    el.textContent=txt;m.appendChild(el);m.scrollTop=m.scrollHeight;
  }
  function dot(){
    var el=document.createElement("div");el.id="tcd";
    el.innerHTML="<span></span><span></span><span></span>";
    m.appendChild(el);m.scrollTop=m.scrollHeight;
  }
  async function send(){
    var txt=inp.value.trim();if(!txt||typing)return;
    inp.value="";addMsg(txt,"u");hist.push({role:"user",content:txt});
    typing=true;snd.disabled=true;dot();
    try{
      var res=await fetch(API+"/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:txt,history:hist.slice(-10)})});
      if(!res.ok)throw 0;
      var d=await res.json();
      addMsg(d.reply||"Sorry, try again!","b");
      hist.push({role:"assistant",content:d.reply||""});
    }catch(e){addMsg("Could not reach the assistant right now. Try again shortly.","b");}
    finally{typing=false;snd.disabled=false;inp.focus();}
  }
  function toggle(){
    isOpen=!isOpen;p.classList.toggle("on",isOpen);
    if(isOpen&&m.children.length===0){
      addMsg("Hey! I'm your Tacti-Cool assistant. Ask me about holsters, optics, ammo, or any gear.","b");
      setTimeout(function(){inp.focus();},200);
    }
  }
  b.addEventListener("click",toggle);
  document.getElementById("tcx").addEventListener("click",toggle);
  snd.addEventListener("click",send);
  inp.addEventListener("keydown",function(e){if(e.key==="Enter")send();});
})();
"""

@app.get("/widget.js")
async def widget_js():
    return Response(content=WIDGET_JS, media_type="application/javascript")
