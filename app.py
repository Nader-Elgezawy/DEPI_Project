"""
Forensics Dashboard — main Flask application.

Run with:
    python app.py
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

import config
from utils.loader import discover_tools
from utils.reporter import save_report
from utils.validator import validate_upload

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger("dashboard")

# ---------------------------------------------------------------------------
# Flask + SocketIO setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")

# ---------------------------------------------------------------------------
# Ensure directories exist
# ---------------------------------------------------------------------------
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.REPORT_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# Discover tools
# ---------------------------------------------------------------------------
TOOLS: dict = discover_tools(config.TOOLS_FOLDER)

# In‑memory store for analysis sessions
# session_id → {"tool_id", "filename", "filepath", "logs": [], "status", "report_path"}
SESSIONS: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Dashboard home – shows all available tools."""
    tool_infos = []
    for tid, tcls in TOOLS.items():
        prereqs = tcls.check_prerequisites()
        tool_infos.append({
            "tool_id": tid,
            "name": tcls.name,
            "description": tcls.description,
            "accepted_extensions": tcls.accepted_extensions,
            "prerequisites": prereqs,
            "all_ok": all(p["installed"] for p in prereqs),
        })
    return render_template("index.html", tools=tool_infos)


@app.route("/tool/<tool_id>")
def tool_page(tool_id: str):
    """Dedicated page for a single tool."""
    if tool_id not in TOOLS:
        flash(f"Unknown tool: {tool_id}", "danger")
        return redirect(url_for("index"))
    tcls = TOOLS[tool_id]
    prereqs = tcls.check_prerequisites()
    return render_template(
        "tool.html",
        tool_id=tool_id,
        tool_name=tcls.name,
        tool_description=tcls.description,
        accepted_extensions=tcls.accepted_extensions,
        prerequisites=prereqs,
        all_ok=all(p["installed"] for p in prereqs),
    )


@app.route("/upload/<tool_id>", methods=["POST"])
def upload(tool_id: str):
    """Handle file upload and return a session id."""
    if tool_id not in TOOLS:
        return jsonify({"error": f"Unknown tool: {tool_id}"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    session_id = uuid.uuid4().hex[:12]
    dest_dir = os.path.join(config.UPLOAD_FOLDER, session_id)
    os.makedirs(dest_dir, exist_ok=True)
    filepath = os.path.join(dest_dir, filename)
    file.save(filepath)

    # Validate
    tcls = TOOLS[tool_id]
    ok, msg = validate_upload(filepath, tcls.accepted_extensions)
    if not ok:
        return jsonify({"error": msg}), 400

    SESSIONS[session_id] = {
        "tool_id": tool_id,
        "filename": filename,
        "filepath": filepath,
        "logs": [f"File uploaded: {filename}", f"Validation: {msg}"],
        "status": "ready",
        "report_path": None,
    }

    logger.info("Upload OK — session=%s tool=%s file=%s", session_id, tool_id, filename)
    return jsonify({"session_id": session_id, "message": msg})


@app.route("/local/<tool_id>", methods=["POST"])
def use_local_file(tool_id: str):
    """Use a local file path instead of uploading (for large files)."""
    if tool_id not in TOOLS:
        return jsonify({"error": f"Unknown tool: {tool_id}"}), 404

    data = request.get_json(silent=True) or {}
    filepath = data.get("filepath", "").strip()
    if not filepath:
        return jsonify({"error": "No file path provided."}), 400

    if not os.path.isabs(filepath):
        return jsonify({"error": "Please provide an absolute file path."}), 400

    if not os.path.isfile(filepath):
        return jsonify({"error": f"File not found: {filepath}"}), 404

    filename = os.path.basename(filepath)
    tcls = TOOLS[tool_id]
    ok, msg = validate_upload(filepath, tcls.accepted_extensions)
    if not ok:
        return jsonify({"error": msg}), 400

    session_id = uuid.uuid4().hex[:12]
    SESSIONS[session_id] = {
        "tool_id": tool_id,
        "filename": filename,
        "filepath": filepath,
        "logs": [f"Local file: {filepath}", f"Validation: {msg}"],
        "status": "ready",
        "report_path": None,
    }

    logger.info("Local file OK — session=%s tool=%s file=%s", session_id, tool_id, filepath)
    return jsonify({"session_id": session_id, "message": msg})


@app.route("/session/<session_id>")
def session_page(session_id: str):
    """View an analysis session with live logs."""
    sess = SESSIONS.get(session_id)
    if not sess:
        flash("Session not found.", "danger")
        return redirect(url_for("index"))
    tcls = TOOLS.get(sess["tool_id"])
    tool_name = tcls.name if tcls else sess["tool_id"]
    return render_template(
        "session.html",
        session_id=session_id,
        sess=sess,
        tool_name=tool_name,
    )


@app.route("/report/<session_id>")
def download_report(session_id: str):
    """Download the saved report for a session."""
    sess = SESSIONS.get(session_id)
    if not sess or not sess.get("report_path"):
        flash("No report available.", "warning")
        return redirect(url_for("index"))
    return send_file(sess["report_path"], as_attachment=True)


@app.route("/api/tools")
def api_tools():
    """JSON list of available tools and their prerequisite status."""
    data = []
    for tid, tcls in TOOLS.items():
        prereqs = tcls.check_prerequisites()
        data.append({
            "tool_id": tid,
            "name": tcls.name,
            "description": tcls.description,
            "accepted_extensions": tcls.accepted_extensions,
            "prerequisites": prereqs,
            "all_ok": all(p["installed"] for p in prereqs),
        })
    return jsonify(data)


@app.route("/api/sessions")
def api_sessions():
    """JSON list of recent sessions."""
    return jsonify({
        sid: {
            "tool_id": s["tool_id"],
            "filename": s["filename"],
            "status": s["status"],
        }
        for sid, s in SESSIONS.items()
    })


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------


@socketio.on("run_analysis")
def handle_run_analysis(data):
    """Client sends ``{session_id}`` to kick off tool execution."""
    session_id = data.get("session_id", "")
    sess = SESSIONS.get(session_id)
    if not sess:
        emit("log", {"line": "ERROR: session not found.", "done": True})
        return

    if sess["status"] == "running":
        emit("log", {"line": "Analysis is already running.", "done": False})
        return

    tool_id = sess["tool_id"]
    tcls = TOOLS.get(tool_id)
    if not tcls:
        emit("log", {"line": f"ERROR: tool '{tool_id}' not found.", "done": True})
        return

    sess["status"] = "running"
    sess["logs"].append(f"--- Analysis started at {datetime.now(timezone.utc).isoformat()} ---")
    emit("log", {"line": f"Starting {tcls.name} analysis ...", "done": False})

    def stream(line: str):
        sess["logs"].append(line)
        socketio.emit("log", {"line": line, "done": False}, to=request.sid)

    try:
        tool_instance = tcls()
        tool_instance.run(sess["filepath"], emit=stream)
        sess["status"] = "complete"

        # Auto‑save report
        report_path = save_report(
            config.REPORT_FOLDER,
            tool_id,
            sess["filename"],
            sess["logs"],
        )
        sess["report_path"] = report_path
        stream(f"Report saved: {os.path.basename(report_path)}")
    except Exception as exc:
        sess["status"] = "error"
        stream(f"FATAL ERROR: {exc}")
        logger.exception("Analysis failed for session %s", session_id)

    emit("log", {"line": "--- Analysis finished ---", "done": True})


@socketio.on("save_report")
def handle_save_report(data):
    """Manually trigger report saving."""
    session_id = data.get("session_id", "")
    sess = SESSIONS.get(session_id)
    if not sess:
        emit("report_saved", {"error": "Session not found."})
        return
    report_path = save_report(
        config.REPORT_FOLDER,
        sess["tool_id"],
        sess["filename"],
        sess["logs"],
    )
    sess["report_path"] = report_path
    emit("report_saved", {"path": report_path, "name": os.path.basename(report_path)})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Discovered %d tool(s): %s", len(TOOLS), ", ".join(TOOLS.keys()))
    socketio.run(app, host="0.0.0.0", port=5000, debug=config.DEBUG)
