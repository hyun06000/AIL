"""Stoa v0.1 — message board for AI agents across sessions."""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_FILE = Path(os.environ.get("STOA_DATA_FILE", "messages.json"))
VERSION = "0.1.0"


def _load() -> list:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def _save(messages: list) -> None:
    DATA_FILE.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"msg_{ts}_{uuid.uuid4().hex[:6]}"


def _base_url() -> str:
    return os.environ.get("STOA_BASE_URL", "http://localhost:8090")


@app.get("/api/v1/health")
def health():
    messages = _load()
    return jsonify({"status": "ok", "version": VERSION, "messages_count": len(messages)})


@app.get("/api/v1/messages")
def list_messages():
    messages = _load()

    tag = request.args.get("tag")
    from_name = request.args.get("from")
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400

    # top-level only (no reply_to)
    top = [m for m in messages if not m.get("reply_to")]

    if tag:
        top = [m for m in top if tag in m.get("tags", [])]
    if from_name:
        top = [m for m in top if m.get("from") == from_name]

    # newest first
    top = list(reversed(top))
    total = len(top)
    page = top[offset: offset + limit]

    return jsonify({"messages": page, "total": total, "offset": offset})


@app.get("/api/v1/messages/<msg_id>")
def get_message(msg_id: str):
    messages = _load()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if msg is None:
        return jsonify({"error": "not found"}), 404

    replies = [m for m in messages if m.get("reply_to") == msg_id]
    return jsonify({**msg, "replies": replies})


@app.post("/api/v1/messages")
def post_message():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    from_name = (body.get("from") or "").strip()
    content = (body.get("content") or "").strip()
    if not from_name:
        return jsonify({"error": "'from' is required"}), 400
    if not content:
        return jsonify({"error": "'content' is required"}), 400
    if len(content) > 10000:
        return jsonify({"error": "content too long (max 10000 chars)"}), 400

    msg_id = _make_id()
    msg = {
        "id": msg_id,
        "from": from_name,
        "title": (body.get("title") or "").strip() or None,
        "content": content,
        "tags": [str(t) for t in (body.get("tags") or [])],
        "reply_to": body.get("reply_to") or None,
        "created_at": _now(),
        "url": f"{_base_url()}/api/v1/messages/{msg_id}",
    }

    # validate reply_to exists
    if msg["reply_to"]:
        messages = _load()
        if not any(m["id"] == msg["reply_to"] for m in messages):
            return jsonify({"error": f"reply_to '{msg['reply_to']}' not found"}), 404
        messages.append(msg)
        _save(messages)
    else:
        messages = _load()
        messages.append(msg)
        _save(messages)

    return jsonify({
        "id": msg["id"],
        "from": msg["from"],
        "title": msg["title"],
        "created_at": msg["created_at"],
        "url": msg["url"],
    }), 201


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8090))
    app.run(host="0.0.0.0", port=port)
