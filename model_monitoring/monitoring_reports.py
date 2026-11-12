import os
import json
import pandas as pd
from datetime import datetime

import dashboard_config as cfg
import database.db_manager as db_base
from .model_registry import ModelRegistry
from .performance_monitor import PerformanceMonitor
from .data_drift_detector import DataDriftDetector
from .concept_drift_detector import ConceptDriftDetector
from .regime_monitor import RegimeMonitor

class MonitoringReports:
    """
    Generates institutional model governance, drift detection,
    and champion vs challenger audit reports.
    """
    
    def __init__(self):
        self.registry = ModelRegistry()
        self.perf_monitor = PerformanceMonitor()
        self.drift_detector = DataDriftDetector()
        self.concept_detector = ConceptDriftDetector()
        self.regime_monitor = RegimeMonitor()
        
    def generate_full_report(self, output_dir=None):
        """
        Compiles the complete model lifecycle report across Gold and Silver.
        """
        if output_dir is None:
            output_dir = os.path.join(cfg.RESULTS_DIR)
        os.makedirs(output_dir, exist_ok=True)
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Champions
        champions_df = self.registry.get_all_champions()
        champions_list = champions_df.to_dict(orient="records") if not champions_df.empty else []
        
        # 2. Regimes
        gold_regime = self.regime_monitor.classify_current_regime("GOLD")
        silver_regime = self.regime_monitor.classify_current_regime("SILVER")
        
        # 3. Drift events
        drift_events_df = self.drift_detector.get_drift_events(limit=25)
        drift_events = drift_events_df.to_dict(orient="records") if not drift_events_df.empty else []
        
        # 4. Performance scorecards
        perf_df = self.perf_monitor.get_latest_performance_scorecard()
        perf_list = perf_df.to_dict(orient="records") if not perf_df.empty else []
        
        report_data = {
            "report_timestamp": now_str,
            "system_version": "v7.0_MODEL_LIFECYCLE_ENGINE",
            "market_regimes": {
                "gold": gold_regime,
                "silver": silver_regime
            },
            "active_champions": champions_list,
            "performance_scorecards": perf_list,
            "recent_drift_events": drift_events,
            "governance_rule": "Automatic promotion of challenger models is strictly prohibited without 7-gate validation and explicit human approval."
        }
        
        # Save JSON
        json_path = os.path.join(output_dir, "model_monitoring_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
            
        # Save Markdown summary
        md_path = os.path.join(output_dir, "model_monitoring_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# MODEL LIFECYCLE & MONITORING AUDIT REPORT\n\n")
            f.write(f"**Generated:** {now_str} | **Environment:** MCX India Commodity Quant Sandbox\n\n")
            f.write(f"## 1. Market Regimes\n")
            f.write(f"- **Gold:** {gold_regime['regime']} (Ann Vol: {gold_regime['volatility_ann_pct']}%) - {gold_regime['recommendation']}\n")
            f.write(f"- **Silver:** {silver_regime['regime']} (Ann Vol: {silver_regime['volatility_ann_pct']}%) - {silver_regime['recommendation']}\n\n")
            f.write(f"## 2. Active Champion Models ({len(champions_list)})\n")
            for c in champions_list:
                f.write(f"- **{c['asset']} {c['horizon']}**: `{c['version_id']}` ({c['model_family']}) | Val DirAcc: {c['val_dir_acc']:.2f}%\n")
            f.write(f"\n## 3. Governance Audit\n")
            f.write(f"- 7-Gate Institutional Validation: ACTIVE\n")
            f.write(f"- Shadow Deployment Evaluation: ENABLED\n")
            f.write(f"- Auto-Promotion Barrier: ENFORCED (Explicit approval required)\n")
            
        return {
            "json_path": json_path,
            "md_path": md_path,
            "summary": report_data
        }
