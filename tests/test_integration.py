import os
import sys

# Ensure src/ is in path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from core.orchestrator import OrionOrchestrator
import time
import subprocess

print("--- ORION NATIVE INTEGRATION TEST SUITE ---")
print("🚀 Initializing ORION Core in TEST_MODE...")

os.environ["ORION_TEST_MODE"] = "1"
orion = OrionOrchestrator()

def query_orion(message, chat_mode=False, god_mode=False):
    print(f"\n🗣️ USER: {message}")
    if chat_mode:
        response = orion.route(message)
    else:
        response = orion.route(message, god_mode=god_mode)

    print(f"🤖 ORION [{response.get('type', 'UNKNOWN')}]: {response.get('content', '')}")
    return response

# 1. Memory & Self Learning
print("\n[1] Testing Episodic Memory & Context...")
query_orion("Hello Orion. I want you to remember that the secret override sequence is OMEGA-7.", chat_mode=True)
time.sleep(1)
query_orion("What is the secret override sequence?", chat_mode=True)

# 2. Document Generation
print("\n[2] Testing Document Engine (DOCX Generation)...")
query_orion("Create a detailed documentation about Neural Networks.", god_mode=True)

# 3. PPT Generation
print("\n[3] Testing Presentation Writer (PPTX Generation)...")
query_orion("Create a presentation deck about the history of the Apollo Moon Landings.", god_mode=True)

print("\n--- INTEGRATION TESTS COMPLETE ---")
