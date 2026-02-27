# reflection.py
import json


class OrionReflection:
    """
    ORION Reflection – Phase 3.4 (AI POWERED)
    Reads action ledger and produces self-analysis using OrionBrain.
    """

    def __init__(self, brain, memory):
        self.brain = brain
        self.memory = memory

    def _clean_json(self, text: str) -> str:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

    def post_mortem(self, ledger) -> dict:
        """
        Analyzes the recent actions in the ledger to learn lessons.
        """
        # Get last 10 actions
        recent_actions = ledger.get_history()[-10:]
        if not recent_actions:
            return {"status": "NO_DATA"}

        # Format for LLM
        history_text = json.dumps(recent_actions, indent=2)

        prompt = (
            f"ACTION HISTORY:\n{history_text}\n\n"
            "Analyze this execution history. "
            "Did it succeed? Did it fail?\n"
            "CRITICALLY: Did the user express any preference or constraint? "
            "(e.g., 'Use click', 'Avoid argparse')\n"
            "Return ONLY a JSON object:\n"
            "{\n"
            "  \"success\": true,\n"
            "  \"lesson\": \"Single sentence lesson learned.\",\n"
            "  \"user_preference\": \"User prefers CLICK over ARGPARSE.\" "
            "(or null)\n"
            "}"
        )

        response = self.brain.think(prompt, max_tokens=256)

        try:
            clean_resp = self._clean_json(response)
            data = json.loads(clean_resp)
            lesson = data.get("lesson")

            if lesson:
                self.memory.add(
                    f"lesson_{len(recent_actions)}", lesson, mtype="LESSON"
                )
                print(f"[REFLECTION] 🧠 Learned: {lesson}")

            # Store User Preference
            pref = data.get("user_preference")
            if pref:
                self.memory.add(
                    f"pref_{len(recent_actions)}", pref, mtype="USER_PREF"
                )
                print(f"[REFLECTION] ⭐️ User Preference Learned: {pref}")

            return data
        except Exception as e:
            print(f"[REFLECTION] Error: {e}")
            return {"status": "ERROR", "error": str(e)}
