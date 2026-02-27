import os
import sys

# Ensure imports work
sys.path.append(os.getcwd())

# Mock Brain for quick testing without loading 4GB model


class MockBrain:
    def __init__(self):
        print("🧠 Mock Brain Initialized")

    def think(self, prompt, max_tokens=100):
        print(f"thinking about: {prompt[:50]}...")
        if "outline" in prompt.lower():
            if "12-slide" in prompt:
                return "1. Intro\n2. Feature A\n3. Feature B\n4. Conclusion"
            return "1. Overview\n2. Details\n3. Summary"

        if "bullet points" in prompt.lower():
            return "• Key Point 1\n• Key Point 2\n• Key Point 3"

        return "Generated content based on prompt."


def test_docs():
    print("--- ORION DOC ENGINE TEST ---")

    try:
        from document_engine import DocumentEngine

        # 1. Setup
        brain = MockBrain()
        engine = DocumentEngine(brain)

        # 2. Test BRIEF Mode
        print("\n📄 Testing BRIEF Mode...")
        job = engine.start_job(
            "Project Orion Status",
            mode="brief",
            output_format="md")
        engine.process_job()
        print(f"✅ Brief Doc Created: {job.output_path}")

        # 3. Test PPTX Mode
        print("\n📊 Testing PPTX Mode...")
        job = engine.start_job(
            "Orion Architecture",
            mode="slide",
            output_format="pptx")
        engine.process_job()
        print(f"✅ Presentation Created: {job.output_path}")

    except ImportError as e:
        print(f"❌ Import Error: {e}")
    except Exception as e:
        print(f"❌ Test Failed: {e}")


if __name__ == "__main__":
    test_docs()
