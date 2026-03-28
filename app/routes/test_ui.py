from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>CA Test Chat</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #e5ddd5;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }

    /* ── Header ── */
    .header {
      background: #075e54;
      color: #fff;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      box-shadow: 0 1px 4px rgba(0,0,0,.3);
      flex-shrink: 0;
    }
    .avatar {
      width: 38px; height: 38px;
      background: #25d366;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 18px;
    }
    .header-info { flex: 1; }
    .header-info h1 { font-size: 16px; font-weight: 600; }
    .header-info span { font-size: 12px; opacity: .75; }

    .endpoint-select {
      background: rgba(255,255,255,.15);
      color: #fff;
      border: 1px solid rgba(255,255,255,.3);
      border-radius: 6px;
      padding: 5px 8px;
      font-size: 12px;
      cursor: pointer;
      outline: none;
    }
    .endpoint-select option { background: #075e54; color: #fff; }

    .clear-btn {
      background: rgba(255,255,255,.15);
      color: #fff;
      border: 1px solid rgba(255,255,255,.3);
      border-radius: 6px;
      padding: 5px 10px;
      font-size: 12px;
      cursor: pointer;
    }
    .clear-btn:hover { background: rgba(255,255,255,.25); }

    /* ── Messages ── */
    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .bubble-wrap {
      display: flex;
      flex-direction: column;
      max-width: 72%;
    }
    .bubble-wrap.user  { align-self: flex-end; align-items: flex-end; }
    .bubble-wrap.agent { align-self: flex-start; align-items: flex-start; }

    .bubble {
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 14px;
      line-height: 1.45;
      word-break: break-word;
      box-shadow: 0 1px 1px rgba(0,0,0,.12);
      position: relative;
    }
    .bubble.user  { background: #dcf8c6; border-bottom-right-radius: 2px; }
    .bubble.agent { background: #fff;    border-bottom-left-radius: 2px; }

    .bubble .meta {
      font-size: 11px;
      color: #999;
      margin-top: 4px;
      text-align: right;
    }
    .bubble.agent .meta { text-align: left; }

    .bubble img {
      max-width: 240px;
      border-radius: 6px;
      margin-top: 8px;
      display: block;
    }

    /* typing indicator */
    .typing {
      display: flex; align-items: center; gap: 4px;
      background: #fff;
      padding: 10px 14px;
      border-radius: 8px;
      border-bottom-left-radius: 2px;
      box-shadow: 0 1px 1px rgba(0,0,0,.12);
      align-self: flex-start;
    }
    .typing span {
      width: 8px; height: 8px;
      background: #aaa;
      border-radius: 50%;
      animation: bounce 1.2s infinite;
    }
    .typing span:nth-child(2) { animation-delay: .2s; }
    .typing span:nth-child(3) { animation-delay: .4s; }
    @keyframes bounce {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-6px); }
    }

    /* ── Input bar ── */
    .input-bar {
      background: #f0f0f0;
      padding: 8px 12px;
      display: flex;
      align-items: flex-end;
      gap: 8px;
      flex-shrink: 0;
      border-top: 1px solid #ddd;
    }
    .input-bar textarea {
      flex: 1;
      border: none;
      border-radius: 20px;
      padding: 10px 14px;
      font-size: 14px;
      resize: none;
      outline: none;
      max-height: 100px;
      overflow-y: auto;
      background: #fff;
      line-height: 1.4;
    }
    .send-btn {
      width: 42px; height: 42px;
      background: #075e54;
      border: none;
      border-radius: 50%;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      transition: background .15s;
    }
    .send-btn:hover  { background: #128c7e; }
    .send-btn:active { background: #054d44; }
    .send-btn svg { fill: #fff; width: 20px; height: 20px; }

    /* speaker label above bubble */
    .speaker-label {
      font-size: 11px;
      font-weight: 600;
      margin-bottom: 2px;
      padding: 0 4px;
      color: #555;
    }
    .bubble-wrap.user .speaker-label { color: #075e54; }
  </style>
</head>
<body>

<div class="header">
  <div class="avatar">🛍️</div>
  <div class="header-info">
    <h1>Shop Assistant</h1>
    <span id="endpoint-label">Hybrid Agent</span>
  </div>
  <select class="endpoint-select" id="endpoint-select" onchange="onEndpointChange()">
    <option value="/api/chat">Hybrid</option>
    <option value="/api/chat/tools-only">Tools Only</option>
    <option value="/api/chat/context-only">Context Only</option>
  </select>
  <button class="clear-btn" onclick="clearChat()">Clear</button>
</div>

<div class="messages" id="messages"></div>

<div class="input-bar">
  <textarea
    id="input"
    rows="1"
    placeholder="Type a customer message…"
    onkeydown="handleKey(event)"
    oninput="autoResize(this)"
  ></textarea>
  <button class="send-btn" onclick="sendMessage()">
    <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
  </button>
</div>

<script>
  const CUSTOMER_NAME = "Customer";
  const AGENT_NAME    = "Shop Assistant";

  let history = [];   // [{role, content}]

  function onEndpointChange() {
    const labels = {
      "/api/chat":              "Hybrid Agent",
      "/api/chat/tools-only":   "Tools Only Agent",
      "/api/chat/context-only": "Context Only Agent",
    };
    document.getElementById("endpoint-label").textContent =
      labels[document.getElementById("endpoint-select").value];
  }

  function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 100) + "px";
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function clearChat() {
    history = [];
    document.getElementById("messages").innerHTML = "";
  }

  function now() {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function appendBubble(role, text, imageUrl, time) {
    const wrap = document.createElement("div");
    wrap.className = `bubble-wrap ${role}`;

    const label = document.createElement("div");
    label.className = "speaker-label";
    label.textContent = role === "user" ? CUSTOMER_NAME : AGENT_NAME;
    wrap.appendChild(label);

    const bubble = document.createElement("div");
    bubble.className = `bubble ${role}`;

    const textNode = document.createElement("span");
    textNode.textContent = text;
    bubble.appendChild(textNode);

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
    document.getElementById("messages").appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "typing";
    el.id = "typing-indicator";
    el.innerHTML = "<span></span><span></span><span></span>";
    document.getElementById("messages").appendChild(el);
    scrollToBottom();
  }

  function removeTyping() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
  }

  function scrollToBottom() {
    const box = document.getElementById("messages");
    box.scrollTop = box.scrollHeight;
  }

  async function sendMessage() {
    const input = document.getElementById("input");
    const text  = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    const time = now();
    appendBubble("user", text, null, time);
    history.push({ role: "user", content: text });

    showTyping();

    const endpoint = document.getElementById("endpoint-select").value;

    try {
      const res = await fetch(endpoint, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ messages: history }),
      });

      removeTyping();

      if (!res.ok) {
        const err = await res.text();
        appendBubble("agent", `⚠️ Error ${res.status}: ${err}`, null, now());
        return;
      }

      const data = await res.json();
      appendBubble("agent", data.message, data.image_url || null, now());
      history.push({ role: "assistant", content: data.message });

    } catch (err) {
      removeTyping();
      appendBubble("agent", `⚠️ Could not reach the server. Is it running?`, null, now());
    }
  }

  // focus input on load
  document.getElementById("input").focus();
</script>
</body>
</html>
"""


@router.get("/test", response_class=HTMLResponse, include_in_schema=False)
async def test_ui():
    return HTMLResponse(content=_HTML)
