"""
Echo // Multi-Mind v0.85
- Keyword RAG + Ollama Embedding RAG
- Knowledge Base persistence (saved to echo_knowledge/)
- Chat & folder persistence (echo_chats/)
- Custom Model Profiles (echo_profiles/profiles.json)
- Multi-AI Systems Presets (echo_systems/systems.json)
- Embedding: auto-truncates chunks that exceed model context window
- KB load: filters empty-embedding chunks instead of blocking
- v0.80: Chat duplication, Systems presets, Skip/Pause flow control,
         Global stop fix, Context role-mapping fix, RAG log fix
- v0.85: Fix streaming disconnect (ChunkedEncodingError on client abort),
          Fix clearAll deletes server-side file, Fix sidebar live updates

Install: pip install flask requests flask-cors
Run:     python echo_server.py
"""

import os
import re
import json
import math
import time
import datetime
import requests
import threading
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='echo_ui')
CORS(app)

OLLAMA_URL    = "http://localhost:11434"
CHATS_DIR     = Path(__file__).parent / 'echo_chats'
KNOWLEDGE_DIR = Path(__file__).parent / 'echo_knowledge'
PROFILES_DIR  = Path(__file__).parent / 'echo_profiles'
SYSTEMS_DIR   = Path(__file__).parent / 'echo_systems'
MODELS_FILE   = PROFILES_DIR / 'profiles.json'
SYSTEMS_FILE  = SYSTEMS_DIR  / 'systems.json'
CHATS_DIR.mkdir(exist_ok=True)
KNOWLEDGE_DIR.mkdir(exist_ok=True)
PROFILES_DIR.mkdir(exist_ok=True)
SYSTEMS_DIR.mkdir(exist_ok=True)

# Migrate legacy echo_models.json → echo_profiles/profiles.json
_legacy = Path(__file__).parent / 'echo_models.json'
if _legacy.exists() and not MODELS_FILE.exists():
    try:
        MODELS_FILE.write_text(_legacy.read_text(encoding='utf-8'), encoding='utf-8')
        _legacy.rename(_legacy.with_suffix('.json.bak'))
        print("[PROFILES] Migrated echo_models.json → echo_profiles/profiles.json")
    except Exception as _e:
        print(f"[PROFILES] Migration warning: {_e}")

# ─── RAG STATE ───────────────────────────────────────────────────────────────

rag_chunks     = []   # keyword mode: [{text, source}]
rag_embeddings = []   # embedding mode: [{text, source, embedding:[float]}]
rag_loaded     = False
rag_log        = []   # last 100 retrieval events
embed_progress = {'total': 0, 'done': 0, 'running': False, 'error': '', 'model': ''}

# ─── CHAT STORAGE ────────────────────────────────────────────────────────────

def chats_meta():
    chats   = []
    folders = set()
    try:
        for entry in CHATS_DIR.iterdir():
            if entry.is_dir():
                folders.add(entry.name)
    except Exception:
        pass
    for f in CHATS_DIR.rglob('*.json'):
        try:
            data   = json.loads(f.read_text(encoding='utf-8'))
            folder = f.parent.name if f.parent != CHATS_DIR else ''
            chats.append({
                'id':     data.get('id', f.stem),
                'title':  data.get('title', f.stem),
                'date':   data.get('date', ''),
                'modelA': data.get('modelA', ''),
                'modelB': data.get('modelB', ''),
                'models': data.get('models', []),
                'folder': folder,
            })
        except Exception:
            pass
    chats.sort(key=lambda x: x['id'], reverse=True)
    return chats, sorted(folders)

@app.route('/api/chats/list', methods=['GET'])
def api_chats_list():
    chats, folders = chats_meta()
    return jsonify({'chats': chats, 'folders': folders})

@app.route('/api/chats/save', methods=['POST'])
def api_chats_save():
    data    = request.json or {}
    chat_id = data.get('id', '')
    folder  = data.get('folder', '').strip()
    if not chat_id:
        return jsonify({'error': 'No id'}), 400
    target_dir = CHATS_DIR / folder if folder else CHATS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{chat_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return jsonify({'ok': True, 'path': str(path)})

@app.route('/api/chats/load/<path:chat_id>', methods=['GET'])
def api_chats_load(chat_id):
    for f in CHATS_DIR.rglob(f"{chat_id}.json"):
        try:
            return jsonify(json.loads(f.read_text(encoding='utf-8')))
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/chats/delete/<path:chat_id>', methods=['DELETE'])
def api_chats_delete(chat_id):
    for f in CHATS_DIR.rglob(f"{chat_id}.json"):
        f.unlink()
        return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/chats/folder', methods=['POST'])
def api_chats_folder():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'No name'}), 400
    (CHATS_DIR / name).mkdir(parents=True, exist_ok=True)
    return jsonify({'ok': True})

@app.route('/api/chats/move', methods=['POST'])
def api_chats_move():
    data    = request.json or {}
    chat_id = data.get('id', '')
    folder  = data.get('folder', '').strip()
    for f in CHATS_DIR.rglob(f"{chat_id}.json"):
        target_dir = CHATS_DIR / folder if folder else CHATS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        new_path = target_dir / f.name
        f.rename(new_path)
        return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/chats/duplicate/<path:chat_id>', methods=['POST'])
def api_chats_duplicate(chat_id):
    """Deep-copy a chat with a new ID, preserving all settings and log."""
    for f in CHATS_DIR.rglob(f"{chat_id}.json"):
        try:
            data    = json.loads(f.read_text(encoding='utf-8'))
            new_id  = datetime.datetime.now().strftime('%Y-%m-%dT%H-%M-%S') + '-copy'
            old_title = data.get('title', chat_id)
            data['id']    = new_id
            data['title'] = f"{old_title} (copy)"
            data['date']  = datetime.datetime.now().isoformat()
            # Save in the same folder as the original
            target_dir = f.parent
            new_path   = target_dir / f"{new_id}.json"
            new_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"[CHAT] Duplicated '{chat_id}' → '{new_id}'")
            return jsonify({'ok': True, 'new_id': new_id, 'title': data['title']})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Not found'}), 404

# ─── KNOWLEDGE BASE PERSISTENCE ──────────────────────────────────────────────

@app.route('/api/knowledge/list', methods=['GET'])
def api_knowledge_list():
    kbs = []
    for f in KNOWLEDGE_DIR.glob('*.json'):
        try:
            data   = json.loads(f.read_text(encoding='utf-8'))
            chunks = data.get('chunks', [])
            kb_type = data.get('type', 'keyword')
            # Flag KB only when ALL embeddings are empty (fully broken)
            broken = (kb_type == 'embedding' and len(chunks) > 0 and
                      all(not c.get('embedding') for c in chunks[:10]))
            kbs.append({
                'id':         f.stem,
                'name':       data.get('name', f.stem),
                'model':      data.get('model', ''),
                'folder':     data.get('folder', ''),
                'type':       kb_type,
                'chunks':     len(chunks),
                'files':      len(set(c.get('source','') for c in chunks)),
                'chunk_size': data.get('chunk_size', 500),
                'overlap':    data.get('overlap', 50),
                'created':    data.get('created', ''),
                'broken':     broken,
            })
        except Exception:
            pass
    kbs.sort(key=lambda x: x.get('created',''), reverse=True)
    return jsonify({'knowledge': kbs})

@app.route('/api/knowledge/save', methods=['POST'])
def api_knowledge_save():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'No name required'}), 400
    kb_type = data.get('type', 'keyword')
    chunks  = rag_embeddings if kb_type == 'embedding' else rag_chunks
    if not chunks:
        return jsonify({'error': 'No chunks loaded to save'}), 400
    # Validate embeddings — block only if ALL are empty, warn on partial
    if kb_type == 'embedding':
        empty = sum(1 for c in chunks if not c.get('embedding'))
        if empty == len(chunks):
            return jsonify({'error': f'All {len(chunks)} chunks have empty embeddings. Re-embed your files before saving.'}), 400
        if empty:
            print(f"[KB] Saving with {empty}/{len(chunks)} empty-embedding chunks — they will be skipped during retrieval")
    safe = re.sub(r'[^\w\-]', '_', name)
    kb = {
        'name':       name,
        'type':       kb_type,
        'model':      data.get('model', ''),
        'folder':     data.get('folder', ''),   # source folder — allows re-embedding
        'chunk_size': data.get('chunk_size', 500),
        'overlap':    data.get('overlap', 50),
        'created':    datetime.datetime.now().isoformat(),
        'chunks':     chunks,
    }
    path = KNOWLEDGE_DIR / f"{safe}.json"
    path.write_text(json.dumps(kb, ensure_ascii=False), encoding='utf-8')
    print(f"[KB] Saved: {path} ({len(chunks)} chunks)")
    return jsonify({'ok': True, 'id': safe})

@app.route('/api/knowledge/load/<kb_id>', methods=['POST'])
def api_knowledge_load(kb_id):
    global rag_chunks, rag_embeddings, rag_loaded
    path = KNOWLEDGE_DIR / f"{kb_id}.json"
    if not path.exists():
        return jsonify({'error': 'Not found'}), 404
    data    = json.loads(path.read_text(encoding='utf-8'))
    chunks  = data.get('chunks', [])
    kb_type = data.get('type', 'keyword')
    # Detect broken KB: embedding type but no actual vectors stored
    if kb_type == 'embedding':
        valid   = [c for c in chunks if c.get('embedding')]
        invalid = len(chunks) - len(valid)
        if not valid:
            # Fully broken — return repair info so UI can show the REPAIR button
            return jsonify({
                'error':      'broken_embeddings',
                'empty':      len(chunks),
                'total':      len(chunks),
                'name':       data.get('name', kb_id),
                'folder':     data.get('folder', ''),
                'model':      data.get('model', ''),
                'chunk_size': data.get('chunk_size', 500),
                'overlap':    data.get('overlap', 50),
            }), 400
        if invalid:
            print(f"[KB] Loaded '{kb_id}' — skipped {invalid} empty-embedding chunks, {len(valid)} valid")
        chunks = valid
        rag_embeddings = chunks
        rag_chunks     = []
    else:
        rag_chunks     = chunks
        rag_embeddings = []
    rag_loaded = True
    return jsonify({
        'ok':         True,
        'name':       data.get('name'),
        'model':      data.get('model', ''),
        'folder':     data.get('folder', ''),
        'type':       kb_type,
        'chunks':     len(chunks),
        'files':      len(set(c.get('source','') for c in chunks)),
        'chunk_size': data.get('chunk_size', 500),
        'overlap':    data.get('overlap', 50),
    })

@app.route('/api/knowledge/delete/<kb_id>', methods=['DELETE'])
def api_knowledge_delete(kb_id):
    path = KNOWLEDGE_DIR / f"{kb_id}.json"
    if path.exists():
        path.unlink()
        return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

# ─── CUSTOM MODEL PROFILES ───────────────────────────────────────────────────

def load_model_profiles():
    if MODELS_FILE.exists():
        try:
            return json.loads(MODELS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return []

def save_model_profiles(profiles):
    MODELS_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding='utf-8')

@app.route('/api/profiles', methods=['GET'])
def api_profiles_list():
    return jsonify({'profiles': load_model_profiles()})

@app.route('/api/profiles/save', methods=['POST'])
def api_profiles_save():
    profile = request.json or {}
    if not profile.get('id'):
        profile['id'] = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    profiles = load_model_profiles()
    idx = next((i for i, p in enumerate(profiles) if p['id'] == profile['id']), None)
    if idx is not None:
        profiles[idx] = profile
    else:
        profiles.append(profile)
    save_model_profiles(profiles)
    return jsonify({'ok': True, 'id': profile['id']})

@app.route('/api/profiles/delete/<profile_id>', methods=['DELETE'])
def api_profiles_delete(profile_id):
    profiles = [p for p in load_model_profiles() if p['id'] != profile_id]
    save_model_profiles(profiles)
    return jsonify({'ok': True})

# ─── MULTI-AI SYSTEMS ──────────────────────────────────────────────────────────

def load_systems():
    if SYSTEMS_FILE.exists():
        try:
            return json.loads(SYSTEMS_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return []

def save_systems(systems):
    SYSTEMS_FILE.write_text(json.dumps(systems, ensure_ascii=False, indent=2), encoding='utf-8')

@app.route('/api/systems', methods=['GET'])
def api_systems_list():
    return jsonify({'systems': load_systems()})

@app.route('/api/systems/save', methods=['POST'])
def api_systems_save():
    system = request.json or {}
    if not system.get('id'):
        system['id'] = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    system['updated'] = datetime.datetime.now().isoformat()
    systems = load_systems()
    idx = next((i for i, s in enumerate(systems) if s['id'] == system['id']), None)
    if idx is not None:
        systems[idx] = system
    else:
        systems.append(system)
    save_systems(systems)
    print(f"[SYSTEMS] Saved: {system.get('name','?')} ({system['id']})")
    return jsonify({'ok': True, 'id': system['id']})

@app.route('/api/systems/delete/<system_id>', methods=['DELETE'])
def api_systems_delete(system_id):
    systems = [s for s in load_systems() if s['id'] != system_id]
    save_systems(systems)
    return jsonify({'ok': True})

# ─── RAG — KEYWORD MODE ──────────────────────────────────────────────────────

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(' '.join(words[i:i+chunk_size]))
        i += max(chunk_size - overlap, 1)
    return chunks

def load_rag_files(folder_path, chunk_size=500, overlap=50):
    global rag_chunks, rag_loaded
    folder = Path(folder_path)
    if not folder.exists():
        return 0
    rag_chunks = []
    count = 0
    for txt_file in folder.glob("*.txt"):
        try:
            content = txt_file.read_text(encoding='utf-8', errors='ignore')
            for c in chunk_text(content, chunk_size=chunk_size, overlap=overlap):
                rag_chunks.append({"text": c, "source": txt_file.name})
            count += 1
        except Exception as e:
            print(f"[RAG] Error: {txt_file.name}: {e}")
    rag_loaded = True
    print(f"[RAG] {len(rag_chunks)} chunks from {count} files")
    return len(rag_chunks)

STOPS = {'the','a','an','is','are','was','were','i','you','we','they','it',
         'in','on','at','to','for','of','and','or','but','with','my','your',
         'our','this','that','have','has','had','be','been','do','did','will'}

def simple_score(query, text):
    qw = set(re.findall(r'\w+', query.lower())) - STOPS
    tw = set(re.findall(r'\w+', text.lower()))  - STOPS
    if not qw:
        return 0
    return len(qw & tw) / math.sqrt(len(qw) * max(len(tw), 1))

def retrieve_keyword(query, top_k=5):
    if not rag_chunks:
        return []
    scored = sorted([(simple_score(query, c['text']), c) for c in rag_chunks],
                    key=lambda x: x[0], reverse=True)
    return [c for score, c in scored[:top_k] if score > 0]

# ─── RAG — EMBEDDING MODE ────────────────────────────────────────────────────

def cosine_sim(a, b):
    dot = sum(x*y for x,y in zip(a,b))
    na  = math.sqrt(sum(x*x for x in a))
    nb  = math.sqrt(sum(x*x for x in b))
    return dot / (na * nb) if na and nb else 0.0

def get_embedding(text, model):
    """Try new Ollama /api/embed first, fall back to legacy /api/embeddings.
    Automatically halves the text when Ollama returns a context-length error."""
    current     = text
    trunc_count = 0

    while current:  # loop to retry with shorter text on context errors
        got_context_error = False

        # New API: POST /api/embed  { model, input }  → { embeddings: [[...]] }
        try:
            r = requests.post(f"{OLLAMA_URL}/api/embed",
                              json={"model": model, "input": current}, timeout=120)
            if r.ok:
                embs = r.json().get('embeddings', [])
                if embs and isinstance(embs[0], list) and embs[0]:
                    return embs[0]
            elif ('context' in r.text.lower() or 'length' in r.text.lower()):
                got_context_error = True
        except Exception:
            pass

        if not got_context_error:
            # Legacy API: POST /api/embeddings  { model, prompt }  → { embedding: [...] }
            try:
                r = requests.post(f"{OLLAMA_URL}/api/embeddings",
                                  json={"model": model, "prompt": current}, timeout=120)
                if r.ok:
                    emb = r.json().get('embedding', [])
                    if emb:
                        return emb
                elif ('context' in r.text.lower() or 'length' in r.text.lower()):
                    got_context_error = True
            except Exception:
                pass

        if got_context_error:
            trunc_count += 1
            new_len = len(current) // 2
            if new_len < 1:
                break
            print(f"[EMBED] Context too long ({len(current)} chars) — truncating to {new_len} (trunc #{trunc_count})")
            current = current[:new_len]
        else:
            break  # non-context failure, no point truncating

    print(f"[EMBED] WARNING: get_embedding returned empty for model '{model}' — check model name and Ollama version")
    return []

def embed_files_background(folder_path, chunk_size, overlap, embed_model):
    global rag_embeddings, rag_loaded, embed_progress
    folder = Path(folder_path)
    if not folder.exists():
        embed_progress.update({'error': 'Folder not found', 'running': False})
        return
    all_chunks = []
    for txt_file in folder.glob("*.txt"):
        try:
            content = txt_file.read_text(encoding='utf-8', errors='ignore')
            for c in chunk_text(content, chunk_size, overlap):
                all_chunks.append({"text": c, "source": txt_file.name})
        except Exception as e:
            print(f"[EMBED] Read error {txt_file.name}: {e}")
    embed_progress.update({'total': len(all_chunks), 'done': 0, 'model': embed_model, 'error': ''})
    rag_embeddings = []
    print(f"[EMBED] Embedding {len(all_chunks)} chunks with {embed_model}…")
    for i, chunk in enumerate(all_chunks):
        try:
            emb = get_embedding(chunk['text'], embed_model)
            rag_embeddings.append({**chunk, 'embedding': emb})
        except Exception as e:
            print(f"[EMBED] chunk {i} error: {e}")
        embed_progress['done'] = i + 1
    rag_loaded = True
    embed_progress['running'] = False
    print(f"[EMBED] Done — {len(rag_embeddings)} embeddings")

def retrieve_embedding(query, embed_model, top_k=5):
    valid_chunks = [c for c in rag_embeddings if c.get('embedding')]
    if not valid_chunks:
        print("[EMBED RETRIEVE] No valid embeddings in memory — did embedding finish?")
        return []
    q_emb = get_embedding(query, embed_model)
    if not q_emb:
        print(f"[EMBED RETRIEVE] Empty query embedding — model '{embed_model}' unreachable or wrong name")
        return []
    scored = sorted([(cosine_sim(q_emb, c['embedding']), c) for c in valid_chunks],
                    key=lambda x: x[0], reverse=True)
    top_scores = [round(s, 4) for s, _ in scored[:min(3, len(scored))]]
    print(f"[EMBED RETRIEVE] Top-{top_k} cosine scores: {top_scores}")
    results = [c for score, c in scored[:top_k] if score > 0.01]
    if not results and scored:
        print(f"[EMBED RETRIEVE] All scores ≤ 0.01 — embedding mismatch suspected")
    return results

# ─── RAG API ──────────────────────────────────────────────────────────────────

@app.route('/api/rag/load', methods=['POST'])
def api_load_rag():
    data       = request.json or {}
    folder     = data.get('folder', '')
    if not folder:
        return jsonify({"error": "No folder provided"}), 400
    chunk_size = max(50, min(int(data.get('chunk_size', 500)), 4000))
    overlap    = max(0, min(int(data.get('overlap', 50)), chunk_size - 1))
    count      = load_rag_files(folder, chunk_size=chunk_size, overlap=overlap)
    return jsonify({"chunks": count, "files": len(set(c['source'] for c in rag_chunks))})

@app.route('/api/rag/embed_load', methods=['POST'])
def api_embed_load():
    global embed_progress
    if embed_progress['running']:
        return jsonify({"error": "Already running"}), 400
    data        = request.json or {}
    folder      = data.get('folder', '')
    embed_model = data.get('embed_model', 'nomic-embed-text')
    chunk_size  = max(50, min(int(data.get('chunk_size', 500)), 4000))
    overlap     = max(0, min(int(data.get('overlap', 50)), chunk_size - 1))
    if not folder:
        return jsonify({"error": "No folder provided"}), 400
    embed_progress = {'total': 0, 'done': 0, 'running': True, 'error': '', 'model': embed_model}
    threading.Thread(target=embed_files_background,
                     args=(folder, chunk_size, overlap, embed_model), daemon=True).start()
    return jsonify({"ok": True})

@app.route('/api/rag/embed_status', methods=['GET'])
def api_embed_status():
    return jsonify({
        **embed_progress,
        'chunks': len(rag_embeddings),
        'files':  len(set(c['source'] for c in rag_embeddings))
    })

@app.route('/api/rag/embed_unload', methods=['POST'])
def api_embed_unload():
    """Unload the embedding model from Ollama VRAM via the correct embedding endpoint."""
    data  = request.json or {}
    model = data.get('model', '')
    if not model:
        return jsonify({'error': 'No model specified'}), 400
    unloaded = False
    # Try new /api/embed first
    try:
        r = requests.post(f"{OLLAMA_URL}/api/embed",
                          json={"model": model, "input": "", "keep_alive": 0}, timeout=15)
        if r.ok:
            unloaded = True
            print(f"[EMBED] Unloaded '{model}' via /api/embed")
    except Exception:
        pass
    # Also try legacy /api/embeddings
    if not unloaded:
        try:
            requests.post(f"{OLLAMA_URL}/api/embeddings",
                          json={"model": model, "prompt": "", "keep_alive": 0}, timeout=15)
            unloaded = True
            print(f"[EMBED] Unloaded '{model}' via /api/embeddings")
        except Exception as e:
            print(f"[EMBED] Unload error: {e}")
    return jsonify({'ok': True, 'model': model})


@app.route('/api/rag/status', methods=['GET'])
def api_rag_status():
    # Also report whether stored embeddings are valid (non-empty vectors)
    embed_valid = sum(1 for c in rag_embeddings if c.get('embedding'))
    return jsonify({
        "loaded":        rag_loaded,
        "chunks":        len(rag_chunks),
        "embed_chunks":  len(rag_embeddings),
        "embed_valid":   embed_valid,
        "files":         list(set(c['source'] for c in rag_chunks))
    })

@app.route('/api/rag/log', methods=['GET'])
def api_rag_log():
    return jsonify({"log": rag_log})

@app.route('/api/rag/log/clear', methods=['POST'])
def api_rag_log_clear():
    rag_log.clear()
    return jsonify({"ok": True})

# ─── OLLAMA PROXY ─────────────────────────────────────────────────────────────

@app.route('/api/tags', methods=['GET'])
def proxy_tags():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return Response(r.content, content_type='application/json')
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 503

def _stream_response(upstream_response):
    """Stream chunks from an upstream requests.Response, handling client disconnects cleanly.

    When the browser aborts (Stop button / AbortController), Flask stops reading
    from this generator.  Without a try/finally the upstream connection to Ollama
    stays open and keeps generating until the full response is done, blocking
    subsequent requests for 30-60 s.  Closing `upstream_response` here sends a
    RST to Ollama so it can stop immediately and free VRAM for the next request.
    """
    try:
        for chunk in upstream_response.iter_content(chunk_size=None):
            yield chunk
    except Exception:
        pass  # client disconnected mid-stream – that's fine
    finally:
        upstream_response.close()

@app.route('/api/generate', methods=['POST'])
def proxy_generate():
    data   = request.json or {}
    stream = data.get('stream', True)
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=data, stream=stream, timeout=120)
        if stream:
            return Response(_stream_response(r), content_type='application/x-ndjson')
        return Response(r.content, content_type='application/json')
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route('/api/chat', methods=['POST'])
def proxy_chat():
    data        = request.json or {}
    use_rag     = data.pop('use_rag', False)
    rag_top_k   = int(data.pop('rag_top_k', 5))
    rag_mode    = data.pop('rag_mode', 'keyword')
    embed_model = data.pop('embed_model', 'nomic-embed-text')
    rag_template = data.pop('rag_template', '### Memory Context:\n{context}')

    if use_rag:
        messages  = data.get('messages', [])
        last_user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
        if last_user:
            if rag_mode == 'embedding' and rag_embeddings:
                results = retrieve_embedding(last_user, embed_model, top_k=rag_top_k)
            elif rag_chunks:
                results = retrieve_keyword(last_user, top_k=rag_top_k)
            else:
                results = []
            if results:
                ctx_text = "\n\n".join(f"[{r['source']}] {r['text']}" for r in results)
                rag_ctx  = "\n\n" + rag_template.replace('{context}', ctx_text) + "\n\n"
                if messages and messages[0]['role'] == 'system':
                    messages[0]['content'] += rag_ctx
                else:
                    messages.insert(0, {'role': 'system', 'content': rag_ctx.strip()})
                rag_log.append({
                    'time':   datetime.datetime.now().strftime('%H:%M:%S'),
                    'query':  last_user[:100],
                    'mode':   rag_mode,
                    'chunks': [{'source': r['source'], 'preview': r['text'][:150]} for r in results]
                })
                if len(rag_log) > 100:
                    rag_log.pop(0)

    stream = data.get('stream', True)
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=data, stream=stream, timeout=120)
        if stream:
            return Response(_stream_response(r), content_type='application/x-ndjson')
        return Response(r.content, content_type='application/json')
    except Exception as e:
        return jsonify({"error": str(e)}), 503

# ─── STATIC ───────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def serve_index():
    return send_from_directory('echo_ui', 'index.html')

@app.route('/<path:path>', methods=['GET'])
def serve_static(path):
    return send_from_directory('echo_ui', path)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("═" * 58)
    print("  ECHO // MULTI-MIND  v0.85")
    print("═" * 58)
    print(f"  UI:        http://localhost:8080")
    print(f"  Ollama:    {OLLAMA_URL}")
    print(f"  Chats:     {CHATS_DIR}")
    print(f"  Knowledge: {KNOWLEDGE_DIR}")
    print(f"  Profiles:  {PROFILES_DIR}")
    print(f"  Systems:   {SYSTEMS_DIR}")
    print("═" * 58)
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
