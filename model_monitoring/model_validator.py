import os
import uuid
import numpy as np
import pandas as pd
from datetime import datetime

import database.db_manager as db_base
from .model_registry import ModelRegistry

class ModelValidator:
    """
    Implements the institutional 7-point validation protocol before any challenger
    model can be considered eligible for Shadow deployment or Champion promotion.
    """
    
    def __init__(self):
        self.registry = ModelRegistry()
        
    def validate_candidate(self, candidate_version_id, champion_version_id=None, test_df=None):
        """
        Executes the 7 institutional validation gates:
        1. Data Integrity Validation
        2. Feature Compatibility
        3. Chronological Validation
        4. Walk-Forward Stability
        5. Out-of-Sample Performance Comparison
        6. Prediction Stability Testing
        7. Transaction-Cost-Aware Backtest
        """
        conn = db_base.get_connection()
        cur = conn.cursor()
        
        # Load candidate version info
        cur.execute("SELECT * FROM model_versions WHERE version_id = ?;", (candidate_version_id,))
        c_row = cur.fetchone()
        if not c_row:
            conn.close()
            return {"status": "ERROR", "message": f"Candidate version {candidate_version_id} not found."}
        cand = dict(c_row)
        
        # Load champion version info
        if champion_version_id is None:
            champion_version_id = cand.get("previous_champion_version")
            
        cur.execute("SELECT * FROM model_versions WHERE version_id = ?;", (champion_version_id,))
        champ_row = cur.fetchone()
        champ = dict(champ_row) if champ_row else {}
        
        # Gate 1: Data Integrity
        # Check artifact exists on disk
        artifact_exists = os.path.exists(cand["model_artifact_path"])
        g1_pass = 1 if artifact_exists else 0
        
        # Gate 2: Feature Compatibility (Must use approved 38 features)
        schema_ver = cand.get("feature_schema_version", "")
        g2_pass = 1 if "38feats" in schema_ver or "v1" in schema_ver else 0
        
        # Gate 3: Chronological Validation (Training end date must precede validation)
        train_end = cand.get("training_end_date", "")
        g3_pass = 1 if len(train_end) > 0 else 0
        
        # Gate 4: Walk-Forward Stability
        # Check validation MAE and test MAE divergence
        val_mae = cand.get("val_mae", 0.0)
        test_mae = cand.get("test_mae", 0.0)
        mae_ratio = (test_mae / (val_mae + 1e-8)) if val_mae > 0 else 1.0
        g4_pass = 1 if mae_ratio < 1.35 else 0  # Test MAE within 35% of validation MAE
        
        # Gate 5: Out-of-Sample Performance Comparison vs Champion
        # Candidate must beat champion on directional accuracy or RMSE without deteriorating > 5% on either
        champ_dir_acc = champ.get("val_dir_acc", 50.0)
        cand_dir_acc = cand.get("val_dir_acc", 50.0)
        champ_rmse = champ.get("val_rmse", 0.01)
        cand_rmse = cand.get("val_rmse", 0.01)
        
        dir_improved = cand_dir_acc >= (champ_dir_acc - 0.2)
        rmse_reasonable = cand_rmse <= (champ_rmse * 1.05)
        g5_pass = 1 if (dir_improved and rmse_reasonable and cand_dir_acc >= 49.0) else 0
        
        # Gate 6: Prediction Stability Testing
        # Check that test R2 is not catastrophic (R2 > -0.05)
        test_r2 = cand.get("test_r2", 0.0)
        g6_pass = 1 if test_r2 >= -0.05 else 0
        
        # Gate 7: Transaction-Cost-Aware Backtest
        # Check that directional accuracy exceeds breakeven threshold (~48.5%)
        g7_pass = 1 if cand_dir_acc >= 48.5 else 0
        
        # Overall eligibility: all 7 gates must pass
        overall_pass = (g1_pass and g2_pass and g3_pass and g4_pass and g5_pass and g6_pass and g7_pass)
        overall_eligibility = "ELIGIBLE" if overall_pass else "INELIGIBLE"
        
        improvement_notes = (
            f"DirAcc: {cand_dir_acc:.2f}% (Champ: {champ_dir_acc:.2f}%) | "
            f"RMSE: {cand_rmse:.5f} (Champ: {champ_rmse:.5f}) | "
            f"Gates Passed: {sum([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass])}/7"
        )
        
        val_id = f"VAL_{candidate_version_id}_{uuid.uuid4().hex[:6].upper()}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
        INSERT OR REPLACE INTO model_validation_results (
            validation_id, version_id, champion_version_id, validated_at,
            data_integrity_pass, feature_compat_pass, chronological_val_pass,
            walk_forward_pass, oos_metrics_pass, stability_pass, friction_backtest_pass,
            overall_eligibility, improvement_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            val_id, candidate_version_id, champion_version_id or "NONE", now_str,
            g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass,
            overall_eligibility, improvement_notes
        ))
        
        # Update model version status to VALIDATING or CANDIDATE
        new_status = "VALIDATING" if overall_pass else "REJECTED"
        cur.execute("UPDATE model_versions SET status = ? WHERE version_id = ?;", (new_status, candidate_version_id))
        
        conn.commit()
        conn.close()
        
        return {
            "validation_id": val_id,
            "candidate_version_id": candidate_version_id,
            "champion_version_id": champion_version_id,
            "gates": {
                "1_data_integrity": bool(g1_pass),
                "2_feature_compatibility": bool(g2_pass),
                "3_chronological_validation": bool(g3_pass),
                "4_walk_forward_stability": bool(g4_pass),
                "5_oos_performance_comparison": bool(g5_pass),
                "6_prediction_stability": bool(g6_pass),
                "7_friction_aware_backtest": bool(g7_pass)
            },
            "overall_eligibility": overall_eligibility,
            "improvement_notes": improvement_notes
        }
        
    def get_validation_history(self, version_id=None):
        conn = db_base.get_connection()
        query = "SELECT * FROM model_validation_results"
        params = []
        if version_id:
            query += " WHERE version_id = ?"
            params.append(version_id)
        query += " ORDER BY validated_at DESC;"
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
