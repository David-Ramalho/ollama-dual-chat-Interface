# ECHO // DUAL MIND

> A local, privacy-first interface that lets two AI models talk to each other — or both respond to you — powered by Ollama and a lightweight Flask proxy with built-in RAG memory injection.

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
- **Feed long-term memory** to either model via a RAG (Retrieval-Augmented Generation) pipeline that reads from plain `.txt` files on your machine — no vector database, no cloud.

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
  - [Frontend — index.html](#frontend--indexhtml)
  - [Streaming Protocol](#streaming-protocol)
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
│   Fetch → /api/chat  /api/tags  /api/rag/*           │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (port 8080)
┌──────────────────────▼──────────────────────────────┐
│              Flask Server (echo_server.py)           │
│                                                      │
│  ┌───────────┐   ┌──────────────┐   ┌────────────┐  │
│  │  RAG      │   │  CORS Proxy  │   │  Static    │  │
│  │  Engine   │   │  /api/chat   │   │  File      │  │
│  │  (in-mem) │   │  /api/tags   │   │  Server    │  │
│  └─────┬─────┘   └──────┬───────┘   └────────────┘  │
│        │ context inject │ forward                    │
└────────┼───────────────┼────────────────────────────┘
         │               │ HTTP (port 11434)
         └───────────────▼
              Ollama API  (local)
         ┌─────────────────────┐
         │   Model A (qwen3)   │
         │   Model B (llama3)  │
         │   ...               │
         └─────────────────────┘
```

The Flask server has three jobs:

1. **Solve CORS** — browsers block direct `fetch()` to `localhost:11434`. The proxy removes that restriction without touching Ollama's config.
2. **Inject RAG context** — before forwarding a chat request, the server can prepend retrieved memory chunks from your `.txt` files into the system prompt.
3. **Serve the UI** — the single `index.html` file is served as a static asset, so the whole app runs from one `python echo_server.py` command.

---

## Feature List

| Feature | Details |
|---|---|
| **Dual Model** | Two independent Ollama models, each with its own system prompt and parameters |
| **Auto Mode** | Fully autonomous AI ↔ AI conversation for N configurable turns |
| **Manual / Inject Mode** | Send your own message and both models respond sequentially |
| **Per-Model Parameters** | Temperature, Top-P, Top-K, Max Tokens, Repeat Penalty — set independently per side |
| **RAG Memory** | Load a folder of `.txt` files; relevant chunks are injected into the system prompt per query |
| **Streaming** | Responses stream token-by-token using NDJSON; UI updates in real time |
| **Thinking Tag Support** | Detects `<think>...</think>` blocks (native or embedded) and renders them in a collapsible aside |
| **VRAM Management** | Unload model A, B, or both from VRAM with one click (`keep_alive: 0`) |
| **Chat Export** | Download the full conversation (including thinking blocks) as a `.txt` file |
| **Zero Dependencies UI** | Pure HTML/CSS/JS — no build step, no npm |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.8+ | Tested on 3.10 and 3.11 |
| Ollama | Running locally at `http://localhost:11434` |
| At least one Ollama model pulled | e.g. `ollama pull qwen3:1.7b` |
| pip packages | `flask`, `requests`, `flask-cors` |

Install Python dependencies:

```bash
pip install flask requests flask-cors
```

Ollama installation: https://ollama.com

---

## Installation

```bash
# 1. Clone or download the repo
git clone https://github.com/yourname/echo-dual-mind.git
cd echo-dual-mind

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
echo-dual-mind/
├── echo_server.py       ← Flask backend (proxy + RAG + static server)
└── echo_ui/
    └── index.html       ← Complete frontend (HTML + CSS + JS, single file)
```

---

## Technical Deep Dive

### Backend — echo_server.py

The server is a single-file Flask application with no database, no ORM, no task queue. All state is held in memory at the process level.

**Initialization:**

```python
app = Flask(__name__, static_folder='echo_ui')
CORS(app)
OLLAMA_URL = "http://localhost:11434"
```

`flask-cors` adds `Access-Control-Allow-Origin: *` to every response, which is what lets the browser's `fetch()` calls reach the proxy without CORS errors. `static_folder='echo_ui'` tells Flask where to find `index.html` and any other assets.

**Proxy routes:**

The `/api/tags`, `/api/generate`, and `/api/chat` routes are thin wrappers around Ollama's native API. They accept the same request shape and forward it unchanged, except `/api/chat` which may inject RAG context first.

For streaming responses, Flask uses Python generators:

```python
def generate():
    for chunk in r.iter_content(chunk_size=None):
        yield chunk
return Response(generate(), content_type='application/x-ndjson')
```

This keeps memory constant regardless of response length — chunks are forwarded to the browser as they arrive from Ollama without buffering the full response.

---

### RAG System

RAG (Retrieval-Augmented Generation) allows the models to "remember" information from your text files. Echo implements a simple, dependency-free version:

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

Each `.txt` file is split into overlapping windows of 500 words with a 50-word overlap. The overlap prevents information loss at chunk boundaries — a sentence that crosses a boundary will be partially present in both adjacent chunks.

**Step 2 — Scoring (BM25-inspired keyword overlap):**

```python
def simple_score(query, text):
    query_words = set(re.findall(r'\w+', query.lower()))
    text_words  = set(re.findall(r'\w+', text.lower()))
    # remove stop words from both sets
    ...
    overlap = query_words & text_words
    return len(overlap) / math.sqrt(len(query_words) * max(len(text_words), 1))
```

This is a cosine-similarity-like score computed over word sets rather than TF-IDF vectors. The `math.sqrt` normalization penalizes very short or very long chunks from dominating results — functionally similar to the IDF component of BM25 without requiring a pre-built index. No external libraries (numpy, scikit-learn, faiss) are needed.

**Step 3 — Injection:**

When `use_rag: true` arrives in a chat request, the server retrieves the top-5 scoring chunks for the last user message and prepends them to the system prompt:

```python
rag_context = "\n\n### Personal Memory Context:\n"
for r in results:
    rag_context += f"[{r['source']}] {r['text']}\n\n"

if messages[0]['role'] == 'system':
    messages[0]['content'] += rag_context   # append to existing system prompt
else:
    messages.insert(0, {'role': 'system', 'content': rag_context.strip()})
```

The source filename is included so the model can cite where a memory came from.

**Trade-offs vs. vector RAG:**

| | Echo (keyword) | Vector RAG |
|---|---|---|
| Dependencies | None | sentence-transformers, faiss/chromadb |
| Semantic matching | No | Yes |
| Speed | Very fast | Fast (after indexing) |
| Works on any hardware | Yes | Requires CPU/GPU for embeddings |
| Best for | Personal logs, structured notes | Large, diverse corpora |

---

### Frontend — index.html

The entire UI is a self-contained HTML file with inline `<style>` and `<script>`. No framework, no build tools. Key design decisions:

**CSS custom properties** define the entire color palette:

```css
:root {
  --a: #7c6aff;   /* Model A — purple */
  --b: #ff6a9a;   /* Model B — pink   */
  --c: #6affdd;   /* RAG / system — cyan */
  --u: #ffd86a;   /* User — gold     */
}
```

These propagate everywhere via `var()`, making the whole theme adjustable from one place.

**State** is three JavaScript variables at module level:

```js
let running = false;    // is a generation in progress?
let stop    = false;    // user hit stop?
let convHistory = [];   // [{role, content, model?}] — full conversation
let chatLog     = [];   // for export — includes think blocks and sys messages
```

There is intentionally no framework-managed state. The DOM is the source of truth for visual state; `convHistory` is the source of truth for what gets sent to the API.

---

### Streaming Protocol

Ollama's streaming chat endpoint returns newline-delimited JSON (NDJSON). Each line is a JSON object like:

```json
{"model":"qwen3:1.7b","message":{"role":"assistant","content":"Hello"},"done":false}
```

The `stream()` function in the UI reads this with the Fetch Streams API:

```js
const reader = res.body.getReader();
const dec    = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const lines = dec.decode(value).split('\n').filter(l => l.trim());
  for (const line of lines) {
    const j = JSON.parse(line);
    if (j.message.thinking) thinking += j.message.thinking;  // native think field
    if (j.message.content)  response += j.message.content;   // text content
    // throttled UI update every 40ms
    if (Date.now() - lastUI > 40) { updateMsg(el, display); lastUI = Date.now(); }
  }
}
```

The 40ms throttle prevents the browser from repainting the DOM on every single token (which would cause jank at high token rates). Instead, accumulated content is flushed to the DOM at ~25fps.

Two sources of "thinking" content are handled:

- **Native field** — some models (LFM2.5-thinking, certain Qwen variants) emit a separate `message.thinking` JSON field alongside `message.content`.
- **Embedded tags** — models that output `<think>...</think>` inline in their content string. The `parseThink()` function handles both complete tags and mid-stream incomplete tags.

---

### Thinking Tag Renderer

```js
function parseThink(raw) {
  // Complete tag: <think>...</think> already closed
  var m = raw.match(/<think>([\s\S]*?)<\/think>/);
  if (m) { ... }

  // Partial tag: still streaming inside <think>
  var oi = raw.indexOf('<think>');
  if (oi !== -1) { ... }

  // No tags: plain response
  return { thinkHtml: '', responseHtml: renderMd(raw.trim()) };
}
```

The function handles three states because the stream is processed incrementally. During generation, the `</think>` closing tag hasn't arrived yet — the renderer shows a live "THINKING..." block. Once the full tag is received, it switches to the finalized collapsed block.

A lightweight Markdown renderer (`renderMd`) handles bold, italic, `##`/`###` headings, and `---` horizontal rules via regex — enough for model outputs without the overhead of a library like `marked.js`.

---

### Conversation History & Role Mapping

This is the most subtle part of the system. Ollama's chat API expects a flat `messages` array with roles `system`, `user`, `assistant`. In a two-model conversation, both models need to see the same history — but each needs to interpret its own turns as `assistant` and the other model's turns as `user`.

The `buildMsgs()` function handles this mapping:

```js
function buildMsgs(history, isA, mA, mB, sysPrompt) {
  const msgs = [];
  if (sysPrompt) msgs.push({ role: 'system', content: sysPrompt });

  let assistantTurn = 0; // 0 = A spoke, 1 = B spoke, alternating

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
  return msgs;
}
```

**Example** — history after 2 auto turns (A then B), now building for Model B's next turn:

| Raw history turn | `wasA` | `isA` (B) | Assigned role |
|---|---|---|---|
| A's first response | true | false | `user` |
| B's first response | false | false | `assistant` |

This correctly makes Model B see itself as the assistant and Model A as the user — even when both are the same model (`mA === mB`).

---

## Configuration Reference

**Server** (`echo_server.py`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API base URL |
| Flask port | `8080` | Set in `app.run(port=8080)` |
| `chunk_size` | `500` words | RAG chunk size |
| `overlap` | `50` words | RAG chunk overlap |
| `top_k` (RAG) | `5` | Number of context chunks injected per request |

**UI per-model parameters** (set in the Settings panel):

| Parameter | Default | Ollama field | Effect |
|---|---|---|---|
| Temperature | 0.7 | `temperature` | Randomness of sampling |
| Top P | 0.9 | `top_p` | Nucleus sampling threshold |
| Top K | 40 | `top_k` | Vocabulary top-K cutoff |
| Max Tokens | 2048 | `num_predict` | Maximum tokens generated |
| Repeat Penalty | 1.1 | `repeat_penalty` | Penalizes repeated n-grams |

---

## API Reference

All routes are served by `echo_server.py` on port `8080`.

### `GET /api/tags`
Returns available Ollama models. Proxies `GET http://localhost:11434/api/tags`.

### `POST /api/chat`
Proxies Ollama's chat endpoint with optional RAG injection.

**Extra field (stripped before forwarding):**
```json
{ "use_rag": true }
```
When `true` and RAG files are loaded, context chunks are injected into the system prompt before the request is forwarded.

### `POST /api/generate`
Proxies Ollama's generate endpoint (used for model warm-up).

### `POST /api/rag/load`
Loads all `.txt` files from a local directory into the in-memory RAG index.
```json
{ "folder": "C:/path/to/your/memory/files" }
```
Returns: `{ "chunks": 342, "files": 7 }`

### `GET /api/rag/status`
Returns current RAG state:
```json
{ "loaded": true, "chunks": 342, "files": ["chat_2024.txt", "notes.txt"] }
```

### `POST /api/rag/retrieve`
Debug endpoint. Returns top-K matching chunks for a query:
```json
{ "query": "my favourite food", "top_k": 3 }
```

---

## Usage Guide

### Auto Mode — AI ↔ AI Conversation

1. Select **Model A** and **Model B** from the dropdowns (can be the same model).
2. Optionally open **⚙ Settings** to set a different system prompt and parameters for each model.
3. Set the number of **Turns** (each turn = one model responding).
4. Optionally type a **seed message** in the input bar — this becomes the conversation starter.
5. Press **▶ AUTO**.

The conversation alternates: A → B → A → B → ... The seed message is treated as the initial user message. If no seed is typed, a default greeting is used.

Press **■ STOP** at any time to halt mid-conversation.

### Manual Mode — You Talk to Both

1. Select at least **Model A** (Model B is optional).
2. Type your message and press **SEND** (or Enter).
3. Model A responds first, then Model B (if selected) responds with full awareness of Model A's answer.

### RAG Memory

1. Open the **◈ RAG** panel.
2. Enter the full path to a folder containing `.txt` files (chat logs, notes, documents).
3. Click **LOAD FILES** — the server reads and chunks all `.txt` files.
4. Toggle **USE RAG** on.

From this point, every chat request will silently retrieve the 5 most relevant chunks and prepend them to the model's system prompt. The model sees memory as part of its context, not as a separate tool call.

### VRAM Management

Running two large models simultaneously requires enough VRAM. Use the **⏏ A**, **⏏ B**, or **⏏ ALL** buttons to send `keep_alive: 0` to Ollama, which immediately evicts the model weights from GPU memory. This is useful when switching to a different model pair.

### Exporting Conversations

Click **↓ SAVE TXT** to download the full conversation as a plain text file, including:
- Model names and system prompts used
- Whether RAG was enabled
- All messages in order
- `<think>` blocks where present

---

## FAQ

**Q: Can I use models from different providers (e.g., OpenAI + Ollama)?**  
Not natively — the proxy is Ollama-specific. You could extend `echo_server.py` to add a second proxy route pointing to a different API and update the UI's `fetch` target per side.

**Q: My RAG results seem irrelevant. How do I improve them?**  
The keyword scorer works best with specific, factual text. Very conversational or ambiguous queries may not match well. For better semantic retrieval, you could replace `simple_score()` with a proper embedding model (e.g., `sentence-transformers`) and cosine similarity — the RAG pipeline architecture is ready for that swap.

**Q: Both models respond simultaneously or sequentially?**  
Sequential. Model A completes its full response before Model B starts. Model B receives Model A's response in its conversation history, so it's aware of and can react to what Model A said.

**Q: What happens if Ollama is offline?**  
The UI shows `OLLAMA OFFLINE` in the status pill. The model dropdowns display "Cannot reach server". No crash — just degraded state until Ollama comes back.

**Q: Can I run this on a server and share it on a network?**  
Yes. Change `app.run(host='0.0.0.0', port=8080)` is already the default. Access from other machines via `http://your-server-ip:8080`. For internet exposure, use a reverse proxy (nginx) or a tunnel like ngrok.

---

## Credits

- [Ollama](https://ollama.com) — local model serving
- [Flask](https://flask.palletsprojects.com) — Python web framework
- [JetBrains Mono](https://www.jetbrains.com/legalnotice/fonts/) + [Syne](https://fonts.google.com/specimen/Syne) — fonts used in the UI
