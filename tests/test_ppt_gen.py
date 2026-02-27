from skills.presentation_writer import PresentationWriter
import os

topic = "ORION_TEST_PROJECT"
outline = ["Introduction", "Core_Architecture", "Future_Outlook"]
content_map = {
    "Introduction": [
        "- Welcome to Orion",
        "- This is a test slide",
        "- here are the bullet points ignore this"],
    "Core_Architecture": [
        "- Modular Design",
        "- Dark_Theme_Enabled",
        "- python-pptx"],
    "Future_Outlook": [
        "- Scaling Up",
        "- Mobile Integration",
        "- Total Sovereignty"]}

output_path = "test_output.pptx"
if os.path.exists(output_path):
    os.remove(output_path)

print("Generating test PPTX...")
try:
    PresentationWriter.create_deck(topic, outline, content_map, output_path)
    print(f"Success! Saved to {output_path}")
except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()
