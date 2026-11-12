"""
Secrets and Large Files Audit Script
Scans all project files for potential credentials, API tokens, passwords,
and files exceeding GitHub limits.
"""

import os
import re

PROJECT_DIR = r"D:\Downloads\Gold_Silver_Quant_Project"

SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key\s*[:=]\s*["\'])([A-Za-z0-9_\-]{16,})(["\'])', "API Key"),
    (r'(?i)(secret[_-]?key\s*[:=]\s*["\'])([A-Za-z0-9_\-]{16,})(["\'])', "Secret Key"),
    (r'(?i)(access[_-]?token\s*[:=]\s*["\'])([A-Za-z0-9_\-]{16,})(["\'])', "Access Token"),
    (r'(?i)(password\s*[:=]\s*["\'])([^"\']{6,})(["\'])', "Password"),
    (r'(?i)(jwt[_-]?token\s*[:=]\s*["\'])([A-Za-z0-9_\.\-]{20,})(["\'])', "JWT Token"),
    (r'(?i)(ghp_[A-Za-z0-9]{36})', "GitHub Personal Token"),
]

EXCLUDE_DIRS = {"__pycache__", ".git"}
EXCLUDE_EXTS = {".png", ".jpg", ".joblib", ".zip", ".pyc"}

def audit_project():
    found_secrets = []
    large_files = []
    all_files = []

    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            file_path = os.path.join(root, f)
            rel_path = os.path.relpath(file_path, PROJECT_DIR).replace("\\", "/")
            size = os.path.getsize(file_path)

            all_files.append({"path": rel_path, "size": size})

            # Check size
            if size > 10 * 1024 * 1024: # > 10MB
                large_files.append({"path": rel_path, "size": size})

            # Check secrets in text files
            ext = os.path.splitext(f)[1].lower()
            if ext in EXCLUDE_EXTS:
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    for pattern, kind in SECRET_PATTERNS:
                        matches = re.findall(pattern, content)
                        if matches:
                            # Filter out placeholders
                            for m in matches:
                                val = m[1] if isinstance(m, tuple) and len(m) > 1 else str(m)
                                if any(placeholder in val.lower() for placeholder in ["your_", "example", "placeholder", "xxx", "dummy", "test"]):
                                    continue
                                found_secrets.append({
                                    "file": rel_path,
                                    "kind": kind,
                                    "snippet_masked": val[:4] + "*" * (len(val)-8) + val[-4:] if len(val) > 8 else "***"
                                })
            except Exception as e:
                pass

    return found_secrets, large_files, all_files

if __name__ == "__main__":
    secrets, large_files, all_files = audit_project()
    print("=== SECRETS AUDIT ===")
    print(f"Total potential hardcoded secrets found: {len(secrets)}")
    for s in secrets:
        print(f"  [!] File: {s['file']} | Type: {s['kind']} | Value: {s['snippet_masked']}")

    print("\n=== LARGE FILES AUDIT (> 10 MB) ===")
    print(f"Total files > 10 MB: {len(large_files)}")
    for lf in sorted(large_files, key=lambda x: -x["size"]):
        print(f"  [SIZE] {lf['size']/(1024*1024):.2f} MB | {lf['path']}")
