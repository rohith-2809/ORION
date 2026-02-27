import socket
import json
import time


def simulate_attack():
    HOST = '127.0.0.1'
    PORT = 5000

    print(f"--- SIMULATING COMPROMISED HOST ({HOST}:{PORT}) ---")

    try:
        # 1. Connect to Bridge
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        print("✅ Connected to Orion Bridge")

        # 2. Handshake
        handshake = {
            "type": "HANDSHAKE",
            "platform": "Windows 11 (Simulated)",
            "agent_id": "agent_sim_01"
        }
        s.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
        time.sleep(1)

        # 3. Send Malicious Telemetry (Brute Force Simulation)
        telemetry = {
            "type": "TELEMETRY",
            "category": "WIN_EVENT",
            "payload": (
                "EventId: 4625, Message: An account failed to log on. "
                "Account Name: Admin. Source Network Address: 192.168.1.50"
            ),
            "timestamp": time.time()
        }

        print(f"🚀 Sending Telemetry: {telemetry['payload'][:50]}...")
        s.sendall((json.dumps(telemetry) + "\n").encode('utf-8'))

        # 4. Wait for potential commands (Active Defense)
        s.settimeout(5.0)
        try:
            response = s.recv(4096)
            if response:
                print(
                    f"⚠️ RECEIVED COMMAND FROM ORION: {
                        response.decode('utf-8').strip()}")
        except socket.timeout:
            print("ℹ️ No immediate command received (Check Kernel Logs)")

        s.close()
        print("--- SIMULATION COMPLETE ---")

    except ConnectionRefusedError:
        print("❌ Could not connect. Is Orion Kernel running?")


if __name__ == "__main__":
    simulate_attack()
