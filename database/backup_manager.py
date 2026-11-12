import os
import shutil
import sqlite3
from datetime import datetime

import dashboard_config as cfg
import database.db_manager as db_base

class DatabaseBackupManager:
    """
    Manages safe SQLite database backups, integrity audits, and disaster recovery.
    Uses SQLite's online backup API (safe during concurrent writes and WAL mode).
    """
    
    def __init__(self, db_path=None, backup_dir=None):
        self.db_path = db_path or db_base.DB_FILE
        self.backup_dir = backup_dir or os.path.join(cfg.BASE_DIR, "database", "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        
    def check_integrity(self):
        """
        Runs SQLite PRAGMA integrity_check and quick_check.
        """
        if not os.path.exists(self.db_path):
            return {"status": "ERROR", "is_healthy": False, "message": f"Database file {self.db_path} does not exist."}
            
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        
        cur.execute("PRAGMA integrity_check;")
        integrity_row = cur.fetchone()[0]
        
        cur.execute("PRAGMA foreign_key_check;")
        fk_violations = cur.fetchall()
        
        cur.execute("PRAGMA journal_mode;")
        journal_mode = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
        table_count = cur.fetchone()[0]
        
        conn.close()
        
        is_healthy = (integrity_row.lower() == "ok") and (len(fk_violations) == 0)
        return {
            "status": "HEALTHY" if is_healthy else "CORRUPTED",
            "is_healthy": is_healthy,
            "integrity_check": integrity_row,
            "foreign_key_violations": len(fk_violations),
            "journal_mode": journal_mode,
            "table_count": table_count,
            "db_size_kb": round(os.path.getsize(self.db_path) / 1024.0, 1)
        }
        
    def create_backup(self):
        """
        Performs an online, zero-downtime atomic backup using the SQLite Backup API.
        Safe against simultaneous reads/writes.
        """
        if not os.path.exists(self.db_path):
            return {"status": "ERROR", "success": False, "message": "Source database not found."}
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"mcx_market_data_backup_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        src_conn = sqlite3.connect(self.db_path, timeout=30.0)
        dst_conn = sqlite3.connect(backup_path)
        
        # Online atomic copy
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
            
        dst_conn.close()
        src_conn.close()
        
        backup_size = os.path.getsize(backup_path)
        return {
            "status": "BACKUP_SUCCESS",
            "success": True,
            "backup_file": backup_filename,
            "backup_path": backup_path,
            "size_bytes": backup_size,
            "size_kb": round(backup_size / 1024.0, 1),
            "timestamp": timestamp
        }
        
    def list_backups(self):
        """
        Lists all available local database backups.
        """
        if not os.path.exists(self.backup_dir):
            return []
            
        backups = []
        for f in os.listdir(self.backup_dir):
            if f.endswith(".db"):
                p = os.path.join(self.backup_dir, f)
                backups.append({
                    "filename": f,
                    "path": p,
                    "size_kb": round(os.path.getsize(p) / 1024.0, 1),
                    "created_at": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")
                })
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)
        
    def restore_backup(self, backup_filename):
        """
        Restores the database from a specified backup file.
        """
        backup_path = os.path.join(self.backup_dir, backup_filename)
        if not os.path.exists(backup_path):
            return {"status": "ERROR", "success": False, "message": f"Backup file {backup_filename} not found."}
            
        # Create safety pre-restore backup first
        self.create_backup()
        
        src_conn = sqlite3.connect(backup_path)
        dst_conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
            
        dst_conn.close()
        src_conn.close()
        
        return {
            "status": "RESTORE_SUCCESS",
            "success": True,
            "restored_from": backup_filename,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

# Module-level convenience functions
_default_manager = None

def get_backup_manager():
    global _default_manager
    if _default_manager is None:
        _default_manager = DatabaseBackupManager()
    return _default_manager

def check_integrity():
    return get_backup_manager().check_integrity()

def create_backup():
    return get_backup_manager().create_backup()

def list_backups():
    return get_backup_manager().list_backups()

def restore_backup(backup_filename):
    return get_backup_manager().restore_backup(backup_filename)

if __name__ == "__main__":
    integ = check_integrity()
    print("Database Integrity:", integ)
    bak = create_backup()
    print("Backup Result:", bak)
