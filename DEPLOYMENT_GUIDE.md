# GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL
## ENTERPRISE DEPLOYMENT & INFRASTRUCTURE GUIDE

**Document Version:** 1.0 (Production Hardened)  
**Target Environments:** Local Windows Workstation | Linux Cloud Server | Containerized Docker  
**Database Engine:** SQLite 3 with Write-Ahead Logging (WAL)  
**Security Boundary:** Simulation-Only Execution Sandbox  

---

## 1. Local Workstation Deployment (Windows 10/11)

### 1.1 Prerequisites
- **Operating System:** Windows 10/11 64-bit
- **Python:** Python 3.10, 3.11, or 3.12 (64-bit) with `pip`
- **RAM:** Minimum 8 GB (16 GB recommended for multi-model ensembles)
- **Disk Space:** 5 GB free disk space

### 1.2 Installation Steps
1. Clone or copy project to target folder:
   ```cmd
   cd D:\Downloads\Gold_Silver_Quant_Project
   ```
2. Verify Python environment:
   ```cmd
   python --version
   ```
3. Install dependencies:
   ```cmd
   python -m pip install -r requirements.txt
   ```
4. Verify database initialization:
   ```cmd
   python -c "import database.db_manager as db; db.init_db(); print('DB Initialized OK')"
   ```
5. Test platform execution:
   ```cmd
   python -m unittest tests/test_phase8_production_hardening.py
   ```

### 1.3 Running via Batch Launchers
- **Launch:** Double-click `START_GOLD_SILVER_TERMINAL.bat`
- **Shutdown:** Double-click `STOP_GOLD_SILVER_TERMINAL.bat`

---

## 2. Cloud Server Deployment (Ubuntu / Debian Linux VM)

### 2.1 Server Provisioning
Recommended Virtual Machine Specs:
- **Cloud Providers:** Google Cloud Platform (Compute Engine e2-standard-4), AWS (t3.xlarge), or Azure (Standard_D4s_v5)
- **OS:** Ubuntu 22.04 LTS x86_64
- **Network:** Ingress TCP port 8501 (restricted by corporate VPN or IP whitelist)

### 2.2 Server Installation
```bash
# 1. Update OS packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git sqlite3 libsqlite3-dev

# 2. Setup project folder
sudo mkdir -p /opt/gold_silver_quant
sudo chown -R $USER:$USER /opt/gold_silver_quant
cd /opt/gold_silver_quant

# 3. Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Initialize database
python -c "import database.db_manager as db; db.init_db()"
```

### 2.3 Systemd Service Configuration
Create systemd service file at `/etc/systemd/system/gold-silver-terminal.service`:

```ini
[Unit]
Description=Gold & Silver Quantitative Intelligence Terminal
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/gold_silver_quant
Environment="PATH=/opt/gold_silver_quant/venv/bin:/usr/bin"
Environment="STREAMLIT_SERVER_PORT=8501"
Environment="STREAMLIT_SERVER_HEADLESS=true"
Environment="STREAMLIT_SERVER_ADDRESS=0.0.0.0"
ExecStart=/opt/gold_silver_quant/venv/bin/python -m streamlit run app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gold-silver-terminal
sudo systemctl start gold-silver-terminal
sudo systemctl status gold-silver-terminal
```

---

## 3. Docker Container Deployment

### 3.1 Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit port
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 3.2 Build and Run
```bash
docker build -t gold-silver-terminal:v8.0 .
docker run -d -p 8501:8501 -v $(pwd)/database:/app/database --name quant-terminal gold-silver-terminal:v8.0
```

---

## 4. Database Resilience & Backup Strategy

### 4.1 SQLite WAL Concurrency
The system utilizes SQLite with Write-Ahead Logging (`WAL` mode). This allows concurrent reads while writes are being processed, eliminating lock contention between background data ingestion and user dashboard queries.

### 4.2 Automated Online Backups
The platform includes an automated online backup utility that uses SQLite's non-blocking C-level backup API:
```python
from database.backup_manager import create_backup
res = create_backup()
print(f"Backup created: {res['backup_path']} ({res['size_kb']} KB)")
```
Backups are saved to `database/backups/mcx_market_data_backup_YYYYMMDD_HHMMSS.db`.

### 4.3 Automated Cron / Task Scheduler Setup
- **Linux Crontab (Daily Backup at 00:00 UTC):**
  ```cron
  0 0 * * * /opt/gold_silver_quant/venv/bin/python -c "import database.backup_manager as bm; bm.create_backup()" >> /opt/gold_silver_quant/logs/backup.log 2>&1
  ```
- **Windows Task Scheduler:**
  Create a scheduled task executing `python -c "import database.backup_manager as bm; bm.create_backup()"` daily.

---

## 5. Security & Isolation Policies

1. **Credential Segregation:**
   - Always copy `.env.example` to `.env` and assign restricted file permissions (`chmod 600 .env`).
   - Never commit `.env` or database files to source control.
2. **Reverse Proxy & SSL/TLS:**
   - For web deployments, place the terminal behind NGINX or Caddy configured with Let's Encrypt SSL/TLS certificates and HTTP Basic Authentication or OAuth2 proxy.
3. **Strict Order Execution Boundary:**
   - Under no circumstances should order routing modules connect to live broker trade execution endpoints. The platform is designed strictly as a simulation and research sandbox.
