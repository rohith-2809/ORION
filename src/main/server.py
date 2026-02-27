import sys
import os

# Append src/ to the path dynamically so server.py can resolve the other
# directories. Must be done BEFORE local imports.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import send_from_directory
import psutil
import glob
import logging
import threading
from core.orchestrator import OrionOrchestrator
from flask_socketio import SocketIO
from flask_cors import CORS
from flask import Flask, request, jsonify

# Prevent OpenMP Threading Collisions between PyTorch (NeMo) and Llama.cpp
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"


app = Flask(__name__)
app.config['SECRET_KEY'] = 'orion_secret'
CORS(app)

# Silence noisy /api/status polling from Werkzeug logs
log = logging.getLogger('werkzeug')


class StatusFilter(logging.Filter):
    def filter(self, record):
        return '/api/status' not in record.getMessage()


log.addFilter(StatusFilter())

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize Orion with SocketIO
print("Initializing Orion Orchestrator with Socket.IO...")
orion = OrionOrchestrator(socketio=socketio)

# Start Orion's background loops if necessary (e.g., defense kernel)
# Note: Orion's init starts the defense kernel in a separate
# thread/process usually.
orion.voice_active = True
voice_thread = threading.Thread(target=orion.always_on_voice_loop, daemon=True)
voice_thread.start()


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    god_mode = data.get('god_mode', False)
    chat_mode = data.get('chat_mode', False)

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if getattr(orion, 'is_busy', False):
        print("[API] Blocked incoming request - System is busy")
        return jsonify({
            "type": "CHAT",
            "content": "I am currently processing another task. Please wait."
        })

    print(
        f"User: {user_message} "
        f"(God Mode: {god_mode}, Chat Mode: {chat_mode})"
    )

    # [BUG FIX] If both God Mode and Chat Mode are enabled, turn off Voice
    if god_mode and chat_mode:
        if getattr(orion, 'voice_active', False):
            print("[API] God Mode and Chat Mode enabled -> Voice disabled")
            orion.voice_active = False

    # If in Chat Mode, bypass task constraints and get a rich conversational
    # response directly
    if chat_mode:
        orion.is_busy = False  # Force reset just in case
        print("[API] Routing directly to Brain (Chat Mode) with History...")

        # [FEATURE] Allow silent Memory Storage even in Chat Mode
        decision = orion.intent.classify(user_message)
        if decision.get("intent") == "MEMORY_STORE":
            print(
                f"[API] 🧠 Saving Memory in Chat Mode: "
                f"{decision['key']} -> {decision['value']}"
            )
            orion.memory.add(decision["key"], decision["value"])

        # [FEATURE] Prioritize Document Generation over Chat Mode
        if decision.get("intent") in ["DOCUMENT_CREATE", "DOCUMENT_JOB_RESUME"]:
            print(f"[API] 📝 Document intent ({decision.get('intent')}) requested in Chat Mode. Routing to Orchestrator...")
            # Route to normal execution path
            response = orion.route(user_message, god_mode=god_mode)
            print(f"Orion: {response}")
            return jsonify(response)

        # Build conversational history from episodic memory safely
        recent_episodes = orion.memory.get_recent_episodes(limit=3)
        context_str = ""
        for ep in reversed(recent_episodes):
            context_str += f"- User: {ep['user']}\n  Orion: {ep['agent']}\n"

        if context_str:
            prompt = (
                "[PAST CONVERSATION CONTEXT]\n"
                f"{context_str}\n"
                "[CURRENT USER MESSAGE]\n"
                f"{user_message}"
            )
        else:
            prompt = user_message

        # Ensure deep reasoning and no task execution
        response_text = orion.brain.think(prompt)

        # Save to memory so the next chat hit has history context
        orion.memory.add_episode(user_message, response_text)

        response = {
            "type": "CHAT",
            "content": response_text
        }
    elif god_mode:
        # Bypass normal restrictions and execute directly if it's an action
        # Or provide God Mode specific reasoning
        response = orion.route(user_message, god_mode=True)
    else:
        # Process with Orion normally
        response = orion.route(user_message)

    print(f"Orion: {response}")

    return jsonify(response)


@app.route('/api/voice_status', methods=['POST'])
def voice_status():
    data = request.json
    active = data.get('active', True)

    orion.voice_active = active
    print(f"[API] Orion Voice Active set to: {orion.voice_active}")

    return jsonify({"status": "success", "voice_active": orion.voice_active})


@app.route('/api/status', methods=['GET'])
def status():
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent

    # Simple threat check from Orion's kernel memory if available
    threats = 0
    try:
        if hasattr(orion, 'kernel') and hasattr(orion.kernel, 'memory'):
            if orion.kernel.memory.incident_state.value != "normal":
                threats = 1
    except BaseException:
        pass

    return jsonify({
        "status": "online",
        "system": "Orion",
        "cpu": cpu,
        "memory": mem,
        "threats": threats
    })


@app.route('/api/scan', methods=['POST'])
def scan():
    print("[API] Triggering Deep Scan via Agent...")

    # Relay to Orchestrator -> Agent
    # We use a special route intent or direct method if available.
    # For now, let's treat it as a routed command "scan system" which Orion
    # should understand,
    # OR better, expose a direct method in Orchestrator for API control.

    if hasattr(orion, 'trigger_agent_scan'):
        response = orion.trigger_agent_scan()
        return jsonify(response)

    # Fallback to local simulation if Agent not ready
    return jsonify({
        "scan_complete": False,
        "error": "Orchestrator Bridge Not Ready"
    })


@app.route('/api/clean', methods=['POST'])
def clean():
    print("[API] Triggering System Clean via Agent...")

    if hasattr(orion, 'trigger_agent_clean'):
        response = orion.trigger_agent_clean()
        return jsonify(response)

    return jsonify({
        "status": "error",
        "message": "Orchestrator Bridge Not Ready"
    })


@app.route('/api/integrity', methods=['POST'])
def integrity():
    print("[API] Triggering System Integrity Check...")

    if hasattr(orion, 'trigger_agent_integrity'):
        response = orion.trigger_agent_integrity()
        return jsonify(response)

    return jsonify({
        "status": "error",
        "message": "Orchestrator Bridge Not Ready"
    })


@app.route('/api/outputs', methods=['GET'])
def list_outputs():
    """Lists all generated documents available for download."""
    output_dir = "/mnt/c/Users/rohith/Desktop/ORION_OUTPUTS"

    # Create directory if it doesn't exist to prevent errors
    os.makedirs(output_dir, exist_ok=True)

    files = []
    # Find all PPTX and MD files
    for filepath in glob.glob(os.path.join(output_dir, '*.*')):
        if filepath.endswith('.pptx') or filepath.endswith('.md'):
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            is_pptx = filename.endswith('.pptx')
            files.append({
                "filename": filename,
                "size_bytes": size,
                "type": "presentation" if is_pptx else "document"
            })

    return jsonify({"outputs": files})


@app.route('/api/download/<filename>', methods=['GET'])
def download_output(filename):
    """Serves the requested file to the frontend for download."""
    output_dir = "/mnt/c/Users/rohith/Desktop/ORION_OUTPUTS"

    # Basic directory traversal protection
    if ".." in filename or "/" in filename:
        return jsonify({"error": "Invalid filename"}), 400

    try:
        return send_from_directory(output_dir, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


if __name__ == '__main__':
    # Run using SocketIO
    print("Starting Orion Brain & API (Socket.IO Enabled) on port 3000...")

    # Speak boot message when server is ready
    def boot_speech():
        import time
        time.sleep(2)
        print("🟢 [ORION CORE] System Ready.")
        if hasattr(orion, 'tts'):
            orion.tts.speak("Orion is at your service, sir.")

    threading.Thread(target=boot_speech, daemon=True).start()

    socketio.run(
        app,
        host='0.0.0.0',
        port=3000,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True)
