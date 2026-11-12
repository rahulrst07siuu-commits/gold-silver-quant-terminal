import os
import sqlite3
import pandas as pd
from datetime import datetime, time

import database.db_manager as db_base
from .challenger_trainer import ChallengerTrainer
from .model_validator import ModelValidator
from .model_deployment import ModelDeployment

class RetrainingScheduler:
    """
    Controlled adaptive retraining scheduler.
    Orchestrates candidate model retraining upon manual request, scheduled evaluation,
    or drift/performance degradation triggers.
    Enforces pre-flight ingestion safety checks and duplicate job prevention.
    """
    
    def __init__(self):
        self.trainer = ChallengerTrainer()
        self.validator = ModelValidator()
        self.deployment = ModelDeployment()
        
    def is_safe_to_retrain(self):
        """
        Safety pre-flight check:
        Avoid retraining during market opening burst (09:00 - 09:15 IST)
        when market data ingestion and live tick spikes occur.
        """
        now_time = datetime.now().time()
        # Ingestion burst window: 09:00 to 09:15
        if time(9, 0) <= now_time <= time(9, 15):
            return False, "Retraining blocked during morning market opening ingestion window (09:00 - 09:15 IST)."
        return True, "Safe to execute training pipeline."
        
    def has_running_job(self, asset, horizon):
        """
        Prevents duplicate concurrent training jobs for the same asset and horizon.
        """
        conn = db_base.get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT COUNT(*) FROM model_training_jobs
        WHERE asset = ? AND horizon = ? AND status = 'RUNNING';
        """, (asset.upper(), horizon.lower()))
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
        
    def trigger_retraining(self, asset="GOLD", horizon="4h", model_family="ExtraTrees", trigger_type="MANUAL"):
        """
        Executes controlled candidate retraining with full governance:
        1. Pre-flight safety check
        2. Duplicate job check
        3. Train challenger model
        4. Run 7-gate validation
        5. If eligible, automatically deploy to SHADOW mode (Never Champion!)
        """
        safe, msg = self.is_safe_to_retrain()
        if not safe and trigger_type != "MANUAL":
            return {"status": "BLOCKED", "message": msg}
            
        if self.has_running_job(asset, horizon):
            return {"status": "BLOCKED", "message": f"A training job is already active for {asset} {horizon}."}
            
        # 1. Train candidate
        train_res = self.trainer.train_challenger(
            asset=asset, horizon=horizon, model_family=model_family, trigger_type=trigger_type
        )
        
        if train_res["status"] != "COMPLETED":
            return train_res
            
        candidate_version_id = train_res["version_id"]
        
        # 2. Execute 7-gate validation
        val_res = self.validator.validate_candidate(candidate_version_id)
        
        # 3. If eligible, deploy to SHADOW mode
        shadow_res = None
        if val_res["overall_eligibility"] == "ELIGIBLE":
            shadow_res = self.deployment.deploy_to_shadow(candidate_version_id)
            
        return {
            "status": "COMPLETED",
            "asset": asset.upper(),
            "horizon": horizon.lower(),
            "candidate_version_id": candidate_version_id,
            "training_result": train_res,
            "validation_result": val_res,
            "shadow_deployment": shadow_res,
            "message": (
                f"Candidate {candidate_version_id} trained and validated ({val_res['overall_eligibility']}). "
                f"{'Deployed to SHADOW mode for live observation. Awaiting human operator approval for Champion promotion.' if val_res['overall_eligibility'] == 'ELIGIBLE' else 'Candidate rejected: failed validation gates.'}"
            )
        }
        
    def get_training_jobs(self, limit=25):
        conn = db_base.get_connection()
        query = "SELECT * FROM model_training_jobs ORDER BY start_time DESC LIMIT ?;"
        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        return df
