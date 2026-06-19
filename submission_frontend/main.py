import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk.sessions import VertexAiSessionService
from vertexai import Agent

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
AGENT_RUNTIME_ID = os.environ["AGENT_RUNTIME_ID"]
REGION = os.getenv("GCP_REGION", "us-central1")

app = FastAPI(title="Manager Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

session_service = VertexAiSessionService(project=PROJECT_ID, location=REGION)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/api/pending")
async def get_pending():
    sessions = await session_service.list_sessions(agent_id=AGENT_RUNTIME_ID)
    pending = []
    for session in sessions:
        history = await session_service.get_history(
            agent_id=AGENT_RUNTIME_ID,
            user_id="default-user",
            session_id=session.id,
        )
        pending += _find_interrupts(session.id, history)
    return pending


@app.post("/api/action/{session_id}")
async def take_action(session_id: str, request: Request):
    body = await request.json()
    approved = body["approved"]
    interrupt_id = body["interrupt_id"]
    expense = body["expense"]

    message = {
        "role": "user",
        "parts": [
            {
                "function_response": {
                    "id": interrupt_id,
                    "name": "adk_request_input",
                    "response": {"approved": approved, "expense": expense},
                }
            }
        ],
    }

    agent = Agent(model="gemini-2.0-flash", agent_id=AGENT_RUNTIME_ID)
    await agent.run_async(
        user_id="default-user",
        session_id=session_id,
        message=message,
    )
    return {"status": "ok", "approved": approved}


def _find_interrupts(session_id: str, history: list) -> list:
    pending = []
    pending_inputs = {}
    for event in history:
        if hasattr(event, "function_call") and event.function_call.name == "adk_request_input":
            pending_inputs[event.function_call.id] = event
        if hasattr(event, "function_response") and event.function_response.name == "adk_request_input":
            pending_inputs.pop(event.function_response.id, None)

    for interrupt_id, event in pending_inputs.items():
        args = event.function_call.args
        pending.append({
            "sessionId": session_id,
            "interruptId": interrupt_id,
            "expense": args.get("expense", {}),
            "reason": args.get("reason", ""),
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
</script>
</body>
</html>
"""
