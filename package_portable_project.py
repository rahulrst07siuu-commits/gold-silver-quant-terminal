"""
Package the complete Gold & Silver Quantitative Project into a portable zip file
suitable for running on any laptop or computer.
"""

import os
import zipfile
import time

PROJECT_DIR = r"D:\Downloads\Gold_Silver_Quant_Project"
OUTPUT_ZIP = r"D:\Downloads\Gold_Silver_Quant_Project_PORTABLE.zip"

EXCLUDE_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "temp", "tmp"}
EXCLUDE_EXTS = {".pyc", ".tmp", ".log"}

def make_portable_zip():
    print(f"[*] Starting portable zip compression from: {PROJECT_DIR}")
    start_time = time.time()
    
    total_files = 0
    total_bytes = 0
    
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for root, dirs, files in os.walk(PROJECT_DIR):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            # Skip old database backups except the latest one to keep zip lean
            if "database" in root and "backups" in root:
                # Keep only the latest backup
                backup_files = [f for f in files if f.endswith(".db")]
                if backup_files:
                    latest = sorted(backup_files)[-1]
                    files = [latest]
                else:
                    files = []
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                if file.endswith("_PORTABLE.zip"):
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, PROJECT_DIR)
                
                try:
                    file_size = os.path.getsize(file_path)
                    zipf.write(file_path, os.path.join("Gold_Silver_Quant_Project", rel_path))
                    total_files += 1
                    total_bytes += file_size
                except Exception as e:
                    print(f"    [!] Warning: Could not add {rel_path}: {e}")
                    
    elapsed = time.time() - start_time
    zip_size = os.path.getsize(OUTPUT_ZIP)
    
    print(f"[*] Successfully created portable zip package:")
    print(f"    -> Output File: {OUTPUT_ZIP}")
    print(f"    -> Files Packaged: {total_files}")
    print(f"    -> Original Size: {total_bytes / (1024*1024):.2f} MB")
    print(f"    -> Compressed Size: {zip_size / (1024*1024):.2f} MB")
    print(f"    -> Compression Ratio: {(1 - zip_size/total_bytes)*100:.1f}% reduction")
    print(f"    -> Elapsed Time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    make_portable_zip()
