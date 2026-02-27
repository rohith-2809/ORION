# planner.py
import json


class OrionPlanner:
    """
    ORION Planner – Phase 3.8 (AI POWERED)
    Uses OrionBrain to decompose goals into executable steps.
    """

    def __init__(self, brain, memory=None):
        self.brain = brain
        self.memory = memory

    def _clean_json(self, text: str) -> str:
        """
        Extracts JSON from markdown code blocks if present.
        """
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

    def plan(self, goal: str, context: str = "") -> dict:
        """
        Generates a structured plan using Memory (Fast) or LLM (Slow).
        """
        # 1. CHECK MEMORY
        if self.memory:
            cached_steps = self.memory.retrieve_plan(goal)
            if cached_steps:
                return {
                    "goal": goal,
                    "steps": cached_steps,
                    "source": "MEMORY",
                    "executable": True
                }

        # 2. ASK BRAIN (LLM)
        # [USER PREFERENCES]
        prefs = []
        if self.memory:
            recent_prefs = self.memory.get_all_by_type("USER_PREF", limit=5)
            if recent_prefs:
                prefs = [p["value"] for p in recent_prefs]

        pref_context = ""
        if prefs:
            pref_list = "\n- ".join(prefs)
            pref_context = (
                f"\nUSER PREFERENCES (STRICTLY FOLLOW):\n- {pref_list}\n"
            )

        prompt = (
            f"GOAL: {goal}\n"
            f"CONTEXT: {context}\n"
            f"{pref_context}\n"
            "You are a tactical planner. Break this goal into a "
            "sequential list of steps.\n"
            "You have the following tools:\n"
            "- FILE_READ (path)\n"
            "- FILE_WRITE (path, content)\n"
            "- SHELL_EXECUTE (command) [Use sparingly, requires approval]\n\n"
            "Return ONLY a JSON object with this format:\n"
            "{\n"
            "  \"steps\": [\n"
            "    {\"action\": \"FILE_WRITE\", \"payload\": "
            "{\"path\": \"hello.py\", \"content\": \"print('Hello')\"}, "
            "\"description\": \"Create script\"},\n"
            "    {\"action\": \"SHELL_EXECUTE\", \"payload\": "
            "{\"command\": \"python hello.py\"}, "
            "\"description\": \"Run script\"}\n"
            "  ]\n"
            "}"
        )

        response = self.brain.think(prompt, max_tokens=1024)

        try:
            clean_resp = self._clean_json(response)
            plan_data = json.loads(clean_resp)
            steps = plan_data.get("steps", [])

            return {
                "goal": goal,
                "steps": steps,
                "source": "BRAIN",
                "executable": True,
                "raw_response": response
            }
        except Exception as e:
            print(f"[PLANNER] JSON Parse Error: {e}")
            # Fallback to a manual review step
            return {
                "goal": goal,
                "steps": [],
                "executable": False,
                "error": str(e),
                "raw_response": response
            }
