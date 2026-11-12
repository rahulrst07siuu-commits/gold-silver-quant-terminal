"""
Data Governance and SQLite Schema Management for Phase 10 Data Mining & Quality Engine.
Provides schema migration, versioning, audit logging, and persistence.
"""

import os
import sys
import sqlite3
import hashlib
import json
from datetime import datetime

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import dashboard_config as cfg
import database.db_manager as db_base

def init_phase10_tables(conn=None):
    """Creates Phase 10 audit, anomaly, and data mining governance tables in SQLite."""
    close_after = False
    if conn is None:
        conn = db_base.get_connection()
        close_after = True
    try:
        cur = conn.cursor()
        
        # 1. Dataset Quality Audits
        cur.execute("""
        CREATE TABLE IF NOT EXISTS data_quality_audits (
            audit_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            audit_timestamp TEXT NOT NULL,
            total_rows INTEGER,
            total_cols INTEGER,
            missing_values INTEGER,
            duplicate_rows INTEGER,
            ohlc_errors INTEGER,
            quality_score REAL,
            audit_summary TEXT,
            created_at TEXT NOT NULL
        );
        """)
        
        # 2. Data Anomaly Events
        cur.execute("""
        CREATE TABLE IF NOT EXISTS data_anomaly_events (
            event_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            asset TEXT NOT NULL,
            column_name TEXT NOT NULL,
            original_value REAL,
            detection_method TEXT NOT NULL,
            severity_score REAL,
            classification TEXT NOT NULL,
            action_taken TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        
        # 3. Outlier Classifications & Review Ledger
        cur.execute("""
        CREATE TABLE IF NOT EXISTS outlier_classifications (
            outlier_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            asset TEXT NOT NULL,
            original_value REAL,
            method TEXT NOT NULL,
            classification TEXT NOT NULL,
            reason TEXT NOT NULL,
            action TEXT NOT NULL,
            review_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        
        # 4. Data Corrections Ledger
        cur.execute("""
        CREATE TABLE IF NOT EXISTS data_corrections (
            correction_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            asset TEXT NOT NULL,
            column_name TEXT NOT NULL,
            original_value REAL,
            corrected_value REAL,
            correction_method TEXT NOT NULL,
            rationale TEXT NOT NULL,
            approved_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        
        # 5. Dataset Versions & 3-Tier Layer Lineage
        cur.execute("""
        CREATE TABLE IF NOT EXISTS dataset_versions (
            version_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            layer TEXT NOT NULL,
            file_path TEXT NOT NULL,
            row_count INTEGER,
            col_count INTEGER,
            hash_checksum TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        
        # 6. Feature Mining Results
        cur.execute("""
        CREATE TABLE IF NOT EXISTS feature_mining_results (
            feature_id TEXT PRIMARY KEY,
            feature_name TEXT NOT NULL,
            asset TEXT NOT NULL,
            target_horizon TEXT NOT NULL,
            mutual_info REAL,
            spearman_corr REAL,
            pearson_corr REAL,
            permutation_importance REAL,
            stability_score REAL,
            recommendation TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        
        # 7. Clustering Results
        cur.execute("""
        CREATE TABLE IF NOT EXISTS clustering_results (
            cluster_id TEXT PRIMARY KEY,
            model_type TEXT NOT NULL,
            n_clusters INTEGER,
            silhouette_score REAL,
            calinski_harabasz REAL,
            inertia REAL,
            feature_names TEXT,
            description TEXT,
            created_at TEXT NOT NULL
        );
        """)
        
        # 8. Data Quality Scores
        cur.execute("""
        CREATE TABLE IF NOT EXISTS data_quality_scores (
            score_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            overall_score REAL,
            completeness_score REAL,
            accuracy_score REAL,
            timestamp_score REAL,
            duplicate_score REAL,
            outlier_score REAL,
            unit_score REAL,
            freshness_score REAL,
            deductions_json TEXT,
            created_at TEXT NOT NULL
        );
        """)
        
        conn.commit()
    finally:
        if close_after:
            conn.close()

def log_quality_audit(dataset_name, total_rows, total_cols, missing_values, duplicate_rows, ohlc_errors, score, summary):
    """Persists a data quality audit record."""
    conn = db_base.get_connection()
    try:
        cur = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        audit_id = f"AUDIT_{dataset_name.upper()[:8]}_{int(datetime.now().timestamp())}"
        cur.execute("""
        INSERT OR REPLACE INTO data_quality_audits (
            audit_id, dataset_name, audit_timestamp, total_rows, total_cols,
            missing_values, duplicate_rows, ohlc_errors, quality_score, audit_summary, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (audit_id, dataset_name, ts, total_rows, total_cols, missing_values, duplicate_rows, ohlc_errors, score, summary, ts))
        conn.commit()
        return audit_id
    finally:
        conn.close()

def log_outlier_classification(dataset_name, timestamp, asset, original_value, method, classification, reason, action, review_status="AUTOMATED_REVIEW"):
    """Persists an outlier classification record."""
    return log_outlier_classifications_batch([{
        "dataset_name": dataset_name, "timestamp": timestamp, "asset": asset,
        "original_value": original_value, "method": method, "classification": classification,
        "reason": reason, "action": action, "review_status": review_status
    }])[0]

def log_outlier_classifications_batch(records):
    """Persists multiple outlier classification records in a single atomic transaction."""
    if not records:
        return []
    conn = db_base.get_connection()
    ids = []
    try:
        cur = conn.cursor()
        ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        param_list = []
        for r in records:
            hash_input = f"{r['timestamp']}_{r['method']}_{r['original_value']}".encode()
            outlier_id = f"OUT_{r['asset'][:4]}_{hashlib.md5(hash_input).hexdigest()[:8]}"
            ids.append(outlier_id)
            param_list.append((
                outlier_id, r["dataset_name"], str(r["timestamp"]), r["asset"].upper(),
                float(r["original_value"]), r["method"], r["classification"], r["reason"],
                r["action"], r.get("review_status", "AUTOMATED_REVIEW"), ts_now
            ))
        cur.executemany("""
        INSERT OR REPLACE INTO outlier_classifications (
            outlier_id, dataset_name, timestamp, asset, original_value, method,
            classification, reason, action, review_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, param_list)
        conn.commit()
        return ids
    finally:
        conn.close()

def log_quality_score(dataset_name, overall, comp, acc, ts_score, dup_score, outl_score, unit_score, fresh_score, deductions):
    """Persists detailed data quality score breakdown."""
    conn = db_base.get_connection()
    try:
        cur = conn.cursor()
        ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        score_id = f"DQS_{dataset_name.upper()[:8]}_{int(datetime.now().timestamp())}"
        deductions_str = json.dumps(deductions)
        cur.execute("""
        INSERT OR REPLACE INTO data_quality_scores (
            score_id, dataset_name, overall_score, completeness_score, accuracy_score,
            timestamp_score, duplicate_score, outlier_score, unit_score, freshness_score,
            deductions_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (score_id, dataset_name, overall, comp, acc, ts_score, dup_score, outl_score, unit_score, fresh_score, deductions_str, ts_now))
        conn.commit()
        return score_id
    finally:
        conn.close()

def compute_file_hash(filepath):
    """Calculates SHA256 checksum of dataset file."""
    if not os.path.exists(filepath):
        return None
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()

class DataGovernanceManager:
    """Object-oriented wrapper around Phase 10 governance functions."""
    def __init__(self, db_path=None):
        self.db_path = db_path or db_base.DB_FILE
        init_phase10_tables()

    def log_quality_audit(self, *args, **kwargs):
        return log_quality_audit(*args, **kwargs)

    def log_outlier_classification(self, *args, **kwargs):
        return log_outlier_classification(*args, **kwargs)

    def log_outlier_classifications_batch(self, *args, **kwargs):
        return log_outlier_classifications_batch(*args, **kwargs)

    def log_quality_score(self, *args, **kwargs):
        return log_quality_score(*args, **kwargs)

    def compute_file_hash(self, *args, **kwargs):
        return compute_file_hash(*args, **kwargs)


if __name__ == "__main__":
    init_phase10_tables()
    print("Phase 10 governance tables initialized successfully.")
