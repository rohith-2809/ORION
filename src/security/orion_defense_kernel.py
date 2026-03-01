
"""
ORION DEFENSE KERNEL
===================
Cognitive, policy-governed host defense layer.
State-of-the-art, explainable, non-autonomous EDR kernel.
"""

import psutil
import time
import statistics
import hashlib
import ast
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
import uuid
from enum import Enum
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from security.orion_mitigation_engine import MitigationExecutionEngine
from security.orion_mitigation_engine import MitigationPlanner


# ─────────────────────────────────────────────
# TRUST CONTEXT (ORION INTERNAL ACTIONS)
# ─────────────────────────────────────────────

class TrustContext:
    """
    Tracks trusted ORION-originated actions to prevent false positives.
    """

    def __init__(self):
        self.trusted_paths = set()
        self.trusted_until = {}

    def trust_path(self, path, ttl=5):
        expire_at = time.time() + ttl
        self.trusted_paths.add(path)
        self.trusted_until[path] = expire_at

    def is_trusted(self, path):
        now = time.time()
        expire_at = self.trusted_until.get(path)

        if expire_at and now <= expire_at:
            return True

        # cleanup expired
        if path in self.trusted_until:
            del self.trusted_until[path]
            self.trusted_paths.discard(path)

        return False

# ─────────────────────────────────────────────
# APPLICATION SANDBOXING (PORTABLE)
# ─────────────────────────────────────────────


class ApplicationSandbox:
    def observe(self, path, timeout=5):
        before_files = set(os.listdir("/tmp"))
        before_conns = len(psutil.net_connections())

        try:
            proc = subprocess.Popen(
                [path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(timeout)
            proc.terminate()
        except Exception:
            return None

        after_files = set(os.listdir("/tmp"))
        after_conns = len(psutil.net_connections())

        file_delta = len(after_files - before_files)
        conn_delta = after_conns - before_conns

        score = 0
        reasons = []

        if file_delta > 3:
            score += 0.4
            reasons.append("Created multiple files")

        if conn_delta > 0:
            score += 0.5
            reasons.append("Opened network connections")

        if score >= 0.6:
            return (
                f"Sandboxed application suspicious: {', '.join(reasons)}",
                min(score, 1.0)
            )

        return None

# ─────────────────────────────────────────────
# NETWORK TRAFFIC ANALYSIS (PORTABLE)
# ─────────────────────────────────────────────


class NetworkTrafficEngine:
    def __init__(self):
        # pid → deque[(timestamp, remote_ip)]
        self.pid_history = defaultdict(lambda: deque(maxlen=50))

    def analyze(self, memory):
        findings = []
        now = time.time()

        for c in psutil.net_connections(kind="inet"):
            if not c.pid or not c.raddr:
                continue

            pid = c.pid
            ip = c.raddr.ip
            self.pid_history[pid].append((now, ip))

        for pid, history in self.pid_history.items():
            if len(history) < 5:
                continue

            # same destination repeated
            ips = [ip for _, ip in history]
            most_common = max(set(ips), key=ips.count)

            if ips.count(most_common) >= 5:
                findings.append(
                    (f"Repeated outbound connection to {most_common} by PID {pid}", 0.85))

            # beaconing: regular intervals
            times = [t for t, _ in history]
            intervals = [times[i + 1] - times[i]
                         for i in range(len(times) - 1)]

            if intervals and max(intervals) - min(intervals) < 2:
                findings.append((
                    f"Possible beaconing behavior detected (PID {pid})",
                    0.9
                ))

        return findings

# ─────────────────────────────────────────────
# INCIDENT STATES
# ─────────────────────────────────────────────


class IncidentState(Enum):
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    CONFIRMED = "confirmed"
    CONTAINED = "contained"

# ─────────────────────────────────────────────
# CORE EVENT MODEL
# ─────────────────────────────────────────────


class SecurityEvent:
    def __init__(self, source, category, payload, severity=0):
        self.id = str(uuid.uuid4())
        self.time = datetime.now(timezone.utc).isoformat()
        self.source = source
        self.category = category
        self.payload = payload
        self.severity = severity


# ─────────────────────────────────────────────
# DETERMINISTIC MEMORY
# ─────────────────────────────────────────────

class DeterministicMemory:
    def __init__(self):
        self.events = deque(maxlen=5000)
        self.baselines = defaultdict(list)
        self.file_hashes = {}
        self.exe_hashes = {}          # exe_path → hash
        self.pid_users = {}           # pid → user
        self.alert_cache = set()
        self.integrity_alerted = set()
        self.incident_state = IncidentState.NORMAL
        self.incident_reason = None
        self.incident_started_at = None
        self.incident_active = False

    def store_event(self, event):
        self.events.append(event)

    def update_baseline(self, key, value):
        self.baselines[key].append(value)

    def baseline_ready(self, key, min_samples=10):
        return len(self.baselines[key]) >= min_samples

    def baseline_stats(self, key):
        data = self.baselines[key]
        if len(data) < 10:
            return None
        return statistics.mean(data), statistics.stdev(data) or 1


# ─────────────────────────────────────────────
# HASHING
# ─────────────────────────────────────────────

def hash_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


# ─────────────────────────────────────────────
# SYSTEM + PROCESS SENSORS
# ─────────────────────────────────────────────

class Sensors:
    def collect(self):
        events = []

        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent

        events.append(SecurityEvent(
            source="system",
            category="resource",
            payload={"cpu": cpu, "memory": mem}
        ))

        for p in psutil.process_iter(
                ["pid", "ppid", "name", "username", "exe"]):
            try:
                events.append(SecurityEvent(
                    source="process",
                    category="process",
                    payload=p.info
                ))
            except psutil.NoSuchProcess:
                pass

        return events


# ─────────────────────────────────────────────
# FILE SYSTEM SENSOR
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# FILE SYSTEM SENSOR (TRUST-AWARE, FALSE-POSITIVE SAFE)
# ─────────────────────────────────────────────

class OrionFileEventHandler(FileSystemEventHandler):

    def __init__(self, kernel):
        self.kernel = kernel
        self.activity_window = deque(maxlen=200)

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

    def _handle(self, event):
        if event.is_directory:
            return

        path = event.src_path

        # ───────── TRUSTED ORION WRITE (HARD BYPASS) ─────────
        if self.kernel.trust.is_trusted(path):
            return

        # ───────── AVOID OWN TTS FILES ─────────
        if path.endswith(".wav") and ("/tmp/" in path or "/var/tmp/" in path):
            return

        # ───────── STORE FILE EVENT ─────────
        self.kernel.memory.store_event(
            SecurityEvent(
                source="file_sensor",
                category="file",
                payload={"path": path}
            )
        )

        # ───────── RANSOMWARE BURST HEURISTIC ─────────
        now = time.time()
        self.activity_window.append(now)

        # keep only last 5 seconds
        while self.activity_window and now - self.activity_window[0] > 5:
            self.activity_window.popleft()

        if len(self.activity_window) > 30:
            self.kernel.raise_finding(
                "Possible ransomware behavior: mass file operations",
                0.9
            )

        # ───────── FILE INTEGRITY CHECK (TRUST-AWARE) ─────────
        new_hash = hash_file(path)
        old_hash = self.kernel.memory.file_hashes.get(path)

        if (
            old_hash
            and new_hash
            and old_hash != new_hash
            and not self.kernel.trust.is_trusted(path)
        ):
            if path not in self.kernel.memory.integrity_alerted:
                self.kernel.memory.integrity_alerted.add(path)
                self.kernel.raise_finding(
                    f"File integrity violation: {path}",
                    0.7
                )

        # ───────── UPDATE HASH BASELINE ─────────
        if new_hash:
            self.kernel.memory.file_hashes[path] = new_hash

# ─────────────────────────────────────────────
# BEHAVIORAL ANOMALY ENGINE
# ─────────────────────────────────────────────


class BehavioralAnomalyEngine:
    def analyze(self, event, memory):
        if event.category != "resource":
            return None

        cpu = event.payload["cpu"]
        mem = event.payload["memory"]

        memory.update_baseline("cpu", cpu)
        memory.update_baseline("mem", mem)

        if not (memory.baseline_ready("cpu") and memory.baseline_ready("mem")):
            return None

        cpu_mean, cpu_std = memory.baseline_stats("cpu")
        mem_mean, mem_std = memory.baseline_stats("mem")

        score = max(
            abs(cpu - cpu_mean) / cpu_std,
            abs(mem - mem_mean) / mem_std
        )

        if score > 4:
            return ("Behavioral anomaly detected", min(score / 10, 1.0))


# ─────────────────────────────────────────────
# PROCESS INTEGRITY ENGINE (FULL)
# ─────────────────────────────────────────────

class ProcessIntegrityEngine:
    def analyze(self, event, memory):
        if event.category != "process":
            return None

        p = event.payload
        pid = p.get("pid")
        user = p.get("username")
        exe = p.get("exe")

        # privilege escalation
        prev_user = memory.pid_users.get(pid)
        if prev_user and prev_user != user:
            return (f"Privilege escalation detected in PID {pid}", 0.9)

        memory.pid_users[pid] = user

        # executable integrity
        if exe:
            exe_hash = hash_file(exe)
            old_hash = memory.exe_hashes.get(exe)

            if old_hash and exe_hash and old_hash != exe_hash:
                return (f"Executable modified while running: {exe}", 0.85)

            if exe_hash:
                memory.exe_hashes[exe] = exe_hash

            # suspicious execution path
            if exe.startswith(("/tmp", "/var/tmp", "/dev/shm")):
                return (f"Executable running from writable path: {exe}", 0.8)


# ─────────────────────────────────────────────
# STATIC CODE INSPECTION (FULL)
# ─────────────────────────────────────────────

class StaticCodeInspector(ast.NodeVisitor):
    def __init__(self):
        self.issues = []

    def visit_Call(self, node):
        if getattr(node.func, "id", "") in ("exec", "eval", "compile"):
            self.issues.append("Dangerous dynamic execution")
        self.generic_visit(node)


def inspect_code(source):
    tree = ast.parse(source)
    inspector = StaticCodeInspector()
    inspector.visit(tree)
    return inspector.issues


# ─────────────────────────────────────────────
# THREAT CORRELATION ENGINE (FULL)
# ─────────────────────────────────────────────

class ThreatCorrelationEngine:
    def correlate(self, memory):
        recent = list(memory.events)[-100:]

        behavior = any(
            e.category == "resource" and e.payload.get("cpu", 0) > 90
            for e in recent
        )
        files = sum(1 for e in recent if e.category == "file") > 20
        procs = any(
            e.category == "process"
            and isinstance(e.payload.get("exe"), str)
            and e.payload.get("exe").startswith("/tmp")
            for e in recent
        )

        if behavior and files and procs:
            return [
                ("Multi-stage intrusion likely (behavior + file + process)", 0.95)]
        return []
# ─────────────────────────────────────────────
# UNAUTHORIZED ACCESS DETECTION
# ─────────────────────────────────────────────


class UnauthorizedAccessEngine:
    def __init__(self):
        self.user_failures = defaultdict(deque)

    def analyze(self):
        findings = []
        auth_log = "/var/log/auth.log"

        if not os.path.exists(auth_log):
            return findings

        try:
            with open(auth_log, "r", errors="ignore") as f:
                lines = f.readlines()[-200:]
        except Exception:
            return findings

        now = time.time()

        for line in lines:
            if "Failed password" in line:
                parts = line.split()
                user = parts[parts.index("for") +
                             1] if "for" in parts else "unknown"
                self.user_failures[user].append(now)

        for user, attempts in self.user_failures.items():
            while attempts and now - attempts[0] > 300:
                attempts.popleft()

            if len(attempts) > 5:
                findings.append((
                    f"Brute-force login attempt detected for user '{user}'",
                    0.85
                ))

        return findings

# ─────────────────────────────────────────────
# USB & PERIPHERAL DETECTION
# ─────────────────────────────────────────────


class USBMonitorEngine:
    def __init__(self):
        self.known_devices = set()

    def analyze(self):
        findings = []
        dev_path = "/dev"

        try:
            devices = set(os.listdir(dev_path))
        except Exception:
            return findings

        removable = {d for d in devices if d.startswith(("sd", "usb"))}
        new = removable - self.known_devices

        for d in new:
            findings.append((
                f"New removable device detected: /dev/{d}",
                0.8
            ))

        self.known_devices |= removable
        return findings

# ─────────────────────────────────────────────
# POLICY ENGINE (FULL)
# ─────────────────────────────────────────────


class PolicyEngine:
    def propose(self, finding, confidence):
        return {
            "finding": finding,
            "confidence": round(confidence, 2),
            "recommended_action": [
                "alert user",
                "preserve forensic artifacts",
                "prepare isolation plan"
            ],
            "requires_authority": True
        }


# ─────────────────────────────────────────────
# ORION DEFENSE KERNEL
# ─────────────────────────────────────────────

class OrionDefenseKernel:

    def __init__(self, watch_path=".", event_sink=None):
        self.event_sink = event_sink
        self.event_callback = None
        self.memory = DeterministicMemory()
        self.sensors = Sensors()
        self.behavior = BehavioralAnomalyEngine()
        self.process = ProcessIntegrityEngine()
        self.correlation = ThreatCorrelationEngine()
        self.policy = PolicyEngine()
        self.network = NetworkTrafficEngine()
        self.auth = UnauthorizedAccessEngine()
        self.usb = USBMonitorEngine()
        self.mitigation = MitigationExecutionEngine()
        self.observer = Observer()
        self.mitigation_planner = MitigationPlanner()
        self.active_plan = None
        self.trust = TrustContext()

    def set_event_callback(self, callback):
        """
        Register a callback to notify the Orchestrator of events.
        """
        self.event_callback = callback

        # TRUST THE AGENT
        self.trust.trust_path(
            "/home/rohith/ORION/windows_agent.py",
            ttl=999999999)

        # Exempt NeMo and Vosk dynamic TTS / STT swap directories from
        # mass-file integrity panics
        self.trust.trust_path("/tmp", ttl=999999999)
        self.trust.trust_path("/var/tmp", ttl=999999999)

        # BRIDGE SERVER (Pending Implementation in Phase 3/4)
        # However, to prevent AttributeError crashes when mitigation tries to
        # act, define empty mock or local callback
        self.bridge = BridgeServer(self, port=5000)
        self.bridge.start()

        WATCH_PATHS = [
            "/home",
            "/tmp",
            "/var/tmp",
            "/etc",
            "/usr/local"
        ]

        for path in WATCH_PATHS:
            if os.path.exists(path):
                self.observer.schedule(
                    OrionFileEventHandler(self),
                    path,
                    recursive=True
                )

        self.observer.start()

# ─────────────────────────────────────────────
# INCIDENT STATE MANAGEMENT
# ─────────────────────────────────────────────

    def process_telemetry(self, msg):
        """
        Ingest telemetry from the Bridge (Windows Agent).
        """
        cat = msg.get("category")
        payload = msg.get("payload")

        # print(f"[ORION KERNEL] 📥 Processing Telemetry: {cat}")

        # 1. Store in Event Memory
        self.memory.store_event(SecurityEvent("windows_agent", cat, payload))

        # 2. Analyze for Threats (Simple Keyword Matching for Alpha)
        if cat == "WIN_EVENT":
            if "4625" in str(payload) or "Audit Failure" in str(payload):
                self.raise_finding(
                    "Detected Windows Logon Failure (Brute Force Risk)",
                    confidence=0.7,
                    details={
                        "raw": payload})
            elif "1102" in str(payload):
                self.raise_finding(
                    "Windows Audit Log Cleared (Covering Tracks)",
                    confidence=0.95,
                    details={
                        "raw": payload})

        elif cat == "PROCESS_START":
            # Support both legacy string and new dict payload
            if isinstance(payload, dict):
                proc_name = payload.get("name", "").lower()
                pid = payload.get("pid")
            else:
                proc_name = str(payload).lower()
                pid = None

            # [NOISE FILTER]
            IGNORED_PROCS = [
                "arecord", "python", "python3", "wsl.exe", "wslhost.exe",
                "svchost.exe", "conhost.exe", "explorer.exe",
                "chrome.exe", "code.exe", "vmmem"
            ]
            if any(ign in proc_name for ign in IGNORED_PROCS):
                return
        suspicious = [
            "mimikatz.exe", "ncat.exe", "powershell.exe",
            "notepad.exe", "malware_simulator.py", "maleware_simulator.exe"
        ]
        if proc_name in suspicious:  # Suspicious
            self.raise_finding(
                f"Suspicious Process Started: {proc_name}",
                confidence=0.95,
                details={"process": proc_name, "pid": pid}
            )

    # ───── Update incident state ─────
    def update_incident_state(self, finding, confidence):
        proposed = (
            IncidentState.CONFIRMED
            if confidence >= 0.9
            else IncidentState.SUSPICIOUS
        )

        # Already confirmed → do nothing
        if self.memory.incident_state == IncidentState.CONFIRMED:
            return

        # Ignore duplicate suspicious
        if (
            self.memory.incident_state == IncidentState.SUSPICIOUS
            and proposed == IncidentState.SUSPICIOUS
        ):
            return

        self.memory.incident_state = proposed
        self.memory.incident_reason = finding
        self.memory.incident_started_at = datetime.now(timezone.utc)
        self.memory.incident_active = True

        print(f"[ORION STATE] Incident escalated → {proposed.value.upper()}")

        # ───── Create mitigation plan (PROPOSE ONLY) ─────
        if proposed == IncidentState.CONFIRMED and self.active_plan is None:
            self.create_mitigation_plan(finding, confidence)

    def create_mitigation_plan(self, finding, confidence, details=None):
        """
        If confidence is high, we can AUTONOMOUSLY request action
        via the Bridge.
        """
        plan_id = str(uuid.uuid4())

        # 1. Identify Action
        action_type = "ALERT_USER"  # Default
        cmd = None

        if "suspicious host process" in finding.lower():
            # Example: "Suspicious Host Process: malware.exe (PID 1234)"
            if details and "pid" in details:
                action_type = "KILL_PROCESS"
                cmd = {
                    "action": "KILL_PROCESS",
                    "pid": details["pid"],
                    "id": plan_id
                }

        elif (
            "port scan" in finding.lower() or
            "brute-force" in finding.lower()
        ):
            if details and "ip" in details:
                action_type = "BLOCK_IP"
                cmd = {
                    "action": "BLOCK_IP",
                    "ip": details["ip"],
                    "id": plan_id
                }

        # 2. NOTIFY USER (Voice Confirmation Required)
        # We NO LONGER auto-execute. We ask Rohith.
        # [REFINEMENT] Only speak if confidence is high and actionable
        is_windows_threat = (
            "windows" in finding.lower() or
            "mimikatz" in finding.lower() or
            "ncat" in finding.lower()
        )

        if (
            confidence >= 0.9 and cmd and
            self.event_callback and is_windows_threat
        ):
            print(f"[ORION DEFENSE] 🛡️ PROPOSING MITIGATION: {action_type}")

            # Store plan first
            self.active_plan = {
                "id": plan_id,
                "finding": finding,
                "confidence": confidence,
                "proposed_action": action_type,
                "cmd": cmd
            }

            # Notify Orchestrator to Speak
            self.event_callback({
                "type": "DEFENSE_PROPOSAL",
                "finding": finding,
                "action": action_type,
                "target": details.get("pid") or details.get("ip") or "Unknown"
            })
            return

        # 3. Otherwise, just log plan
        self.active_plan = {
            "id": plan_id,
            "finding": finding,
            "confidence": confidence,
            "proposed_action": action_type,
            "cmd": cmd
        }

        if self.active_plan:
            print("[ORION MITIGATION] Plan generated")
            print(f"  → {self.active_plan['proposed_action']}")

    def approve_mitigation(self):
        if not self.active_plan:
            print("[ORION MITIGATION] No active plan to approve")
            return

        print("[ORION MITIGATION] Authority approved — executing plan")
        if self.active_plan.get("cmd"):
            if getattr(self, "bridge", None):
                self.bridge.send_command(self.active_plan["cmd"])
            else:
                print(
                    "[ORION MITIGATION] Bridge disconnected. "
                    "Falling back to simple log execution"
                )
        else:
            action = self.active_plan.get('proposed_action', 'Unknown')
            print(f"  → No specific command for: {action}")

        self.memory.incident_state = IncidentState.CONTAINED
        print("[ORION STATE] Incident escalated → CONTAINED")
        self.active_plan = None

    def execute_manual_action(self, action_type, target):
        """
        Manually trigger a defense action via the Bridge.
        """
        print(f"[ORION DEFENSE] 🛡️ MANUAL OVERRIDE: {action_type} -> {target}")

        cmd = None
        if action_type == "KILL_PROCESS":
            # Try to parse target as PID (int) or Name (str)
            try:
                pid = int(target)
                cmd = {
                    "action": "KILL_PROCESS",
                    "pid": pid,
                    "id": str(uuid.uuid4())
                }
            except ValueError:
                # Assuming name - requires Windows Agent to handle name resolution or we fail
                # For now, let's assume PID for safety or specific Name support
                print("⚠️ Manual Kill requires PID for safety.")
                return "Failed: PID required"

        elif action_type == "BLOCK_IP":
            cmd = {
                "action": "BLOCK_IP",
                "ip": target,
                "id": str(uuid.uuid4())
            }

        if cmd:
            if getattr(self, "bridge", None):
                self.bridge.send_command(cmd)
            else:
                print(
                    f"[ORION DEFENSE] Bridge absent. Failed execute: "
                    f"{action_type}"
                )
            self.memory.store_event(
                SecurityEvent(
                    "orion_kernel", "manual_action", cmd, severity=1.0
                )
            )
            return f"Executed {action_type} on {target}"

        return "Unknown Action"

    def raise_finding(self, finding, confidence, details=None):
        self.update_incident_state(finding, confidence)

        key = finding.split(":")[0]
        if key in self.memory.alert_cache:
            return
        self.memory.alert_cache.add(key)
        self.log(finding, confidence)
        if self.memory.incident_state == IncidentState.CONFIRMED and self.active_plan is None:
            self.create_mitigation_plan(finding, confidence, details)

    def tick(self):
        for event in self.sensors.collect():
            self.memory.store_event(event)

            result = self.behavior.analyze(event, self.memory)
            if result:
                self.raise_finding(*result)

            result = self.process.analyze(event, self.memory)
            if result:
                self.raise_finding(*result)

        for finding, conf in self.correlation.correlate(self.memory):
            self.raise_finding(finding, conf)
        for finding, conf in self.network.analyze(self.memory):
            self.raise_finding(finding, conf)
        for finding, conf in self.auth.analyze():
            self.raise_finding(finding, conf)
        for finding, conf in self.usb.analyze():
            self.raise_finding(finding, conf)

    def reset_incident(self):
        self.memory.incident_state = IncidentState.NORMAL
        self.memory.incident_reason = None
        self.memory.incident_started_at = None
        self.memory.alert_cache.clear()
        self.memory.incident_active = False
        print("[ORION STATE] Incident reset → NORMAL")

    def log(self, proposal, confidence=None):
        if confidence:
            print(f"[ORION DEFENSE] {proposal} (Confidence: {confidence})")
        else:
            print(f"[ORION DEFENSE] {proposal}")


# ─────────────────────────────────────────────
# HOST-LINK BRIDGE SERVER (TCP JSON)
# ─────────────────────────────────────────────
import socket  # noqa: E402
import threading  # noqa: E402
import json  # noqa: E402


class BridgeServer:
    def __init__(self, kernel, port=5000):
        self.kernel = kernel
        self.port = port
        self.running = True
        self.server_socket = None
        self.clients = []

    def start(self):
        t = threading.Thread(target=self._listen_loop, daemon=True)
        t.start()

    def _listen_loop(self):
        try:
            self.server_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen(5)
            print(f"[ORION BRIDGE] Listening on 0.0.0.0:{self.port}")

            while self.running:
                client, addr = self.server_socket.accept()
                print(f"[ORION BRIDGE] Connection from {addr}")
                self.clients.append(client)
                t = threading.Thread(
                    target=self._handle_client, args=(
                        client,), daemon=True)
                t.start()
        except Exception as e:
            print(f"[ORION BRIDGE] Server error: {e}")

    def _handle_client(self, client):
        buffer = ""
        while self.running:
            try:
                data = client.recv(4096)
                if not data:
                    break

                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue

                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "TELEMETRY":
                            self.kernel.process_telemetry(msg)
                        elif msg.get("type") == "HEARTBEAT":
                            pass  # Keep-alive
                    except json.JSONDecodeError:
                        print(f"[ORION BRIDGE] Bad JSON: {line}")

            except Exception as e:
                print(f"[ORION BRIDGE] Client Error: {e}")
                break

        print("[ORION BRIDGE] Client disconnected")
        if client in self.clients:
            self.clients.remove(client)
            client.close()

    def send_command(self, cmd):
        msg = json.dumps(cmd) + "\n"
        to_remove = []
        for client in self.clients:
            try:
                client.sendall(msg.encode('utf-8'))
            except Exception as e:
                print(f"[ORION BRIDGE] Send Error: {e}")
                to_remove.append(client)

        for client in to_remove:
            if client in self.clients:
                self.clients.remove(client)

        if client in self.clients:
            self.clients.remove(client)
        client.close()

    def _process_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "TELEMETRY":
            # Ingest external telemetry as a trusted event
            payload = msg.get("payload", {})
            cat = msg.get("category", "host_unknown")

            event = SecurityEvent(
                source="windows_host",
                category=cat,
                payload=payload
            )
            self.kernel.memory.store_event(event)

            # Route specific findings
            if cat == "process":
                # Example: Check for suspicious host processes here
                pass

        elif msg_type == "HANDSHAKE":
            print(f"[ORION BRIDGE] Handshake from {msg.get('platform')}")


# ─────────────────────────────────────────────
# RUN LOOP
# ─────────────────────────────────────────────

if __name__ == "__main__":
    kernel = OrionDefenseKernel(watch_path="/")
    try:
        while True:
            kernel.tick()
            time.sleep(3)
    except KeyboardInterrupt:
        kernel.observer.stop()
        kernel.observer.join()
