"""
Generate GITHUB_PROJECT_INVENTORY.md
Recursively audits all files in D:\Downloads\Gold_Silver_Quant_Project,
categorizing every file into functional architectural components.
"""

import os
import time

PROJECT_DIR = r"D:\Downloads\Gold_Silver_Quant_Project"
OUTPUT_MD = r"D:\Downloads\Gold_Silver_Quant_Project\GITHUB_PROJECT_INVENTORY.md"

def scan_project():
    inventory = {
        "dashboard_pages": [],
        "python_core_and_scripts": [],
        "prediction_engine": [],
        "data_mining": [],
        "model_monitoring": [],
        "paper_trading": [],
        "market_monitor": [],
        "data_providers": [],
        "ingestion": [],
        "database": [],
        "config": [],
        "tests": [],
        "documentation": [],
        "launch_scripts": [],
        "html_and_portals": [],
        "model_artifacts": [],
        "datasets": [],
        "results_and_plots": [],
        "other": []
    }

    total_bytes = 0
    total_files = 0

    for root, dirs, files in os.walk(PROJECT_DIR):
        # Exclude pycache and zip
        if "__pycache__" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".pyc"):
                continue
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, PROJECT_DIR).replace("\\", "/")
            size = os.path.getsize(path)
            total_bytes += size
            total_files += 1

            file_info = {"path": rel_path, "size": size, "name": file}

            # Categorize
            if rel_path.startswith("dashboard_pages/"):
                inventory["dashboard_pages"].append(file_info)
            elif rel_path.startswith("prediction_engine/"):
                inventory["prediction_engine"].append(file_info)
            elif rel_path.startswith("data_mining/"):
                if "cleaned" in rel_path and rel_path.endswith(".csv"):
                    inventory["datasets"].append(file_info)
                else:
                    inventory["data_mining"].append(file_info)
            elif rel_path.startswith("model_monitoring/"):
                inventory["model_monitoring"].append(file_info)
            elif rel_path.startswith("paper_trading/"):
                inventory["paper_trading"].append(file_info)
            elif rel_path.startswith("market_monitor/"):
                inventory["market_monitor"].append(file_info)
            elif rel_path.startswith("data_providers/"):
                inventory["data_providers"].append(file_info)
            elif rel_path.startswith("ingestion/"):
                inventory["ingestion"].append(file_info)
            elif rel_path.startswith("database/"):
                inventory["database"].append(file_info)
            elif rel_path.startswith("config/"):
                inventory["config"].append(file_info)
            elif rel_path.startswith("tests/"):
                inventory["tests"].append(file_info)
            elif rel_path.startswith("models/"):
                inventory["model_artifacts"].append(file_info)
            elif rel_path.startswith("data/") or rel_path.endswith(".csv") or rel_path.endswith(".xlsx"):
                inventory["datasets"].append(file_info)
            elif rel_path.startswith("results/") or rel_path.startswith("plots/"):
                inventory["results_and_plots"].append(file_info)
            elif rel_path.endswith(".md"):
                inventory["documentation"].append(file_info)
            elif rel_path.endswith(".bat") or rel_path.endswith(".sh"):
                inventory["launch_scripts"].append(file_info)
            elif rel_path.endswith(".html"):
                inventory["html_and_portals"].append(file_info)
            elif rel_path.endswith(".py"):
                inventory["python_core_and_scripts"].append(file_info)
            else:
                inventory["other"].append(file_info)

    return inventory, total_files, total_bytes

def write_inventory_markdown(inventory, total_files, total_bytes):
    lines = []
    lines.append("# GITHUB PROJECT INVENTORY & AUDIT")
    lines.append("**Repository Target:** Private GitHub Repository")
    lines.append(f"**Audit Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Total Tracked Files:** {total_files}")
    lines.append(f"**Total Volume:** {total_bytes / (1024*1024):.2f} MB")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. EXECUTIVE COMPONENT SUMMARY")
    lines.append("")
    lines.append("| Component Category | Directory / Scope | File Count | Approximate Size |")
    lines.append("|---|---|---|---|")

    categories = [
        ("Dashboard Pages (11 Pages)", "dashboard_pages/", "dashboard_pages"),
        ("Prediction Engine", "prediction_engine/", "prediction_engine"),
        ("Data Mining & Quality", "data_mining/", "data_mining"),
        ("Model Monitoring & Drift", "model_monitoring/", "model_monitoring"),
        ("Paper Trading System", "paper_trading/", "paper_trading"),
        ("Market Monitor & Data Feed", "market_monitor/", "market_monitor"),
        ("Data Providers & Connectors", "data_providers/", "data_providers"),
        ("Data Ingestion Pipeline", "ingestion/", "ingestion"),
        ("Database & Schema", "database/", "database"),
        ("Configuration", "config/", "config"),
        ("Automated Tests", "tests/", "tests"),
        ("Core Application & Scripts", "Root (*.py)", "python_core_and_scripts"),
        ("Documentation & Reports", "*.md", "documentation"),
        ("Launch Scripts", "*.bat, *.sh", "launch_scripts"),
        ("HTML Portals & Visuals", "*.html", "html_and_portals"),
        ("Model Artifacts (Trained)", "models/", "model_artifacts"),
        ("Datasets (Historical/Clean)", "data/, data_mining/cleaned/", "datasets"),
        ("Visual Results & Plots", "results/, plots/", "results_and_plots"),
        ("Other Configurations", "Root metadata", "other")
    ]

    for label, scope, key in categories:
        items = inventory[key]
        c_size = sum(i["size"] for i in items) / (1024*1024)
        lines.append(f"| **{label}** | `{scope}` | {len(items)} | {c_size:.2f} MB |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. DETAILED MODULE BREAKDOWN")
    lines.append("")

    for label, scope, key in categories:
        items = inventory[key]
        lines.append(f"### {label} (`{scope}` — {len(items)} files)")
        lines.append("| File Path | Size (KB) |")
        lines.append("|---|---|")
        for item in sorted(items, key=lambda x: x["path"]):
            lines.append(f"| `{item['path']}` | {item['size']/1024:.1f} KB |")
        lines.append("")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Inventory written successfully to: {OUTPUT_MD}")

if __name__ == "__main__":
    inv, count, b_total = scan_project()
    write_inventory_markdown(inv, count, b_total)
