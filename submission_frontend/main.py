import os
import json
import logging
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_URL = os.environ["AGENT_URL"]
APP_NAME = os.getenv("APP_NAME", "expense_agent")
USER_IDS = ["default-user", "pubsub", "system"]

app = FastAPI(title="Manager Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/api/pending")
async def get_pending():
    async with httpx.AsyncClient(timeout=30) as client:
        all_sessions = []
        for uid in USER_IDS:
            list_url = f"{AGENT_URL}/apps/{APP_NAME}/users/{uid}/sessions"
            try:
                resp = await client.get(list_url)
                if resp.status_code == 200:
                    sessions = resp.json()
                    all_sessions.extend([(uid, s) for s in sessions])
            except Exception:
                pass

        pending = []
        for uid, session in all_sessions:
            sid = session["id"]
            hist_url = f"{AGENT_URL}/apps/{APP_NAME}/users/{uid}/sessions/{sid}"
            try:
                hist_resp = await client.get(hist_url)
                if hist_resp.status_code != 200:
                    continue
                session_data = hist_resp.json()
                events = session_data.get("events", [])
                found = _find_interrupts(sid, events)
                pending += found
            except Exception:
                pass
    return pending


@app.post("/api/action/{session_id}")
async def take_action(session_id: str, request: Request):
    body = await request.json()
    approved = body["approved"]
    interrupt_id = body["interrupt_id"]
    expense = body["expense"]
    user_id = body.get("userId", "default-user")

    decision = "approved" if approved else "rejected"
    amount = expense.get("amount", 0)
    submitter = expense.get("submitter", "")
    category = expense.get("category", "")
    description = expense.get("description", "")
    date = expense.get("date", "")

    message = (
        f"Manager decision for expense: ${amount} {category} - {description} "
        f"(submitted by {submitter}). Decision: {decision}. "
        f"Please confirm this has been processed."
    )

    payload = {
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": message}],
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{AGENT_URL}/run", json=payload)
        if resp.status_code != 200:
            return {"error": f"Agent returned {resp.status_code}"}
    return {"status": "ok", "approved": approved}


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("sessionId", "")

    if not session_id:
        import uuid
        session_id = f"chat-{uuid.uuid4().hex[:8]}"

    payload = {
        "userId": "default-user",
        "sessionId": session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": message}],
        },
    }

    reply_parts = []
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{AGENT_URL}/run", json=payload)
        if resp.status_code != 200:
            return {"error": f"Agent returned {resp.status_code}", "sessionId": session_id}
        events = resp.json()
        for event in events:
            for p in event.get("content", {}).get("parts", []):
                if p.get("text"):
                    reply_parts.append(p["text"])

    reply_text = "\n".join(reply_parts) if reply_parts else "(no response)"
    return {"reply": reply_text, "sessionId": session_id}


def _find_interrupts(session_id: str, events: list) -> list:
    pending = []
    pending_inputs = {}
    submit_results = {}
    approval_calls = set()

    for idx, event in enumerate(events):
        content = event.get("content", {})
        parts = content.get("parts", []) if content else []
        for part in parts:
            fc = part.get("functionCall")
            fr = part.get("functionResponse")
            if fc and fc.get("name") == "adk_request_input":
                pending_inputs[fc["id"]] = fc
            if fr and fr.get("name") == "adk_request_input":
                pending_inputs.pop(fr.get("id"), None)
            if fc and fc.get("name") == "submit_expense":
                submit_results[fc["id"]] = {"args": fc.get("args", {}), "responded": False}
            if fr and fr.get("name") == "submit_expense":
                resp = fr.get("response", {})
                if isinstance(resp, dict):
                    for k, v in submit_results.items():
                        if not v["responded"]:
                            v["responded"] = True
                            v["result"] = resp
                            break
            if fc and fc.get("name") == "request_approval":
                approval_calls.add(fc["id"])

    for interrupt_id, fc in pending_inputs.items():
        args = fc.get("args", {})
        expense = args.get("expense", args)
        pending.append({
            "sessionId": session_id,
            "interruptId": interrupt_id,
            "expense": expense if isinstance(expense, dict) else {},
            "reason": args.get("reason", args.get("message", "")),
        })

    for call_id, data in submit_results.items():
        result = data.get("result", {})
        if result.get("status") == "submitted_for_approval":
            expense = result.get("expense", data.get("args", {}))
            pending.append({
                "sessionId": session_id,
                "interruptId": call_id,
                "expense": expense if isinstance(expense, dict) else {},
                "reason": f"High-value expense (${expense.get('amount', '?')}) awaiting manager approval",
            })

    return pending


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Expense Approval Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0a12;--card:rgba(255,255,255,0.04);--card-border:rgba(255,255,255,0.08);
  --text:#e8e8f0;--text-dim:#7a7a8e;--accent:#6c5ce7;--accent-glow:#6c5ce744;
  --green:#00b894;--green-glow:#00b89444;--red:#ff6b6b;--red-glow:#ff6b6b44;
  --radius:16px;--transition:all .3s cubic-bezier(.4,0,.2,1);
}
html,body{height:100%;font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);overflow-x:hidden}
body{position:relative}

.glow-orb{position:fixed;border-radius:50%;filter:blur(120px);pointer-events:none;z-index:0}
.glow-orb.purple{width:500px;height:500px;background:#6c5ce733;top:-10%;left:-5%;animation:drift 20s ease-in-out infinite}
.glow-orb.blue{width:400px;height:400px;background:#0984e333;bottom:-10%;right:-5%;animation:drift 25s ease-in-out infinite reverse}
@keyframes drift{0%,100%{transform:translate(0,0)}50%{transform:translate(60px,40px)}}

.app{position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:40px 24px 80px}

header{display:flex;align-items:center;justify-content:space-between;margin-bottom:40px}
header h1{font-size:1.8rem;font-weight:700;letter-spacing:-0.5px}
header h1 span{color:var(--accent)}
.badge{background:var(--accent);color:#fff;font-size:.75rem;font-weight:600;padding:4px 12px;border-radius:20px}
.stats{display:flex;gap:16px;margin-bottom:32px}
.stat-card{flex:1;background:var(--card);backdrop-filter:blur(20px);border:1px solid var(--card-border);border-radius:var(--radius);padding:20px;text-align:center}
.stat-card .num{font-size:2rem;font-weight:700}
.stat-card .label{font-size:.8rem;color:var(--text-dim);margin-top:4px}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:20px}

.card{background:var(--card);backdrop-filter:blur(24px);border:1px solid var(--card-border);border-radius:var(--radius);padding:24px;transition:var(--transition);position:relative;overflow:hidden}
.card:hover{border-color:rgba(108,92,231,.3);transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.3)}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--accent),#0984e3);opacity:0;transition:opacity .3s}
.card:hover::before{opacity:1}

.card-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.card-title{font-weight:600;font-size:1rem}
.card-amount{font-size:1.5rem;font-weight:700;color:var(--accent)}

.card-body{margin-bottom:16px}
.field{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:.85rem}
.field .key{color:var(--text-dim)}
.field .val{font-weight:500}

.actions{display:flex;gap:10px;margin-top:8px}
.btn{flex:1;padding:10px;border:none;border-radius:10px;font-family:inherit;font-weight:600;font-size:.85rem;cursor:pointer;transition:var(--transition);display:flex;align-items:center;justify-content:center;gap:6px}
.btn-approve{background:var(--green);color:#fff}
.btn-approve:hover{background:#00a884;box-shadow:0 4px 20px var(--green-glow)}
.btn-reject{background:rgba(255,107,107,0.15);color:var(--red);border:1px solid rgba(255,107,107,0.3)}
.btn-reject:hover{background:rgba(255,107,107,0.25);box-shadow:0 4px 20px var(--red-glow)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn .spinner{width:16px;height:16px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;display:none}
.btn.loading .spinner{display:block}
.btn.loading .label{display:none}
@keyframes spin{to{transform:rotate(360deg)}}

.empty{text-align:center;padding:80px 20px;color:var(--text-dim)}
.empty svg{width:80px;height:80px;margin-bottom:16px;opacity:.3}
.empty p{font-size:1.1rem}

.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(8px);z-index:100;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .3s}
.modal-overlay.active{opacity:1;pointer-events:all}
.modal{background:#13131f;border:1px solid var(--card-border);border-radius:var(--radius);padding:32px;max-width:480px;width:90%;transform:translateY(20px) scale(.97);transition:transform .3s cubic-bezier(.4,0,.2,1)}
.modal-overlay.active .modal{transform:translateY(0) scale(1)}
.modal h3{font-size:1.2rem;margin-bottom:8px}
.modal .status-badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.75rem;font-weight:600;margin-bottom:16px}
.modal .status-badge.approved{background:rgba(0,184,148,.15);color:var(--green)}
.modal .status-badge.rejected{background:rgba(255,107,107,.15);color:var(--red)}
.modal pre{background:rgba(255,255,255,.03);border:1px solid var(--card-border);border-radius:10px;padding:16px;font-size:.8rem;overflow-x:auto;margin:12px 0;max-height:260px;overflow-y:auto}
.modal .close-btn{margin-top:16px;width:100%;padding:10px;background:var(--accent);color:#fff;border:none;border-radius:10px;font-family:inherit;font-weight:600;cursor:pointer;transition:var(--transition)}
.modal .close-btn:hover{background:#5a4bd6}

.fade-in{animation:fadeUp .4s ease both}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}

.chat-toggle{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:var(--accent);color:#fff;border:none;font-size:24px;cursor:pointer;box-shadow:0 4px 20px var(--accent-glow);z-index:90;transition:var(--transition);display:flex;align-items:center;justify-content:center}
.chat-toggle:hover{transform:scale(1.08);box-shadow:0 6px 30px var(--accent-glow)}
.chat-panel{position:fixed;bottom:90px;right:24px;width:380px;height:500px;background:#13131f;border:1px solid var(--card-border);border-radius:var(--radius);z-index:90;display:flex;flex-direction:column;transform:translateY(20px) scale(.95);opacity:0;pointer-events:none;transition:var(--transition);overflow:hidden}
.chat-panel.open{transform:translateY(0) scale(1);opacity:1;pointer-events:all}
.chat-header{padding:16px 20px;border-bottom:1px solid var(--card-border);display:flex;align-items:center;justify-content:space-between}
.chat-header h3{font-size:.95rem;font-weight:600}
.chat-header .dot{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.chat-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}
.chat-msg{max-width:85%;padding:10px 14px;border-radius:12px;font-size:.85rem;line-height:1.5;animation:fadeUp .3s ease both}
.chat-msg.user{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:4px}
.chat-msg.agent{align-self:flex-start;background:rgba(255,255,255,0.06);border:1px solid var(--card-border);border-bottom-left-radius:4px}
.chat-msg.agent pre{margin:6px 0 0;padding:8px;background:rgba(0,0,0,.3);border-radius:6px;font-size:.75rem;overflow-x:auto;white-space:pre-wrap}
.chat-input-area{padding:12px 16px;border-top:1px solid var(--card-border);display:flex;gap:8px}
.chat-input-area input{flex:1;background:rgba(255,255,255,0.05);border:1px solid var(--card-border);border-radius:10px;padding:10px 14px;color:var(--text);font-family:inherit;font-size:.85rem;outline:none;transition:var(--transition)}
.chat-input-area input:focus{border-color:var(--accent)}
.chat-input-area button{background:var(--accent);color:#fff;border:none;border-radius:10px;padding:10px 16px;font-family:inherit;font-weight:600;font-size:.85rem;cursor:pointer;transition:var(--transition)}
.chat-input-area button:hover{background:#5a4bd6}
.chat-input-area button:disabled{opacity:.5;cursor:not-allowed}
</style>
</head>
<body>
<div class="glow-orb purple"></div>
<div class="glow-orb blue"></div>

<div class="app">
  <header>
    <h1>Expense <span>Approval</span> Dashboard</h1>
    <div class="badge" id="count-badge">0 pending</div>
  </header>
  <div class="stats">
    <div class="stat-card"><div class="num" id="stat-total">0</div><div class="label">Total Pending</div></div>
    <div class="stat-card"><div class="num" id="stat-amount">$0</div><div class="label">Total Value</div></div>
    <div class="stat-card"><div class="num" id="stat-categories">0</div><div class="label">Categories</div></div>
  </div>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty-state" style="display:none">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
    <p>All caught up! No pending approvals.</p>
  </div>
</div>

<div class="modal-overlay" id="modal">
  <div class="modal">
    <h3 id="modal-title">Compliance Review</h3>
    <div class="status-badge" id="modal-status"></div>
    <pre id="modal-body"></pre>
    <button class="close-btn" onclick="closeModal()">Close</button>
  </div>
</div>

<button class="chat-toggle" onclick="toggleChat()" id="chatBtn">💬</button>
<div class="chat-panel" id="chatPanel">
  <div class="chat-header">
    <h3>Expense Agent</h3>
    <div class="dot"></div>
  </div>
  <div class="chat-messages" id="chatMessages">
    <div class="chat-msg agent">Hello! I'm your expense agent. Ask me anything about expenses, policies, or submit a new expense.</div>
  </div>
  <div class="chat-input-area">
    <input type="text" id="chatInput" placeholder="Type a message..." onkeypress="if(event.key==='Enter')sendChat()"/>
    <button onclick="sendChat()" id="chatSendBtn">Send</button>
  </div>
</div>

<script>
let pendingData=[];
const grid=document.getElementById('grid');
const emptyState=document.getElementById('empty-state');

function renderCards(data){
  pendingData=data;
  grid.innerHTML='';
  emptyState.style.display=data.length?'none':'block';
  document.getElementById('count-badge').textContent=data.length+' pending';
  document.getElementById('stat-total').textContent=data.length;
  const total=data.reduce((s,x)=>s+(x.expense.amount||0),0);
  document.getElementById('stat-amount').textContent='$'+total.toLocaleString();
  const cats=new Set(data.map(x=>x.expense.category||'Other'));
  document.getElementById('stat-categories').textContent=cats.size;

  data.forEach((item,i)=>{
    const card=document.createElement('div');
    card.className='card fade-in';
    card.style.animationDelay=i*60+'ms';
    const e=item.expense;
    card.innerHTML=`
      <div class="card-header">
        <div class="card-title">${e.title||'Expense'}</div>
        <div class="card-amount">$${(e.amount||0).toLocaleString()}</div>
      </div>
      <div class="card-body">
        <div class="field"><span class="key">Category</span><span class="val">${e.category||'—'}</span></div>
        <div class="field"><span class="key">Vendor</span><span class="val">${e.vendor||'—'}</span></div>
        <div class="field"><span class="key">Employee</span><span class="val">${e.employee||e.submitted_by||'—'}</span></div>
        <div class="field"><span class="key">Date</span><span class="val">${e.date||'—'}</span></div>
        <div class="field"><span class="key">Session</span><span class="val" style="font-size:.7rem;opacity:.6">${item.sessionId.slice(0,16)}…</span></div>
      </div>
      <div class="actions">
        <button class="btn btn-approve" onclick="takeAction('${item.sessionId}','${item.interruptId}',true,${i})">
          <div class="spinner"></div><span class="label">Approve</span>
        </button>
        <button class="btn btn-reject" onclick="takeAction('${item.sessionId}','${item.interruptId}',false,${i})">
          <div class="spinner"></div><span class="label">Reject</span>
        </button>
      </div>`;
    grid.appendChild(card);
  });
}

async function takeAction(sessionId,interruptId,approved,idx){
  const btns=grid.children[idx].querySelectorAll('.btn');
  btns.forEach(b=>{b.disabled=true;b.classList.add('loading')});
  try{
    const res=await fetch('/api/action/'+sessionId,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({approved,interrupt_id:interruptId,expense:pendingData[idx].expense})
    });
    if(res.ok){
      const data=await res.json();
      showModal(pendingData[idx],approved);
      pendingData.splice(idx,1);
      renderCards(pendingData);
    } else {
      alert('Action failed. Please try again.');
      btns.forEach(b=>{b.disabled=false;b.classList.remove('loading')});
    }
  }catch(e){
    alert('Network error. Please try again.');
    btns.forEach(b=>{b.disabled=false;b.classList.remove('loading')});
  }
}

function showModal(item,approved){
  const modal=document.getElementById('modal');
  document.getElementById('modal-title').textContent=item.expense.title||'Expense Review';
  const badge=document.getElementById('modal-status');
  badge.textContent=approved?'Approved':'Rejected';
  badge.className='status-badge '+(approved?'approved':'rejected');
  document.getElementById('modal-body').textContent=JSON.stringify(item,null,2);
  modal.classList.add('active');
}
function closeModal(){document.getElementById('modal').classList.remove('active')}
document.getElementById('modal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});

async function load(){
  try{
    const res=await fetch('/api/pending');
    const data=await res.json();
    renderCards(data);
  }catch(e){console.error(e)}
}
load();
setInterval(load,15000);

let chatSessionId='';
function toggleChat(){
  document.getElementById('chatPanel').classList.toggle('open');
  document.getElementById('chatInput').focus();
}

async function sendChat(){
  const input=document.getElementById('chatInput');
  const msg=input.value.trim();
  if(!msg)return;
  input.value='';

  addChatMsg(msg,'user');
  const sendBtn=document.getElementById('chatSendBtn');
  sendBtn.disabled=true;

  try{
    const res=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg,sessionId:chatSessionId})
    });
    const data=await res.json();
    chatSessionId=data.sessionId||chatSessionId;
    addChatMsg(data.reply||data.error||'(error)','agent');
  }catch(e){
    addChatMsg('Network error','agent');
  }
  sendBtn.disabled=false;
}

function addChatMsg(text,role){
  const container=document.getElementById('chatMessages');
  const div=document.createElement('div');
  div.className='chat-msg '+role;
  if(text.includes('```')||text.includes('{')){
    div.innerHTML='<pre>'+text.replace(/</g,'&lt;')+'</pre>';
  } else {
    div.textContent=text;
  }
  container.appendChild(div);
  container.scrollTop=container.scrollHeight;
}
</script>
</body>
</html>
"""
