# File
import os
import hashlib
from datetime import datetime


class OrionFileExecutor:
    """
    ORION File Executor – Phase 3 (SAFE MODE)

    Capabilities:
    - List files
    - Read files (text only)
    - Metadata extraction
    - NO write / delete / modify
    """

    ALLOWED_ROOT = os.getcwd()  # project root only
    MAX_READ_SIZE = 100_000     # 100 KB safety cap

    def _resolve_path(self, path: str) -> str:
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(self.ALLOWED_ROOT):
            raise PermissionError("Access denied outside project scope")
        return abs_path

    # ---------------- LIST FILES ----------------
    def list_files(self):
        files = []
        for f in os.listdir(self.ALLOWED_ROOT):
            files.append({
                "name": f,
                "type": "dir" if os.path.isdir(f) else "file"
            })
        return files

    # ---------------- READ FILE ----------------
    def read_file(self, path: str):
        path = self._resolve_path(path)

        if not os.path.exists(path):
            return {"error": "File not found"}

        if os.path.isdir(path):
            return {"error": "Cannot read directories"}

        size = os.path.getsize(path)
        if size > self.MAX_READ_SIZE:
            return {"error": "File too large to read safely"}

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return {
            "path": path,
            "size": size,
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "preview": content[:2000],  # never full dump
            "timestamp": datetime.utcnow().isoformat()
        }
