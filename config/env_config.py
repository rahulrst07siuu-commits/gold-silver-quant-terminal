import os

def load_env_file(filepath=None):
    if filepath is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, ".env")
        
    if not os.path.exists(filepath):
        return {}
        
    env_vars = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            env_vars[k] = v
            os.environ[k] = v
    return env_vars

# Load on import
_env = load_env_file()

def get_config(key, default=""):
    return os.environ.get(key, default)

# Primary Configuration Defaults
MARKET_DATA_PROVIDER = get_config("MARKET_DATA_PROVIDER", "FALLBACK_MOCK")

# DhanHQ Credentials
DHAN_CLIENT_ID = get_config("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = get_config("DHAN_ACCESS_TOKEN", "")

# Zerodha Kite Credentials
KITE_API_KEY = get_config("KITE_API_KEY", "")
KITE_ACCESS_TOKEN = get_config("KITE_ACCESS_TOKEN", "")

# Database Config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = get_config("DB_PATH", os.path.join(BASE_DIR, "database", "mcx_market_data.db"))
