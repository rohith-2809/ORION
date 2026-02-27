import socket
import json
import time
import psutil
import os
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor

# CONFIGURATION
ORION_HOST = "127.0.0.1"  # Connect to WSL via localhost
ORION_PORT = 5000
AUTH_TOKEN = "ORION_SECURE_TOKEN_123"  # Simple shared secret for now

# Global Thread Pool to prevent runaway thread creation
executor = ThreadPoolExecutor(max_workers=4)


class SystemMaintenanceEngine:
    __slots__ = ()
    """
    Handles System Hygiene: Cleanup, Scanning, Integration Checks.
    """

    async def clean_junk(self):
        """
        Cleans Temp folders and Prefetch asynchronously via generators.
        """
        deleted_count = 0
        reclaimed_bytes = 0

        targets = [
            os.environ.get("TEMP"),
            os.path.join(os.environ.get("SystemRoot"), "Temp"),
            os.path.join(os.environ.get("SystemRoot"), "Prefetch")
        ]

        def _cleanup_gen():
            for folder in targets:
                if folder and os.path.exists(folder):
                    for root, _, files in os.walk(folder):
                        for f in files:
                            yield os.path.join(root, f)

        # Run file operations off the main event loop
        def _delete_files():
            nonlocal deleted_count, reclaimed_bytes
            for path in _cleanup_gen():
                try:
                    size = os.path.getsize(path)
                    os.remove(path)
                    deleted_count += 1
                    reclaimed_bytes += size
                except Exception:
                    pass

        await asyncio.get_event_loop().run_in_executor(executor, _delete_files)

        return {
            "status": "completed",
            "files_removed": deleted_count,
            "space_reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 2)
        }

    async def deep_scan(self):
        """
        Recursive scan for known malware signatures via generators and async I/O.
        """
        user_profile = os.environ.get("USERPROFILE")
        scan_paths = [
            os.path.join(user_profile, "Downloads"),
            os.path.join(user_profile, "Desktop")
        ]
        bad_names = {"malware.exe", "virus.bat", "mimikatz.exe", "nc.exe"}
        suspicious_files = []

        def _scan_gen():
            for path in scan_paths:
                if path and os.path.exists(path):
                    for root, _, files in os.walk(path):
                        for f in files:
                            if f.lower() in bad_names or f.endswith(".vbs"):
                                yield os.path.join(root, f)

        def _collect():
            for susp_path in _scan_gen():
                suspicious_files.append(susp_path)

        await asyncio.get_event_loop().run_in_executor(executor, _collect)

        return {
            "status": "completed",
            "issues_found": len(suspicious_files),
            "details": suspicious_files
        }

    async def run_integrity_check(self):
        """
        Runs async process to check system integrity.
        """
        try:
            # sfc /scannow asynchronous subprocess
            proc = await asyncio.create_subprocess_exec(
                "sfc", "/scannow",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1200)
            output = stdout.decode()

            if proc.returncode == 0:
                status = "Clean"
                details = "No integrity violations found."
            elif "found corrupt files and successfully repaired" in output:
                status = "Repaired"
                details = "Corrupt files found and repaired."
            elif "found corrupt files but was unable to fix" in output:
                status = "Critical"
                details = "Corrupt files found and could NOT be fixed."
            else:
                status = "Unknown"
                details = "Scan completed with unexpected output."

            return {
                "status": "completed",
                "health_status": status,
                "details": details,
                "raw_output": output[-200:] if output else ""
            }
        except asyncio.TimeoutError:
            return {"status": "error", "msg": "SFC Timed Out"}
        except Exception as e:
            return {"status": "error", "msg": str(e)}


class OrionWindowsAgent:
    __slots__ = ('sock', 'connected', 'running', 'maintenance', 'loop')

    def __init__(self):
        self.sock = None
        self.connected = False
        self.running = True
        self.maintenance = SystemMaintenanceEngine()
        self.loop = asyncio.get_event_loop()

    async def connect(self):
        retry_count = 0
        max_retries = 3

        while self.running and retry_count < max_retries:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setblocking(False)

                # Attempt async connection
                await self.loop.sock_connect(self.sock, (ORION_HOST, ORION_PORT))
                self.connected = True
                print(f"[ORION AGENT] Connected to {ORION_HOST}:{ORION_PORT}")

                # Handshake
                await self.send({"type": "HANDSHAKE", "token": AUTH_TOKEN, "platform": "Windows"})

                # Reset retries on successful connection
                retry_count = 0

                # Start Listen Loop asynchronously
                await self.listen_loop()

            except ConnectionRefusedError:
                retry_count += 1
                print(
                    f"[ORION AGENT] Connection refused ({retry_count}/{max_retries}). Retrying in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                self.connected = False
                retry_count += 1
                print(
                    f"[ORION AGENT] Connection error: {e} ({retry_count}/{max_retries}). Retrying in 5s...")
                await asyncio.sleep(5)
            finally:
                if self.sock:
                    self.sock.close()
                    self.connected = False

        if retry_count >= max_retries:
            print(
                "[ORION AGENT] Max retries reached. Shutting down connection attempts.")
            self.running = False

    async def send(self, data):
        if not self.connected or not self.sock:
            return
        try:
            msg = json.dumps(data) + "\n"
            await self.loop.sock_sendall(self.sock, msg.encode('utf-8'))
        except Exception as e:
            self.connected = False
            print(f"[ORION AGENT] Send error: {e}")  # Log the error

    async def listen_loop(self):
        buffer = ""
        while self.connected:
            try:
                data = await self.loop.sock_recv(self.sock, 4096)
                if not data:
                    self.connected = False
                    break

                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        await self.handle_command(json.loads(line))
            except Exception as e:
                self.connected = False
                print(f"[ORION AGENT] Listen loop error: {e}")  # Log the error

    async def handle_command(self, cmd):
        action = cmd.get("action")

        if action == "KILL_PROCESS":
            pid = cmd.get("pid")
            try:
                p = psutil.Process(pid)
                # Terminate locally without hanging loop
                p.terminate()
                await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "SUCCESS", "msg": f"Killed PID {pid}"})
            except Exception as e:
                await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "ERROR", "msg": str(e)})

        elif action == "BLOCK_IP":
            ip = cmd.get("ip")
            try:
                rule_name = f"Orion_Block_{ip}_{int(time.time())}"
                # Async subprocess call to prevent event loop block
                proc = await asyncio.create_subprocess_exec(
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip}"
                )
                await proc.wait()
                if proc.returncode == 0:
                    await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "SUCCESS", "msg": f"Blocked IP {ip}"})
                else:
                    await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "ERROR", "msg": f"Netsh code {proc.returncode}"})
            except Exception as e:
                await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "ERROR", "msg": str(e)})

        elif action == "MAINTENANCE_CLEAN":
            res = await self.maintenance.clean_junk()
            await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "SUCCESS", "data": res})

        elif action == "MAINTENANCE_SCAN":
            res = await self.maintenance.deep_scan()
            await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "SUCCESS", "data": res})

        elif action == "MAINTENANCE_INTEGRITY":
            # Run integrity check asynchronously
            res = await self.maintenance.run_integrity_check()
            await self.send({"type": "RESULT", "id": cmd.get("id"), "status": "SUCCESS", "data": res})

    async def monitor_events(self):
        """
        Stream Windows Security Events asynchronously without blocking.
        """
        while self.running:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "powershell", "-NoProfile", "-Command",
                    "Get-WinEvent -LogName Security -MaxEvents 5 | Where-Object {$_.Id -in 4624, 4625, 1102, 4720} | Select-Object TimeCreated, Id, Message",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()

                if stdout:
                    lines = stdout.decode().strip().split('\n')
                    for line in lines[3:]:
                        if not line.strip():
                            continue
                        await self.send({
                            "type": "TELEMETRY",
                            "category": "WIN_EVENT",
                            "payload": line.strip(),
                            "timestamp": time.time()
                        })

                await asyncio.sleep(5)
            except Exception as e:
                # Log the error
                print(f"[ORION AGENT] Monitor events error: {e}")
                await asyncio.sleep(10)

    async def telemetry_loop(self):
        # Fire and forget event monitor
        asyncio.create_task(self.monitor_events())

        # -----------------------------------------------------
        # WATCH PATHS
        # -----------------------------------------------------
        drive_letters = ["C:\\", "D:\\", "E:\\"]
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class AsyncWindowsFileEventHandler(FileSystemEventHandler):
                def __init__(self, agent_instance, base_path):
                    self.agent = agent_instance
                    self.base_path = base_path
                    self.excluded_paths = [
                        os.path.join(base_path, "Windows"),
                        os.path.join(base_path, "$Recycle.Bin"),
                        os.path.join(base_path, "System Volume Information"),
                        os.path.join(base_path, "Program Files"),
                        os.path.join(base_path, "Program Files (x86)"),
                        os.path.join(base_path, "ProgramData")
                    ]
                    self.excluded_paths = [p.lower()
                                           for p in self.excluded_paths]

                def _is_excluded(self, path):
                    path_lower = path.lower()

                    # Ignore the agent's own directory regardless of where it
                    # is placed
                    agent_dir = os.path.abspath(
                        os.path.dirname(__file__)).lower()
                    if path_lower.startswith(agent_dir):
                        return True

                    # Ignore common env names and any folder named orion
                    if "\\env\\" in path_lower or "\\venv\\" in path_lower or "\\.env\\" in path_lower or "\\orion\\" in path_lower:
                        return True

                    for excluded in self.excluded_paths:
                        if path_lower.startswith(excluded):
                            return True
                    return False

                def _dispatch_telemetry(self, cat, payload):
                    # Fire-and-forget sending to not block watchdog's thread
                    asyncio.run_coroutine_threadsafe(
                        self.agent.send({
                            "type": "TELEMETRY",
                            "category": cat,
                            "payload": payload,
                            "timestamp": time.time()
                        }),
                        self.agent.loop
                    )

                def on_created(self, event):
                    if not event.is_directory and not self._is_excluded(
                            event.src_path):
                        self._dispatch_telemetry(
                            "FILE_CREATED", event.src_path)

                def on_deleted(self, event):
                    if not event.is_directory and not self._is_excluded(
                            event.src_path):
                        self._dispatch_telemetry(
                            "FILE_DELETED", event.src_path)

                def on_modified(self, event):
                    if not event.is_directory and not self._is_excluded(
                            event.src_path):
                        self._dispatch_telemetry(
                            "FILE_MODIFIED", event.src_path)

                def on_moved(self, event):
                    if not event.is_directory and not self._is_excluded(
                            event.src_path) and not self._is_excluded(event.dest_path):
                        self._dispatch_telemetry(
                            "FILE_MOVED", {
                                "src": event.src_path, "dest": event.dest_path})

            self.observer = Observer()
            for drive in drive_letters:
                if os.path.exists(drive):
                    event_handler = AsyncWindowsFileEventHandler(self, drive)
                    self.observer.schedule(
                        event_handler, drive, recursive=True)
            self.observer.start()
        except ImportError:
            print("[ORION AGENT] Watchdog not installed, file monitoring disabled.")
        except Exception as e:
            print(f"[ORION AGENT] Error starting file monitoring: {e}")

        last_procs = set()

        while self.running:
            if not self.connected:
                await asyncio.sleep(1)
                continue

            cpu_pct = psutil.cpu_percent()

            # Idle optimization: drop out deep scans and limit heavy resource
            # pulls if CPU starts spiking wildly

            # 1. Process List tracking
            try:
                # Use executor since psutil can sporadically block locally
                # depending on WMI state
                current_procs_iter = await self.loop.run_in_executor(executor, lambda: {p.info['name'] for p in psutil.process_iter(['name'])})
                new_procs = current_procs_iter - last_procs

                if new_procs and last_procs:
                    for proc in new_procs:
                        await self.send({
                            "type": "TELEMETRY",
                            "category": "PROCESS_START",
                            "payload": proc,
                            "timestamp": time.time()
                        })
                last_procs = current_procs_iter
            except Exception as e:
                # Log the error
                print(f"[ORION AGENT] Process tracking error: {e}")

            # 2. Resource Stats
            mem = psutil.virtual_memory().percent
            await self.send({"type": "TELEMETRY", "category": "resource", "payload": {"cpu": cpu_pct, "memory": mem}})
            await self.send({"type": "HEARTBEAT", "timestamp": time.time()})

            # Throttle heartbeat/loop dynamically based on usage
            await asyncio.sleep(2 if cpu_pct < 60 else 5)

    async def start(self):
        asyncio.create_task(self.telemetry_loop())
        await self.connect()


if __name__ == "__main__":
    try:
        agent = OrionWindowsAgent()
        # Suppress massive tracing in windows when not debugging
        sys.tracebacklimit = 0
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass
