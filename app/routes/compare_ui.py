from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Agent Comparison</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #1a1a2e;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      color: #fff;
    }

    /* ── Header ── */
    .header {
      background: #16213e;
      padding: 12px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #0f3460;
      flex-shrink: 0;
    }
    .header h1 { font-size: 16px; font-weight: 700; color: #e2e8f0; letter-spacing: .5px; }
    .header span { font-size: 12px; color: #94a3b8; }
    .clear-btn {
      background: #0f3460;
      color: #e2e8f0;
      border: 1px solid #1e4d8c;
      border-radius: 6px;
      padding: 6px 14px;
      font-size: 12px;
      cursor: pointer;
      transition: background .15s;
    }
    .clear-btn:hover { background: #1e4d8c; }

    /* ── Agent column headers ── */
    .columns-header {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
      padding: 8px 12px 0;
      flex-shrink: 0;
    }
    .col-header {
      border-radius: 8px 8px 0 0;
      padding: 10px 14px;
      text-align: center;
    }
    .col-header h2 { font-size: 13px; font-weight: 700; }
    .col-header p  { font-size: 11px; opacity: .75; margin-top: 2px; }

    .hybrid-header   { background: #065f46; }
    .tools-header    { background: #1e3a8a; }
    .context-header  { background: #581c87; }

    /* ── Columns ── */
    .columns {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
      padding: 0 12px;
      flex: 1;
      overflow: hidden;
      min-height: 0;
    }
    .col {
      display: flex;
      flex-direction: column;
      border-radius: 0 0 8px 8px;
      overflow: hidden;
      min-height: 0;
    }

    .hybrid-col  { background: #022c22; border: 1px solid #065f46; border-top: none; }
    .tools-col   { background: #0c1e4a; border: 1px solid #1e3a8a; border-top: none; }
    .context-col { background: #2d0b4e; border: 1px solid #581c87; border-top: none; }

    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-height: 0;
    }
    .messages::-webkit-scrollbar { width: 4px; }
    .messages::-webkit-scrollbar-track { background: transparent; }
    .messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,.15); border-radius: 2px; }

    /* ── Bubbles ── */
    .bubble-wrap { display: flex; flex-direction: column; max-width: 88%; }
    .bubble-wrap.user  { align-self: flex-end; align-items: flex-end; }
    .bubble-wrap.agent { align-self: flex-start; align-items: flex-start; }

    .speaker-label { font-size: 10px; font-weight: 600; margin-bottom: 2px; padding: 0 4px; opacity: .8; }

    .bubble {
      padding: 7px 11px;
      border-radius: 10px;
      font-size: 13px;
      line-height: 1.45;
      word-break: break-word;
    }
    .bubble.user  { background: rgba(255,255,255,.12); color: #e2e8f0; border-bottom-right-radius: 2px; }
    .bubble.agent { color: #f1f5f9; border-bottom-left-radius: 2px; }

    .hybrid-col  .bubble.agent { background: #065f46; }
    .tools-col   .bubble.agent { background: #1e3a8a; }
    .context-col .bubble.agent { background: #581c87; }

    .bubble .meta { font-size: 10px; opacity: .55; margin-top: 4px; text-align: right; }
    .bubble.agent .meta { text-align: left; }

    .bubble img {
      max-width: 100%;
      border-radius: 6px;
      margin-top: 6px;
      display: block;
    }

    /* typing indicator */
    .typing {
      display: flex; align-items: center; gap: 4px;
      padding: 8px 12px;
      border-radius: 10px;
      border-bottom-left-radius: 2px;
      align-self: flex-start;
    }
    .hybrid-col  .typing { background: #065f46; }
    .tools-col   .typing { background: #1e3a8a; }
    .context-col .typing { background: #581c87; }

    .typing span {
      width: 7px; height: 7px;
      background: rgba(255,255,255,.6);
      border-radius: 50%;
      animation: bounce 1.2s infinite;
    }
    .typing span:nth-child(2) { animation-delay: .2s; }
    .typing span:nth-child(3) { animation-delay: .4s; }
    @keyframes bounce {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-5px); }
    }

    /* ── Input bar ── */
    .input-bar {
      background: #16213e;
      padding: 10px 12px;
      display: flex;
      align-items: flex-end;
      gap: 8px;
      flex-shrink: 0;
      border-top: 1px solid #0f3460;
    }
    .input-bar textarea {
      flex: 1;
      background: #0f3460;
      border: 1px solid #1e4d8c;
      border-radius: 20px;
      padding: 10px 16px;
      color: #e2e8f0;
      font-size: 14px;
      resize: none;
      outline: none;
      max-height: 100px;
      overflow-y: auto;
      line-height: 1.4;
    }
    .input-bar textarea::placeholder { color: #64748b; }
    .send-btn {
      width: 42px; height: 42px;
      background: #065f46;
      border: none;
      border-radius: 50%;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      transition: background .15s;
    }
    .send-btn:hover  { background: #047857; }
    .send-btn:active { background: #064e3b; }
    .send-btn svg { fill: #fff; width: 20px; height: 20px; }

    /* status badge */
    .status-bar {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
      padding: 4px 12px;
      flex-shrink: 0;
    }
    .status-badge {
      text-align: center;
      font-size: 10px;
      padding: 2px 0;
      border-radius: 4px;
      opacity: .7;
    }
    .status-badge.thinking { opacity: 1; animation: pulse 1s infinite; }
    .hybrid-badge  { background: #065f46; }
    .tools-badge   { background: #1e3a8a; }
    .context-badge { background: #581c87; }
    @keyframes pulse { 0%,100% { opacity: .6; } 50% { opacity: 1; } }
  </style>
</head>
<body>

<div class="header">
  <div>
    <h1>Agent Comparison</h1>
    <span>Same query — 3 agents — independent memory</span>
  </div>
  <button class="clear-btn" onclick="clearAll()">Clear All</button>
</div>

<div class="columns-header">
  <div class="col-header hybrid-header">
    <h2>Hybrid Agent</h2>
    <p>Context + Tools</p>
  </div>
  <div class="col-header tools-header">
    <h2>Tools-Only Agent</h2>
    <p>Live DB queries</p>
  </div>
  <div class="col-header context-header">
    <h2>Context-Only Agent</h2>
    <p>No tools — catalog only</p>
  </div>
</div>

<div class="status-bar">
  <div class="status-badge hybrid-badge"  id="status-hybrid">Ready</div>
  <div class="status-badge tools-badge"   id="status-tools">Ready</div>
  <div class="status-badge context-badge" id="status-context">Ready</div>
</div>

<div class="columns">
  <div class="col hybrid-col">
    <div class="messages" id="msgs-hybrid"></div>
  </div>
  <div class="col tools-col">
    <div class="messages" id="msgs-tools"></div>
  </div>
  <div class="col context-col">
    <div class="messages" id="msgs-context"></div>
  </div>
</div>

<div class="input-bar">
  <textarea
    id="input"
    rows="1"
    placeholder="Type a customer message — all 3 agents will respond…"
    onkeydown="handleKey(event)"
    oninput="autoResize(this)"
  ></textarea>
  <button class="send-btn" onclick="sendMessage()">
    <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
  </button>
</div>

<script>
  const AGENTS = [
    { id: "hybrid",  endpoint: "/api/chat",              label: "Hybrid",       msgEl: "msgs-hybrid",  statusEl: "status-hybrid"  },
    { id: "tools",   endpoint: "/api/chat/tools-only",   label: "Tools-Only",   msgEl: "msgs-tools",   statusEl: "status-tools"   },
    { id: "context", endpoint: "/api/chat/context-only", label: "Context-Only", msgEl: "msgs-context", statusEl: "status-context" },
  ];

  // Each agent has its own independent history
  const histories = {
    hybrid:  [],
    tools:   [],
    context: [],
  };

  function now() {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 100) + "px";
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  function clearAll() {
    AGENTS.forEach(a => {
      document.getElementById(a.msgEl).innerHTML = "";
      histories[a.id] = [];
      setStatus(a, "Ready", false);
    });
  }

  function setStatus(agent, text, thinking) {
    const el = document.getElementById(agent.statusEl);
    el.textContent = text;
    el.className = `status-badge ${agent.id}-badge${thinking ? " thinking" : ""}`;
  }

  function appendBubble(agentId, role, text, imageUrl, time) {
    const container = document.getElementById(AGENTS.find(a => a.id === agentId).msgEl);

    const wrap = document.createElement("div");
    wrap.className = `bubble-wrap ${role}`;

    const label = document.createElement("div");
    label.className = "speaker-label";
    label.textContent = role === "user" ? "Customer" : AGENTS.find(a => a.id === agentId).label;
    wrap.appendChild(label);

    const bubble = document.createElement("div");
    bubble.className = `bubble ${role}`;

    const txt = document.createElement("span");
    txt.textContent = text;
    bubble.appendChild(txt);

    if (imageUrl) {
      const img = document.createElement("img");
      img.src = imageUrl;
      img.alt = "Product image";
      img.onerror = () => img.remove();
      bubble.appendChild(img);
    }

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = time || now();
    bubble.appendChild(meta);

    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
  }

  function showTyping(agentId) {
    const container = document.getElementById(AGENTS.find(a => a.id === agentId).msgEl);
    const el = document.createElement("div");
    el.className = "typing";
    el.id = `typing-${agentId}`;
    el.innerHTML = "<span></span><span></span><span></span>";
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  function removeTyping(agentId) {
    const el = document.getElementById(`typing-${agentId}`);
    if (el) el.remove();
  }

  async function queryAgent(agent, userText, time) {
    setStatus(agent, "Thinking…", true);
    showTyping(agent.id);

    try {
      const res = await fetch(agent.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: histories[agent.id] }),
      });

      removeTyping(agent.id);

      if (!res.ok) {
        const err = await res.text();
        appendBubble(agent.id, "agent", `⚠️ Error ${res.status}: ${err}`, null, now());
        setStatus(agent, "Error", false);
        return;
      }

      const data = await res.json();
      appendBubble(agent.id, "agent", data.message, data.image_url || null, now());

      // Append ONLY this agent's response to ITS OWN history
      histories[agent.id].push({ role: "assistant", content: data.message });
      setStatus(agent, "Ready", false);

    } catch (err) {
      removeTyping(agent.id);
      appendBubble(agent.id, "agent", "⚠️ Could not reach the server.", null, now());
      setStatus(agent, "Offline", false);
    }
  }

  async function sendMessage() {
    const input = document.getElementById("input");
    const text  = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    const time = now();

    // Append user message to ALL three agents' histories and show in all columns
    AGENTS.forEach(a => {
      histories[a.id].push({ role: "user", content: text });
      appendBubble(a.id, "user", text, null, time);
    });

    // Query all 3 agents simultaneously — independently
    await Promise.all(AGENTS.map(a => queryAgent(a, text, time)));
  }

  document.getElementById("input").focus();
</script>
</body>
</html>
"""


@router.get("/compare", response_class=HTMLResponse, include_in_schema=False)
async def compare_ui():
    return HTMLResponse(content=_HTML)
