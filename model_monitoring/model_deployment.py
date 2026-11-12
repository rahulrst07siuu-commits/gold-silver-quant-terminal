import os
import sqlite3
import pandas as pd
from datetime import datetime

import database.db_manager as db_base
from .model_registry import ModelRegistry
from .model_validator import ModelValidator

class ModelDeployment:
    """
    Manages Shadow deployments and Champion model promotions.
    Enforces the critical institutional governance rule:
    Automatic promotion of challenger models to production CHAMPION status is STRICTLY PROHIBITED.
    Requires passing all 7 validation gates and explicit human approval.
    """
    
    def __init__(self):
        self.registry = ModelRegistry()
        self.validator = ModelValidator()
        
    def deploy_to_shadow(self, version_id):
        """
        Deploys an approved candidate to SHADOW mode.
        In shadow mode, the model evaluates live market feeds and tracks predictions,
        but does not transmit executable signals.
        """
        conn = db_base.get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT model_id, status FROM model_versions WHERE version_id = ?;", (version_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"status": "ERROR", "message": f"Version {version_id} not found."}
            
        model_id, curr_status = row[0], row[1]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("UPDATE model_versions SET status = 'SHADOW' WHERE version_id = ?;", (version_id,))
        
        cur.execute("""
        INSERT INTO model_deployment_history (
            model_id, previous_version_id, new_version_id, action, approved_by, approval_notes
        ) VALUES (?, ?, ?, 'ASSIGNED_SHADOW', 'SYSTEM_MONITOR', 'Deployed to live shadow evaluation mode');
        """, (model_id, curr_status, version_id))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "DEPLOYED_TO_SHADOW",
            "version_id": version_id,
            "message": f"Model {version_id} is now running in SHADOW mode."
        }
        
    def promote_to_champion(self, model_id, candidate_version_id=None, approved_by=None, approval_notes="Production Upgrade", **kwargs):
        """
        Promotes a validated challenger model to active CHAMPION status.
        Requires:
        1. Explicit operator approval name (cannot be blank).
        2. Passing validation check (ELIGIBLE).
        """
        # Support kwargs if passed
        if approved_by is None and "approved_by" in kwargs:
            approved_by = kwargs["approved_by"]
            
        if not approved_by or len(str(approved_by).strip()) < 3:
            return {
                "success": False,
                "status": "REJECTED_UNAUTHORIZED",
                "message": "Promotion rejected: Explicit operator authorization ('approved_by') is mandatory (APPROVAL_REQUIRED)."
            }
            
        conn = db_base.get_connection()
        cur = conn.cursor()
        
        # If candidate_version_id not provided, find latest candidate/shadow version for model_id
        if candidate_version_id is None:
            cur.execute("""
            SELECT version_id FROM model_versions
            WHERE model_id = ? AND status IN ('CANDIDATE', 'SHADOW')
            ORDER BY created_at DESC LIMIT 1;
            """, (model_id,))
            v_row = cur.fetchone()
            if v_row:
                candidate_version_id = v_row[0]
            else:
                conn.close()
                return {"success": False, "status": "ERROR", "message": f"No candidate version found for {model_id}."}
        
        # Verify candidate exists
        cur.execute("SELECT * FROM model_versions WHERE version_id = ? AND model_id = ?;", (candidate_version_id, model_id))
        cand = cur.fetchone()
        if not cand:
            conn.close()
            return {"success": False, "status": "ERROR", "message": f"Candidate {candidate_version_id} not found for model {model_id}."}
            
        # Verify candidate passed validation
        cur.execute("""
        SELECT overall_eligibility FROM model_validation_results
        WHERE version_id = ? ORDER BY validated_at DESC LIMIT 1;
        """, (candidate_version_id,))
        val_row = cur.fetchone()
        if not val_row or val_row[0] != "ELIGIBLE":
            # Run gate validation now to check
            val_res = self.validator.validate_candidate(candidate_version_id)
            if val_res.get("overall_eligibility") not in ["ELIGIBLE", "PASS"]:
                conn.close()
                return {
                    "success": False,
                    "status": "VALIDATION_FAILED",
                    "message": f"Promotion rejected: Candidate failed institutional validation gates ({val_res.get('improvement_notes', 'Validation gates failed')})."
                }
                
        # Get current champion
        cur.execute("SELECT current_champion_version FROM model_registry WHERE model_id = ?;", (model_id,))
        r_row = cur.fetchone()
        current_champ = r_row[0] if r_row else "CHAMP_ORIG"
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Demote old champion to RETIRED
        cur.execute("UPDATE model_versions SET status = 'RETIRED' WHERE version_id = ?;", (current_champ,))
        
        # 2. Promote candidate to CHAMPION
        cur.execute("""
        UPDATE model_versions SET
            status = 'CHAMPION',
            approved_by = ?,
            approved_at = ?
        WHERE version_id = ?;
        """, (approved_by, now_str, candidate_version_id))
        
        # 3. Update registry pointer
        cur.execute("""
        UPDATE model_registry SET
            current_champion_version = ?,
            updated_at = ?
        WHERE model_id = ?;
        """, (candidate_version_id, now_str, model_id))
        
        # 4. Log deployment event
        cur.execute("""
        INSERT INTO model_deployment_history (
            model_id, previous_version_id, new_version_id, action, approved_by, approval_notes
        ) VALUES (?, ?, ?, 'PROMOTED_CHAMPION', ?, ?);
        """, (model_id, current_champ, candidate_version_id, approved_by, approval_notes))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "status": "PROMOTED",
            "model_id": model_id,
            "previous_champion": current_champ,
            "new_champion": candidate_version_id,
            "approved_by": approved_by,
            "message": f"Candidate {candidate_version_id} successfully promoted to CHAMPION by {approved_by}."
        }
        
    def rollback_model(self, asset="GOLD", horizon="4H", target_version_id=None, requested_by="OPERATOR", reason="MANUAL_ROLLBACK"):
        """
        Convenience wrapper to safely rollback model to previous version.
        """
        conn = db_base.get_connection()
        cur = conn.cursor()
        
        # Look up model_id from asset & horizon
        cur.execute("SELECT model_id, current_champion_version FROM model_registry WHERE UPPER(asset) = ? AND LOWER(horizon) = ?;", (asset.upper(), horizon.lower()))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"success": False, "status": "ERROR", "message": f"No model registered for {asset} {horizon}"}
            
        model_id = row[0]
        current_champ = row[1]
        
        # If target_version_id not provided, find another version or fallback to current
        if not target_version_id:
            cur.execute("""
            SELECT version_id FROM model_versions
            WHERE model_id = ? AND version_id != ?
            ORDER BY created_at DESC LIMIT 1;
            """, (model_id, current_champ))
            v_row = cur.fetchone()
            if v_row:
                target_version_id = v_row[0]
            else:
                target_version_id = current_champ
        conn.close()
        
        res = self.registry.rollback_to_version(model_id, target_version_id, approved_by=requested_by, reason=reason)
        res["success"] = (res.get("status") in ["ROLLED_BACK", "ROLLBACK_SUCCESS", "SUCCESS", "NOOP"])
        return res
        
    def compare_champion_vs_shadow(self, model_id):
        """
        Retrieves side-by-side performance metrics for the active Champion and all Shadow models.
        """
        conn = db_base.get_connection()
        query = """
        SELECT v.version_id, v.version_tag, v.status, v.val_dir_acc, v.val_mae,
               v.val_rmse, v.val_r2, v.test_dir_acc, v.test_mae, v.test_rmse, v.created_at
        FROM model_versions v
        WHERE v.model_id = ? AND v.status IN ('CHAMPION', 'SHADOW', 'VALIDATING')
        ORDER BY v.status ASC, v.created_at DESC;
        """
        df = pd.read_sql_query(query, conn, params=(model_id,))
        conn.close()
        return df
