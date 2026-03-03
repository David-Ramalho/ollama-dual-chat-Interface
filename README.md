# ECHO // DUAL MIND

> A local, privacy-first interface that lets two AI models talk to each other — or both respond to you — powered by Ollama and a lightweight Flask proxy with built-in RAG memory injection, persistent chat history, and real-time token monitoring.

```
 ╔═══════════════════════════════════╗
 ║   MODEL A  ↔  [YOU]  ↔  MODEL B  ║
 ║   Auto conversation or dual reply  ║
 ╚═══════════════════════════════════╝
```

---

## What Is Echo Dual Mind?

Echo Dual Mind is a self-hosted, two-model chat environment. Instead of talking to one AI at a time, you can:

- **Run two models simultaneously** — each with its own personality, system prompt, and inference parameters.
- **Watch two models talk to each other** autonomously for N turns, seeded by your message.
- **Inject yourself** into the conversation at any point.
- **Feed long-term memory** to either model via a RAG pipeline that reads from plain `.txt` files — no vector database, no cloud.
- **Save and reload every conversation** from a persistent sidebar with folder organisation.

Everything runs locally. No API keys. No data sent anywhere except to your own Ollama instance.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Feature List](#feature-list)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Technical Deep Dive](#technical-deep-dive)
  - [Backend — echo_server.py](#backend--echo_serverpy)
  - [RAG System](#rag-system)
  - [RAG Controls & Chunk Estimator](#rag-controls--chunk-estimator)
  - [Chat Persistence](#chat-persistence)
  - [Frontend — index.html](#frontend--indexhtml)
  - [Streaming Protocol & Token Counters](#streaming-protocol--token-counters)
  - [Thinking Tag Renderer](#thinking-tag-renderer)
  - [Conversation History & Role Mapping](#conversation-history--role-mapping)
- [Configuration Reference](#configuration-reference)
- [API Reference](#api-reference)
- [Usage Guide](#usage-guide)
- [FAQ](#faq)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Browser (UI)                       │
│               echo_ui/index.html                     │
│  Fetch → /api/chat  /api/tags  /api/rag/*            │
│          /api/chats/*  (chat persistence)            │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (port 8080)
┌──────────────────────▼──────────────────────────────┐
│              Flask Server (echo_server.py)           │
│                                                      │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  RAG      │  │  CORS Proxy  │  │  Chat Store  │  │
│  │  Engine   │  │  /api/chat   │  │  echo_chats/ │  │
│  │  (in-mem) │  │  /api/tags   │  │  (JSON files)│  │
│  └─────┬─────┘  └──────┬───────┘  └──────────────┘  │
│        │ inject        │ forward                     │
└────────┼───────────────┼─────────────────────────────┘
         │               │ HTTP (port 11434)
         └───────────────▼
              Ollama API  (local)
         ┌─────────────────────┐
         │   Model A           │
         │   Model B           │
         └─────────────────────┘
```

The Flask server has four jobs:

1. **Solve CORS** — browsers block direct `fetch()` to `localhost:11434`. The proxy removes that restriction without touching Ollama's config.
2. **Inject RAG context** — before forwarding a chat request, the server retrieves relevant chunks from your `.txt` files and prepends them to the system prompt.
3. **Persist chats** — saves and loads conversations as JSON files in `echo_chats/` next to the server file.
4. **Serve the UI** — the single `index.html` is served as a static asset, so the entire app runs from one `python echo_server.py` command.

---

## Feature List

| Feature | Details |
|---|---|
| **Dual Model** | Two independent Ollama models, each with its own system prompt and parameters |
| **Auto Mode** | Fully autonomous AI ↔ AI conversation for N configurable turns |
| **Turn Countdown** | Live header pill showing current turn / total (e.g. `TURN 3 / 10`) during AUTO |
| **Manual / Inject Mode** | Send your own message; both models respond sequentially |
| **Per-Model Parameters** | Temperature, Top-P, Top-K, Max Tokens, Repeat Penalty, Context Length — set independently per side |
| **Context Length Control** | Set `num_ctx` per model — controls the KV cache / context window Ollama allocates |
| **Token Counters** | Per-message `↑ ctx · ↓ gen` badge + persistent header pills showing prompt tokens in and response tokens out |
| **RAG Memory** | Load a folder of `.txt` files; relevant chunks injected into system prompt per query |
| **RAG Chunk Controls** | Chunk size, overlap, and retrieve top-K all configurable from the UI without restarting |
| **RAG Chunk Estimator** | Enter a file character count; UI instantly shows estimated words, chunks produced, and chunks retrieved |
| **RAG Retrieval Log** | Per-query log showing which file and text chunk was retrieved, with timestamps |
| **Chat Sidebar** | Collapsible left panel listing all saved chats; click to reload any past session |
| **Chat Auto-Save** | Every session saves automatically to `echo_chats/` as JSON when it ends |
| **Chat Folders** | Create named folders; right-click any chat to move it |
| **Full State Restore** | Loading a chat restores models, system prompts, all parameters, and RAG settings |
| **Streaming** | Responses stream token-by-token using NDJSON; UI updates in real time |
| **Smart Scroll** | Auto-scroll follows new tokens only when near the bottom — scrolling up to read pauses it |
| **Thinking Tag Support** | Detects `<think>...</think>` blocks (native field or embedded) and renders them separately |
| **VRAM Management** | Unload model A, B, or both from VRAM with one click (`keep_alive: 0`) |
| **Chat Export** | Download the full conversation including thinking blocks as `.txt` |
| **Zero Dependencies UI** | Pure HTML/CSS/JS — no build step, no npm |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.8+ | Tested on 3.10 and 3.11 |
| Ollama | Running locally at `http://localhost:11434` |
| At least one Ollama model pulled | e.g. `ollama pull qwen3:1.7b` |
| pip packages | `flask`, `requests`, `flask-cors` |

```bash
pip install flask requests flask-cors
```

Ollama installation: https://ollama.com

---

## Installation

```bash
# 1. Clone or download the repo
git clone https://github.com/yourname/ollama-dual-chat.git
cd ollama-dual-chat

# 2. Make sure Ollama is running and you have at least one model
ollama pull qwen3:1.7b      # model A suggestion
ollama pull llama3.1:8b     # model B suggestion

# 3. Install dependencies
pip install flask requests flask-cors

# 4. Run the server
python echo_server.py

# 5. Open the UI
# http://localhost:8080
```

The terminal will show:

```
═══════════════════════════════════════════════════════
  ECHO DUAL CHAT SERVER
═══════════════════════════════════════════════════════
  UI:     http://localhost:8080
  Ollama: http://localhost:11434
═══════════════════════════════════════════════════════
```

---

## Project Structure

```
ollama-dual-chat/
├── echo_server.py       ← Flask backend (proxy + RAG + chat persistence)
├── echo_chats/          ← Auto-created; stores saved chats as JSON
│   ├── 2026-03-01T...json
│   └── my-folder/
│       └── 2026-03-02T...json
└── echo_ui/
    └── index.html       ← Complete frontend (HTML + CSS + JS, single file)
```

---

## Technical Deep Dive

### Backend — echo_server.py

The server is a single-file Flask application with no database, no ORM, no task queue. All state is held in memory at the process level, except for chat history which is written to disk as JSON.

`flask-cors` adds `Access-Control-Allow-Origin: *` to every response, letting the browser's `fetch()` reach the proxy without CORS errors. For streaming responses, Flask uses Python generators to forward chunks as they arrive without buffering:

```python
def generate():
    for chunk in r.iter_content(chunk_size=None):
        yield chunk
return Response(generate(), content_type='application/x-ndjson')
```

---

### RAG System

RAG (Retrieval-Augmented Generation) allows the models to "remember" information from your text files. Echo implements a simple, dependency-free version.

**Step 1 — Chunking:**

```python
def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = ' '.join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
```

Each `.txt` file is split into overlapping word windows. The overlap prevents information loss at chunk boundaries. Both `chunk_size` and `overlap` are configurable from the UI at load time — no server restart needed.

**Step 2 — Scoring:**

```python
def simple_score(query, text):
    query_words = set(re.findall(r'\w+', query.lower()))
    text_words  = set(re.findall(r'\w+', text.lower()))
    # remove stop words...
    overlap = query_words & text_words
    return len(overlap) / math.sqrt(len(query_words) * max(len(text_words), 1))
```

Keyword overlap with `sqrt` normalization — functionally similar to BM25 without a pre-built index. No numpy, no faiss.

**Step 3 — Injection & Logging:**

When `use_rag: true` arrives in a chat request, the server retrieves the top-K scoring chunks for the last user message and prepends them to the system prompt. Every retrieval is appended to the in-memory `rag_log` (capped at 100 entries):

```python
rag_log.append({
    'time':   datetime.datetime.now().strftime('%H:%M:%S'),
    'query':  last_user[:100],
    'chunks': [{'source': r['source'], 'preview': r['text'][:150]} for r in results]
})
```

The UI displays this log inside the RAG panel with file names, timestamps, and chunk previews so you can see exactly what the model received.

**Trade-offs vs. vector RAG:**

| | Echo (keyword) | Vector RAG |
|---|---|---|
| Dependencies | None | sentence-transformers, faiss/chromadb |
| Semantic matching | No | Yes |
| Speed | Very fast | Fast (after indexing) |
| Works on any hardware | Yes | Requires CPU/GPU for embeddings |
| Best for | Personal logs, structured notes | Large, diverse corpora |

---

### RAG Controls & Chunk Estimator

All chunking parameters are exposed in the UI and sent to the server at load time:

| Control | Default | Effect |
|---|---|---|
| Chunk Size | 500 words | Words per chunk. Increase to keep more of a file in a single chunk. |
| Overlap | 50 words | Shared words between adjacent chunks. Prevents boundary gaps. |
| Retrieve Top-K | 5 | Chunks injected per query. More = broader recall, higher context cost. |

**Chunk Estimator** lets you predict the chunking result before loading:

```
chars ÷ 4.97 ≈ word count   (calibrated: 3,845 chars = 773 words)

chunks = ceil((words - chunk_size) / (chunk_size - overlap)) + 1
retrieved = min(top_k, chunks)
```

This lets you tune `chunk_size` until a small file fits in one chunk, guaranteeing the model always receives the full content of that file.

---

### Chat Persistence

Chats are saved as JSON files in `echo_chats/` next to `echo_server.py`. The directory is created automatically on first run.

**Auto-save logic** uses a `chatDirty` flag that becomes `true` only when new messages are generated. `endSession()` only saves when `chatDirty` is true, which prevents re-saving a chat that was just loaded from disk (the duplication bug this solves).

Each saved file contains:

```json
{
  "id": "2026-03-03T17-38-00",
  "title": "03/03/2026 17:38",
  "modelA": "qwen3:1.7b",
  "modelB": "llama3.1:8b",
  "settings": {
    "sysA": "...", "sysB": "...",
    "tempA": "0.7", "ctxA": "4096",
    "ragPath": "C:/...", "useRag": true
  },
  "log": [...]
}
```

Loading restores everything: models, both system prompts, all 14 parameter fields, RAG folder path, chunk settings, and the USE RAG toggle state.

**Folders** are physical subdirectories inside `echo_chats/`. Right-click any chat in the sidebar to move it into a folder via the `POST /api/chats/move` endpoint.

---

### Frontend — index.html

The entire UI is a self-contained HTML file with inline `<style>` and `<script>`. No framework, no build tools.

**Layout** — the page is a flex row: a collapsible `#sidebar` (220px) on the left and the main `#app` taking the rest. The sidebar collapses to a 32px strip.

**State variables:**

```js
let running      = false;   // generation in progress
let stop         = false;   // user hit stop
let chatDirty    = false;   // new messages generated since last save/load
let activeChatId = null;    // ID of the currently loaded chat file
let convHistory  = [];      // messages sent to Ollama on each request
let chatLog      = [];      // full log for export and auto-save
```

**CSS custom properties** define the entire colour palette from one place:

```css
:root {
  --a: #7c6aff;   /* Model A — purple */
  --b: #ff6a9a;   /* Model B — pink   */
  --c: #6affdd;   /* RAG / system — cyan */
  --u: #ffd86a;   /* User — gold     */
}
```

---

### Streaming Protocol & Token Counters

Ollama's streaming endpoint returns NDJSON. The final chunk (`done: true`) carries token usage:

```js
if (j.done) {
  promptTokens = j.prompt_eval_count || 0;  // tokens sent into the model
  evalTokens   = j.eval_count        || 0;  // tokens the model generated
}
```

**Reading the counters:**

- **↑ ctx** — tokens sent *up* to the model: system prompt + full conversation history + RAG chunks. This number grows each turn as history accumulates. Compare it to your Context Length setting to know how much budget remains before the model starts losing early context.
- **↓ gen** — tokens generated *down* from the model in its response.

These appear as a badge under each bubble (`↑ 947 ctx · ↓ 400 gen`) and as persistent header pills that update each turn.

**Smart scroll** — `scrollBottom()` only auto-scrolls when the user is within 80px of the bottom:

```js
function scrollBottom() {
  const c = document.getElementById('chat');
  const distFromBottom = c.scrollHeight - c.scrollTop - c.clientHeight;
  if (distFromBottom < 80) c.scrollTop = c.scrollHeight;
}
```

Scrolling up to read pauses auto-scroll. It resumes when you scroll back down.

---

### Thinking Tag Renderer

The `parseThink()` function handles three states because the stream is processed incrementally:

```js
function parseThink(raw) {
  // Complete tag — already closed
  var m = raw.match(/<think>([\s\S]*?)<\/think>/);
  if (m) { ... }

  // Partial tag — still streaming inside <think>
  var oi = raw.indexOf('<think>');
  if (oi !== -1) { ... }

  // No tags — plain response
  return { thinkHtml: '', responseHtml: renderMd(raw.trim()) };
}
```

Two thinking sources are supported: a native `message.thinking` JSON field (LFM2.5-thinking, some Qwen variants) and inline `<think>` tags embedded in the response content string.

---

### Conversation History & Role Mapping

Ollama expects roles `system`, `user`, `assistant`. In a two-model conversation each model needs to see its own turns as `assistant` and the other's as `user`. The `buildMsgs()` function handles this — and works correctly even when both slots use the same model:

```js
function buildMsgs(history, isA, mA, mB, sysPrompt) {
  let assistantTurn = 0;
  for (const h of history) {
    if (h.role === 'user') {
      msgs.push({ role: 'user', content: h.content });
    } else {
      const wasA = (assistantTurn % 2 === 0);
      msgs.push({
        role: (wasA === isA) ? 'assistant' : 'user',
        content: h.content
      });
      assistantTurn++;
    }
  }
}
```

---

## Configuration Reference

**Server** (`echo_server.py`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API base URL |
| Flask port | `8080` | Set in `app.run(port=8080)` |
| `CHATS_DIR` | `./echo_chats/` | Chat save directory (auto-created next to server file) |

**UI per-model parameters** (saved with each chat):

| Parameter | Default | Ollama field | Effect |
|---|---|---|---|
| Temperature | 0.7 | `temperature` | Randomness of sampling |
| Top P | 0.9 | `top_p` | Nucleus sampling threshold |
| Top K | 40 | `top_k` | Vocabulary top-K cutoff |
| Max Tokens | 2048 | `num_predict` | Maximum tokens generated per response |
| Repeat Penalty | 1.1 | `repeat_penalty` | Penalises repeated n-grams |
| Context Length | 4096 | `num_ctx` | KV cache size — max tokens the model can hold in context |

**RAG parameters** (saved with each chat):

| Parameter | Default | Effect |
|---|---|---|
| Chunk Size | 500 words | Words per chunk |
| Overlap | 50 words | Shared words between adjacent chunks |
| Retrieve Top-K | 5 | Chunks injected per query |

---

## API Reference

All routes served on port `8080`.

| Method | Route | Description |
|---|---|---|
| GET | `/api/tags` | Proxy Ollama model list |
| POST | `/api/chat` | Proxy chat with optional RAG injection (`use_rag`, `rag_top_k`) |
| POST | `/api/generate` | Proxy Ollama generate |
| POST | `/api/rag/load` | Load `.txt` files (`folder`, `chunk_size`, `overlap`) |
| GET | `/api/rag/status` | RAG index status |
| POST | `/api/rag/retrieve` | Debug: query the RAG index directly |
| GET | `/api/rag/log` | Retrieval log (last 100 queries) |
| POST | `/api/rag/log/clear` | Clear retrieval log |
| GET | `/api/chats/list` | List all saved chats and folders |
| POST | `/api/chats/save` | Save a chat session |
| GET | `/api/chats/load/<id>` | Load a chat by ID |
| DELETE | `/api/chats/delete/<id>` | Delete a chat |
| POST | `/api/chats/folder` | Create a folder |
| POST | `/api/chats/move` | Move a chat to a folder |

---

## Usage Guide

### Auto Mode — AI ↔ AI Conversation

1. Select **Model A** and **Model B** from the dropdowns.
2. Open **⚙ Settings** to set system prompts and parameters per model.
3. Set the number of **Turns**.
4. Optionally type a **seed message**.
5. Press **▶ AUTO**.

A gold **TURN X / N** pill counts up in the header. Press **■ STOP** at any time. The session auto-saves when it ends.

### Manual Mode — You Talk to Both

Type your message and press **SEND**. Model A responds first, then Model B responds with awareness of what Model A said.

### Token Monitoring

Every response bubble shows `↑ ctx · ↓ gen` after it finishes generating. Watch `↑ ctx` grow across turns — when it approaches your Context Length setting the model will begin losing early history. Increase Context Length (and ensure you have the VRAM for it) to extend the window.

### RAG Memory

1. Open the **◈ RAG** panel.
2. Use the **Estimator** to check how your files will chunk.
3. Tune **Chunk Size**, **Overlap**, and **Top-K** as needed.
4. Click **LOAD FILES**, then toggle **USE RAG** on.
5. Click **◈ VIEW LOG** after a query to see exactly which chunks were injected.

### Chat History

Click any chat in the left sidebar to reload it. All settings are restored. Right-click to move chats into folders. Hover over a chat to reveal the ✕ delete button.

### VRAM Management

Use **⏏ A**, **⏏ B**, or **⏏ ALL** to immediately evict model weights from GPU memory via `keep_alive: 0`.

---

## FAQ

**Q: What exactly are ↑ ctx and ↓ gen?**
`↑ ctx` is the total tokens sent into the model — system prompt + conversation history + RAG chunks. `↓ gen` is the tokens generated in the response. They are absolute counts, not percentages. Compare `↑ ctx` against your Context Length setting to track how much budget is left.

**Q: My RAG results seem irrelevant.**
The keyword scorer only matches exact words. Try more specific terms, increase Chunk Size so files stay in fewer chunks, or paste critical content directly into the system prompt for guaranteed injection. Use the Retrieval Log to debug what was actually matched.

**Q: My file is small but the model ignores it.**
If no query keywords match the chunk, the score is 0 and nothing is injected. Check the Retrieval Log to confirm. The safest option for a single small file is to paste it into the system prompt directly.

**Q: Can I use the same model for both slots?**
Yes. The role mapping in `buildMsgs()` handles this correctly — the model sees its own prior turns as `assistant` and the other slot's turns as `user` regardless of whether they share a name.

**Q: What happens if Ollama is offline?**
The header shows `OLLAMA OFFLINE`. Model dropdowns show "Cannot reach server". The sidebar and all settings remain usable.

**Q: Can I share this on a network?**
Yes — `app.run(host='0.0.0.0', port=8080)` is the default. Access via `http://your-server-ip:8080`. For internet exposure use nginx or ngrok.

---

## Credits

- [Ollama](https://ollama.com) — local model serving
- [Flask](https://flask.palletsprojects.com) — Python web framework
- [JetBrains Mono](https://www.jetbrains.com/legalnotice/fonts/) + [Syne](https://fonts.google.com/specimen/Syne) — fonts used in the UI
