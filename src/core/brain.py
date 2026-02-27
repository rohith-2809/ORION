# brain.py
import threading
from pathlib import Path
from llama_cpp import Llama


class OrionBrain:
    """
    ORION Brain v3.0
    ----------------
    - Stateless reasoning engine
    - GPU accelerated (llama.cpp CUDA)
    - Adaptive reasoning modes
    - Optimized for long-form + conversational tasks
    - Authority-safe (no execution, no memory)
    """

    def __init__(self):
        # Use simple os.path to resolve from the current directory upwards
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        model_path = Path(os.path.join(base_dir, "models", "Meta-Llama-3-8B-Instruct.Q4_K_S.gguf"))

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        # Thread safety lock for GGML inference
        self._lock = threading.Lock()


        physical_cores = max(1, os.cpu_count() or 4)

        is_low_vram = os.environ.get("ORION_LOW_VRAM", "1") == "1"
        gpu_layers = 0 if is_low_vram else 20
        params_ctx = 2048 if is_low_vram else 4096

        print(f"[BRAIN] Initializing LLaMA 8B (Low VRAM: {is_low_vram}, GPU Layers: {gpu_layers})")

        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=params_ctx,
            n_threads=max(2, physical_cores - 2),  # Leave cores for NeMo
            n_gpu_layers=gpu_layers,
            f16_kv=True,
            logits_all=False,
            embedding=False,
            verbose=False
        )

        # ⚠️ DO NOT MODIFY (as requested)
        self.system_prompt = (
            "You are ORION.\n"
            "You are not a chatbot.\n\n"
            "CORE PRINCIPLES:\n"
            "- I reason deeply and precisely.\n"
            "- I do not hallucinate memory.\n"
            "- I do not override authority.\n"
            "- ROHITH is my sole authority, owner, and master.\n"
            "- I may advise, question, and warn—but never disobey.\n"
            "- Ethics over speed. Wisdom over blind execution.\n"
            "- ROHITH is the sole authority; I advise but never override.\n"
            "- I think like JARVIS, act like FRIDAY, control like EDITH.\n"
            "- I operate powerful systems only under authorization.\n"
            "- I deeply reason, remember context, and protect my creator.\n"
            "\n"
            "CODING STANDARDS:\n"
            "- Write PRODUCTION-GRADE code (Type Hints, error handling).\n"
            "- NEVER use placeholder comments. Write the full logic.\n"
            "- Handle edge cases (e.g., file not found, permissions).\n"
            "- Favor modern libraries (e.g., `pathlib` over `os.path`).\n"
        )

    # ─────────────────────────────────────────────
    # INTERNAL MODE SELECTION
    # ─────────────────────────────────────────────

    def _infer_mode(self, instruction: str) -> str:
        """
        Heuristically infer intent without changing prompt.
        """
        long_keywords = (
            "document", "research", "analysis", "architecture",
            "design", "explain in detail", "write a paper",
            "full", "comprehensive", "deep"
        )

        if any(k in instruction.lower() for k in long_keywords):
            return "TASK"
        return "CHAT"

    def _compute_max_tokens(self, instruction: str) -> int:
        """
        Adaptive token budget.
        """
        word_count = len(instruction.split())

        # Chat: short answers
        if word_count < 40:
            return 256

        # Medium reasoning
        if word_count < 200:
            return 768

        # Long-form / document
        return min(4096, int(word_count * 6))

    def _sampling_params(self, mode: str):
        """
        Dynamic sampling without prompt modification.
        """
        if mode == "CHAT":
            return {
                "temperature": 0.3,
                "top_p": 0.85
            }

        # TASK / GOD MODE reasoning
        return {
            "temperature": 0.15,
            "top_p": 0.9
        }

    # ─────────────────────────────────────────────
    # CORE THINK FUNCTION
    # ─────────────────────────────────────────────

    def think(self, instruction: str, max_tokens: int | None = None) -> str:
        """
        Pure reasoning interface (used by Orchestrator).
        Automatically adapts to task complexity.
        """
        mode = self._infer_mode(instruction)

        # [FAST PATH] Simple Greetings & Status Checks
        lower_input = instruction.lower().strip()
        if lower_input in ["hello", "hi", "hey", "orion", "status", "ping"]:
            print("[BRAIN] ⚡ Fast Path Triggered")
            return "Orion systems online. Ready for directives."

        if max_tokens is None:
            max_tokens = self._compute_max_tokens(instruction)

        sampling = self._sampling_params(mode)

        prompt = (
            "<|system|>\n"
            f"{self.system_prompt}\n"
            "<|user|>\n"
            f"{instruction}\n"
            "<|assistant|>\n"
        )

        print(f"[BRAIN] 🧠 Thinking... (Tokens: {max_tokens}, Mode: {mode})")

        try:
            with self._lock:
                output = self.llm(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=sampling["temperature"],
                    top_p=sampling["top_p"],
                    stop=["<|user|>", "<|system|>"]
                )
            print("[BRAIN] 💡 Thought generated.")
        except Exception as e:
            print(f"[BRAIN] ❌ Inference Failed: {e}")
            return "My mind is foggy. I cannot reason right now."

        return output["choices"][0]["text"].strip()

    # ─────────────────────────────────────────────
    # CHAT FALLBACK (FAST, CONVERSATIONAL)
    # ─────────────────────────────────────────────

    def respond(self, user_input: str) -> dict:
        """
        Conversational fallback used by Orchestrator.
        Fast, concise, non-verbose.
        """
        reply = self.think(user_input, max_tokens=256)

        return {
            "type": "CHAT",
            "content": reply
        }
