import requests
import time

SERVER_URL = "http://127.0.0.1:3000/api/chat"

print("--- ORION SYSTEM VERIFICATION ---")

# 1. Verify Voice Bug Fix
print("\n[Tests 1] Voice Bug Fix")
print("Sending request with God Mode = True, Chat Mode = True")
res = requests.post(SERVER_URL, json={
    "message": "Hello Orion, this is a voice test.",
    "god_mode": True,
    "chat_mode": True
})
print(
    "Server output should show: '[API] God Mode and Chat Mode enabled -> "
    "Voice disabled'"
)
if res.status_code == 200:
    print(f"Orion Response: {res.json().get('content')}")
else:
    print("Request failed.")


# 2. Verify History & Self Learning
print("\n[Tests 2] History & Self Learning")
print("Sending a fact-containing message.")
res = requests.post(SERVER_URL, json={
    "message": "Hi Orion! Just a quick fact for you: "
               "My favorite color is neon green.",
    "god_mode": False,
    "chat_mode": False
})
if res.status_code == 200:
    print(f"Orion Response: {res.json().get('content')}")
else:
    print("Request failed.")

print("\nWaiting 5 seconds for background fact extraction to complete...")
time.sleep(5)

# 3. Verify Document Generation Bug Fix
print("\n[Tests 3] Document Generation (Bypass Refusals)")
print("Sending request to generate 'Aryan Invasion Theory' outline...")
res = requests.post(SERVER_URL, json={
    "message": "Create a brief documentation on Aryan Invasion Theory in docx",
    "god_mode": True,
    "chat_mode": False
})
print("Check server logs to see if it bypasses the refusal.")
if res.status_code == 200:
    print(f"Orion Response: {res.json().get('content')}")
else:
    print("Request failed.")

print("\n--- VERIFICATION SCRIPT COMPLETE ---")
