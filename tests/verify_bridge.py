import threading
import time
import socket
import json
from orion_defense_kernel import OrionDefenseKernel


def mock_event_sink(event):
    print(f"[VERIFY] Event Received: {event['category']} - {event['payload']}")


def verify():
    print("--- STARTING BRIDGE VERIFICATION ---")

    # Initialize Kernel with Mock Sink
    kernel = OrionDefenseKernel(watch_path=".", event_sink=mock_event_sink)

    # Function to simulate Windows Agent (runs in background thread for test)
    def simulated_client():
        time.sleep(2)  # Wait for server to bind
        try:
            print("[VERIFY-CLIENT] Connecting to localhost:5000...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", 5000))

            msg = {
                "type": "HANDSHAKE",
                "token": "TEST_TOKEN",
                "platform": "SimulatedClient"
            }
            sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            print("[VERIFY-CLIENT] Handshake sent. Closing.")
            sock.close()
        except Exception as e:
            print(f"[VERIFY-CLIENT] ERROR: {e}")

    # Start Client Thread
    t_client = threading.Thread(target=simulated_client, daemon=True)
    t_client.start()

    print(
        "[VERIFY] Server started. Waiting 5s for manual or auto connection..."
    )
    time.sleep(5)

    # Initial status check
    if hasattr(kernel, 'bridge'):
        print(f"[VERIFY] Bridge Server Running: {kernel.bridge.running}")
        print(f"[VERIFY] Active Clients: {len(kernel.bridge.clients)}")
    else:
        print("[VERIFY] Bridge not found on kernel!")

    # Cleanup
    kernel.bridge.running = False
    kernel.observer.stop()
    print("--- VERIFICATION END ---")


if __name__ == "__main__":
    verify()
