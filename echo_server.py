"""
Echo Dual Chat Server
- Serves the UI on http://localhost:8080
- Proxies Ollama API (solves CORS, no Ollama changes needed)
- RAG: load your txt memory files for context injection
- No Docker changes required

Install deps: pip install flask requests flask-cors
Run: python echo_server.py
"""

import os
import re
import json
import math
import datetime
import requests
import threading
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='echo_ui')
CORS(app)

OLLAMA_URL = "http://localhost:11434"

# ─── CHAT STORAGE ─────────────────────────────────────────────────────────────

CHATS_DIR = Path(__file__).parent / 'echo_chats'
CHATS_DIR.mkdir(exist_ok=True)

def chats_meta():
    """Return sorted list of chat metadata dicts and folder names."""
    chats = []
    folders = set()
    for f in CHATS_DIR.rglob('*.json'):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            folder = f.parent.name if f.parent != CHATS_DIR else ''
            if folder:
                folders.add(folder)
            chats.append({
                'id':     data.get('id', f.stem),
                'title':  data.get('title', f.stem),
                'date':   data.get('date', ''),
                'modelA': data.get('modelA', ''),
                'modelB': data.get('modelB', ''),
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
    data = request.json or {}
    chat_id = data.get('id', '')
    folder  = data.get('folder', '').strip()
    if not chat_id:
        return jsonify({'error': 'No id'}), 400
    target_dir = CHATS_DIR / folder if folder else CHATS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{chat_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[CHAT] Saved: {path}")
    return jsonify({'ok': True, 'path': str(path)})

@app.route('/api/chats/load/<path:chat_id>', methods=['GET'])
def api_chats_load(chat_id):
    # Search in all subdirs
    for f in CHATS_DIR.rglob(f"{chat_id}.json"):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            return jsonify(data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/chats/delete/<path:chat_id>', methods=['DELETE'])
def api_chats_delete(chat_id):
    for f in CHATS_DIR.rglob(f"{chat_id}.json"):
        f.unlink()
        print(f"[CHAT] Deleted: {f}")
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
    data = request.json or {}
    chat_id = data.get('id', '')
    folder  = data.get('folder', '').strip()
    for f in CHATS_DIR.rglob(f"{chat_id}.json"):
        target_dir = CHATS_DIR / folder if folder else CHATS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        new_path = target_dir / f.name
        f.rename(new_path)
        print(f"[CHAT] Moved: {f} → {new_path}")
        return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

# ─── RAG SYSTEM ──────────────────────────────────────────────────────────────

rag_chunks = []       # list of {text, source}
rag_loaded = False
rag_log    = []       # list of {time, query, chunks:[{source, preview}]}

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = ' '.join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def load_rag_files(folder_path, chunk_size=500, overlap=50):
    global rag_chunks, rag_loaded
    folder = Path(folder_path)
    if not folder.exists():
        print(f"[RAG] Folder not found: {folder_path}")
        return 0

    rag_chunks = []
    count = 0
    for txt_file in folder.glob("*.txt"):
        try:
            content = txt_file.read_text(encoding='utf-8', errors='ignore')
            chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
            for c in chunks:
                rag_chunks.append({"text": c, "source": txt_file.name})
            count += 1
            print(f"[RAG] Loaded {txt_file.name} → {len(chunks)} chunks (size:{chunk_size} overlap:{overlap})")
        except Exception as e:
            print(f"[RAG] Error loading {txt_file.name}: {e}")

    rag_loaded = True
    print(f"[RAG] Total: {len(rag_chunks)} chunks from {count} files")
    return len(rag_chunks)

def simple_score(query, text):
    """Simple keyword overlap scoring - no external deps needed"""
    query_words = set(re.findall(r'\w+', query.lower()))
    text_words = set(re.findall(r'\w+', text.lower()))
    # Remove stop words
    stops = {'the','a','an','is','are','was','were','i','you','we','they',
             'it','in','on','at','to','for','of','and','or','but','with',
             'my','your','our','this','that','have','has','had','be','been'}
    query_words -= stops
    text_words -= stops
    if not query_words:
        return 0
    overlap = query_words & text_words
    return len(overlap) / math.sqrt(len(query_words) * max(len(text_words), 1))

def retrieve_context(query, top_k=6):
    if not rag_chunks:
        return []
    scored = [(simple_score(query, c["text"]), c) for c in rag_chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [c for score, c in scored[:top_k] if score > 0]
    return results

# ─── API ROUTES ───────────────────────────────────────────────────────────────

@app.route('/api/rag/load', methods=['POST'])
def api_load_rag():
    data = request.json or {}
    folder = data.get('folder', '')
    if not folder:
        return jsonify({"error": "No folder provided"}), 400
    chunk_size = max(50, min(int(data.get('chunk_size', 500)), 4000))
    overlap    = max(0,  min(int(data.get('overlap', 50)), chunk_size - 1))
    count = load_rag_files(folder, chunk_size=chunk_size, overlap=overlap)
    return jsonify({"chunks": count, "files": len(set(c['source'] for c in rag_chunks))})

@app.route('/api/rag/status', methods=['GET'])
def api_rag_status():
    return jsonify({
        "loaded": rag_loaded,
        "chunks": len(rag_chunks),
        "files": list(set(c['source'] for c in rag_chunks))
    })

@app.route('/api/rag/retrieve', methods=['POST'])
def api_rag_retrieve():
    data = request.json or {}
    query = data.get('query', '')
    top_k = data.get('top_k', 6)
    results = retrieve_context(query, top_k)
    return jsonify({"results": results})

@app.route('/api/rag/log', methods=['GET'])
def api_rag_log():
    """Return the retrieval log."""
    return jsonify({"log": rag_log})

@app.route('/api/rag/log/clear', methods=['POST'])
def api_rag_log_clear():
    """Clear the in-memory retrieval log."""
    rag_log.clear()
    return jsonify({"ok": True})

@app.route('/api/tags', methods=['GET'])
def proxy_tags():
    """Proxy Ollama model list"""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return Response(r.content, content_type='application/json')
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 503

@app.route('/api/generate', methods=['POST'])
def proxy_generate():
    """Proxy Ollama generate (used for model warm-up)"""
    data = request.json or {}
    stream = data.get('stream', True)
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=data,
            stream=stream,
            timeout=120
        )
        if stream:
            def generate():
                for chunk in r.iter_content(chunk_size=None):
                    yield chunk
            return Response(generate(), content_type='application/x-ndjson')
        else:
            return Response(r.content, content_type='application/json')
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route('/api/chat', methods=['POST'])
def proxy_chat():
    """Proxy Ollama chat with optional RAG injection"""
    data = request.json or {}
    
    # RAG injection: if rag is loaded, retrieve context for the last user message
    use_rag   = data.pop('use_rag', False)
    rag_top_k = int(data.pop('rag_top_k', 5))
    rag_context = ''

    if use_rag and rag_chunks:
        messages = data.get('messages', [])
        # Get last user message for retrieval
        last_user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
        if last_user:
            results = retrieve_context(last_user, top_k=rag_top_k)
            if results:
                rag_context = "\n\n### Personal Memory Context:\n"
                for r in results:
                    rag_context += f"[{r['source']}] {r['text']}\n\n"
                # Inject into system prompt or prepend to first message
                if messages and messages[0]['role'] == 'system':
                    messages[0]['content'] += rag_context
                else:
                    messages.insert(0, {'role': 'system', 'content': rag_context.strip()})
                # ── Log the retrieval ─────────────────────────────────────────
                rag_log.append({
                    'time':   datetime.datetime.now().strftime('%H:%M:%S'),
                    'query':  last_user[:100],
                    'chunks': [{'source': r['source'], 'preview': r['text'][:150]} for r in results]
                })
                if len(rag_log) > 100:   # cap at 100 — negligible memory
                    rag_log.pop(0)

    stream = data.get('stream', True)

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=data,
            stream=stream,
            timeout=120
        )

        if stream:
            def generate():
                for chunk in r.iter_content(chunk_size=None):
                    yield chunk
            return Response(generate(), content_type='application/x-ndjson')
        else:
            return Response(r.content, content_type='application/json')

    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route('/', methods=['GET'])
def serve_index():
    return send_from_directory('echo_ui', 'index.html')

@app.route('/<path:path>', methods=['GET'])
def serve_static(path):
    return send_from_directory('echo_ui', path)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 55)
    print("  ECHO DUAL CHAT SERVER")
    print("=" * 55)
    print(f"  UI:     http://localhost:8080")
    print(f"  Ollama: {OLLAMA_URL}")
    print("=" * 55)
    print("  Load RAG files via the UI or:")
    print("  POST /api/rag/load {'folder': 'C:/path/to/your/txtfiles'}")
    print("=" * 55)
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
