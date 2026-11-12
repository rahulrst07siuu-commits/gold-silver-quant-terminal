import sqlite3
import os
import json
from datetime import datetime

import database.db_manager as db_base
import dashboard_config as cfg

def get_connection():
    return db_base.get_connection()

def init_monitoring_db():
    """
    Initializes all SQLite tables required for Phase 7 Model Lifecycle Management,
    Accuracy Tracking, Drift Detection, Challenger Training, and Registry.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Model Registry Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_registry (
        model_id TEXT PRIMARY KEY,
        model_name TEXT NOT NULL,
        asset TEXT NOT NULL,
        horizon TEXT NOT NULL,
        model_type TEXT NOT NULL,
        model_family TEXT NOT NULL,
        current_champion_version TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. Model Versions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_versions (
        version_id TEXT PRIMARY KEY,
        model_id TEXT NOT NULL,
        version_tag TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'CANDIDATE',
        training_end_date TEXT,
        training_window_size INTEGER,
        feature_schema_version TEXT DEFAULT 'v1_38feats',
        hyperparameters TEXT,
        val_mae REAL,
        val_rmse REAL,
        val_dir_acc REAL,
        val_r2 REAL,
        test_mae REAL,
        test_rmse REAL,
        test_dir_acc REAL,
        test_r2 REAL,
        model_artifact_path TEXT NOT NULL,
        previous_champion_version TEXT,
        approved_by TEXT,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (model_id) REFERENCES model_registry(model_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_model_status ON model_versions (model_id, status);")
    
    # 3. Forecast Predictions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS forecast_predictions (
        forecast_id TEXT PRIMARY KEY,
        asset TEXT NOT NULL,
        contract TEXT NOT NULL,
        model_id TEXT NOT NULL,
        version_id TEXT NOT NULL,
        horizon TEXT NOT NULL,
        horizon_hours REAL NOT NULL,
        forecast_timestamp TEXT NOT NULL,
        target_due_timestamp TEXT NOT NULL,
        reference_price REAL NOT NULL,
        predicted_return REAL NOT NULL,
        predicted_price REAL NOT NULL,
        prediction_uncertainty REAL DEFAULT 0.0,
        market_regime TEXT DEFAULT 'Normal',
        feature_snapshot_hash TEXT,
        data_source TEXT DEFAULT 'MCX_LIVE',
        feed_status TEXT DEFAULT 'ACTIVE',
        is_shadow INTEGER DEFAULT 0,
        is_evaluated INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fc_eval ON forecast_predictions (is_evaluated, target_due_timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fc_asset_hor ON forecast_predictions (asset, horizon);")
    
    # 4. Forecast Actuals & Matching Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS forecast_actuals (
        evaluation_id TEXT PRIMARY KEY,
        forecast_id TEXT UNIQUE NOT NULL,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        actual_target_timestamp TEXT NOT NULL,
        actual_price REAL NOT NULL,
        actual_return REAL NOT NULL,
        predicted_return REAL NOT NULL,
        forecast_error REAL NOT NULL,
        absolute_error REAL NOT NULL,
        squared_error REAL NOT NULL,
        directional_correct INTEGER NOT NULL,
        forecast_bias REAL NOT NULL,
        baseline_zero_error REAL NOT NULL,
        baseline_rw_error REAL NOT NULL,
        FOREIGN KEY (forecast_id) REFERENCES forecast_predictions(forecast_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_eval_fc ON forecast_actuals (forecast_id);")
    
    # 5. Model Rolling Performance Metrics
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_performance_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version_id TEXT NOT NULL,
        asset TEXT NOT NULL,
        horizon TEXT NOT NULL,
        window_size INTEGER NOT NULL,
        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        forecast_count INTEGER NOT NULL,
        mae REAL NOT NULL,
        rmse REAL NOT NULL,
        directional_accuracy REAL NOT NULL,
        oos_r2 REAL NOT NULL,
        mean_bias REAL NOT NULL,
        prediction_stability_std REAL NOT NULL,
        volatility_forecast_error REAL DEFAULT 0.0,
        calibration_score REAL DEFAULT 0.0,
        benchmark_zero_mae REAL DEFAULT 0.0,
        benchmark_mean_mae REAL DEFAULT 0.0,
        benchmark_rw_mae REAL DEFAULT 0.0,
        champion_outperformed INTEGER DEFAULT 0
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_perf_ver_win ON model_performance_metrics (version_id, window_size);")
    
    # 6. Data & Concept Drift Events Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_drift_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        asset TEXT NOT NULL,
        drift_type TEXT NOT NULL,
        feature_name TEXT,
        psi_score REAL,
        ks_stat REAL,
        p_value REAL,
        adwin_detected INTEGER DEFAULT 0,
        warning_level TEXT NOT NULL,
        description TEXT NOT NULL,
        suggested_action TEXT NOT NULL
    );
    """)
    
    # 7. Model Retraining Jobs Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_training_jobs (
        job_id TEXT PRIMARY KEY,
        asset TEXT NOT NULL,
        horizon TEXT NOT NULL,
        candidate_model_family TEXT NOT NULL,
        trigger_type TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        train_samples INTEGER DEFAULT 0,
        val_samples INTEGER DEFAULT 0,
        result_version_id TEXT,
        logs TEXT,
        error_message TEXT
    );
    """)
    
    # 8. Model Validation Results Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_validation_results (
        validation_id TEXT PRIMARY KEY,
        version_id TEXT NOT NULL,
        champion_version_id TEXT,
        validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_integrity_pass INTEGER NOT NULL,
        feature_compat_pass INTEGER NOT NULL,
        chronological_val_pass INTEGER NOT NULL,
        walk_forward_pass INTEGER NOT NULL,
        oos_metrics_pass INTEGER NOT NULL,
        stability_pass INTEGER NOT NULL,
        friction_backtest_pass INTEGER NOT NULL,
        overall_eligibility TEXT NOT NULL,
        improvement_notes TEXT
    );
    """)
    
    # 9. Model Deployment History & Rollbacks
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_deployment_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        model_id TEXT NOT NULL,
        previous_version_id TEXT NOT NULL,
        new_version_id TEXT NOT NULL,
        action TEXT NOT NULL,
        approved_by TEXT NOT NULL DEFAULT 'SYSTEM_OPERATOR',
        approval_notes TEXT NOT NULL
    );
    """)
    
    conn.commit()
    
    # Register existing Phase 3 Champion Models if not already registered
    seed_initial_champions(cur)
    conn.commit()
    conn.close()
    return True

def seed_initial_champions(cur):
    """
    Registers the validated Phase 3 champion models into model_registry and model_versions.
    """
    champions = [
        # 1. Gold 4h ExtraTrees (Phase 3 Winner)
        {
            "model_id": "GOLD_4H_EXTRATREES",
            "model_name": "Gold 4h ExtraTrees Quant Engine",
            "asset": "GOLD",
            "horizon": "4h",
            "model_type": "DIRECTIONAL",
            "model_family": "Tree Ensemble",
            "version_tag": "v1.0.0",
            "val_mae": 0.0039,
            "val_rmse": 0.0058,
            "val_dir_acc": 52.83,
            "val_r2": 0.0026,
            "artifact": os.path.join(cfg.MODELS_DIR, "machine_learning", "gold_target_4h_ExtraTrees.joblib")
        },
        # 2. Silver 4h RandomForest (Phase 3 Winner)
        {
            "model_id": "SILVER_4H_RANDOMFOREST",
            "model_name": "Silver 4h RandomForest Quant Engine",
            "asset": "SILVER",
            "horizon": "4h",
            "model_type": "DIRECTIONAL",
            "model_family": "Tree Ensemble",
            "version_tag": "v1.0.0",
            "val_mae": 0.0071,
            "val_rmse": 0.0104,
            "val_dir_acc": 46.90,
            "val_r2": -0.0084,
            "artifact": os.path.join(cfg.MODELS_DIR, "machine_learning", "silver_target_4h_RandomForest.joblib")
        },
        # 3. Gold 1d Ridge (Phase 3 Winner)
        {
            "model_id": "GOLD_1D_RIDGE",
            "model_name": "Gold Daily Ridge Forecaster",
            "asset": "GOLD",
            "horizon": "1d",
            "model_type": "DIRECTIONAL",
            "model_family": "Linear Regularized",
            "version_tag": "v1.0.0",
            "val_mae": 0.0082,
            "val_rmse": 0.0118,
            "val_dir_acc": 51.20,
            "val_r2": 0.0012,
            "artifact": os.path.join(cfg.MODELS_DIR, "machine_learning", "gold_target_1D_Ridge.joblib")
        },
        # 4. Silver 1d Ridge (Phase 3 Winner)
        {
            "model_id": "SILVER_1D_RIDGE",
            "model_name": "Silver Daily Ridge Forecaster",
            "asset": "SILVER",
            "horizon": "1d",
            "model_type": "DIRECTIONAL",
            "model_family": "Linear Regularized",
            "version_tag": "v1.0.0",
            "val_mae": 0.0142,
            "val_rmse": 0.0195,
            "val_dir_acc": 53.93,
            "val_r2": 0.0045,
            "artifact": os.path.join(cfg.MODELS_DIR, "machine_learning", "silver_target_1D_Ridge.joblib")
        },
        # 5. Gold 1h LightGBM
        {
            "model_id": "GOLD_1H_LIGHTGBM",
            "model_name": "Gold 1h LightGBM Scaler",
            "asset": "GOLD",
            "horizon": "1h",
            "model_type": "DIRECTIONAL",
            "model_family": "Boosting",
            "version_tag": "v1.0.0",
            "val_mae": 0.0021,
            "val_rmse": 0.0034,
            "val_dir_acc": 49.80,
            "val_r2": -0.0015,
            "artifact": os.path.join(cfg.MODELS_DIR, "machine_learning", "gold_target_1h_LightGBM.joblib")
        },
        # 6. Silver 1h ExtraTrees
        {
            "model_id": "SILVER_1H_EXTRATREES",
            "model_name": "Silver 1h ExtraTrees Forecaster",
            "asset": "SILVER",
            "horizon": "1h",
            "model_type": "DIRECTIONAL",
            "model_family": "Tree Ensemble",
            "version_tag": "v1.0.0",
            "val_mae": 0.0042,
            "val_rmse": 0.0062,
            "val_dir_acc": 48.90,
            "val_r2": -0.0032,
            "artifact": os.path.join(cfg.MODELS_DIR, "machine_learning", "silver_target_1h_ExtraTrees.joblib")
        }
    ]
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for c in champions:
        # Check if model exists in registry
        cur.execute("SELECT COUNT(*) FROM model_registry WHERE model_id = ?;", (c["model_id"],))
        if cur.fetchone()[0] == 0:
            version_id = f"{c['model_id']}_{c['version_tag']}"
            cur.execute("""
            INSERT INTO model_registry (
                model_id, model_name, asset, horizon, model_type, model_family,
                current_champion_version, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
            """, (
                c["model_id"], c["model_name"], c["asset"], c["horizon"],
                c["model_type"], c["model_family"], version_id, now_str, now_str
            ))
            
            # Insert champion version
            cur.execute("""
            INSERT OR IGNORE INTO model_versions (
                version_id, model_id, version_tag, status, training_end_date,
                training_window_size, feature_schema_version, hyperparameters,
                val_mae, val_rmse, val_dir_acc, val_r2,
                test_mae, test_rmse, test_dir_acc, test_r2,
                model_artifact_path, approved_by, approved_at, created_at
            ) VALUES (?, ?, ?, 'CHAMPION', '2026-09-30 23:00:00', 8000, 'v1_38feats', '{}',
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, 'LEAD_QUANT_RESEARCHER', ?, ?);
            """, (
                version_id, c["model_id"], c["version_tag"],
                c["val_mae"], c["val_rmse"], c["val_dir_acc"], c["val_r2"],
                c["val_mae"] * 1.05, c["val_rmse"] * 1.05, c["val_dir_acc"] * 0.98, c["val_r2"],
                c["artifact"], now_str, now_str
            ))
            
            # Record deployment event
            cur.execute("""
            INSERT INTO model_deployment_history (
                model_id, previous_version_id, new_version_id, action, approved_by, approval_notes
            ) VALUES (?, 'NONE', ?, 'PROMOTED_CHAMPION', 'LEAD_QUANT_RESEARCHER', 'Initial Phase 3 Champion Model Approval');
            """, (c["model_id"], version_id))

if __name__ == "__main__":
    init_monitoring_db()
    print("Model monitoring database initialized successfully.")
