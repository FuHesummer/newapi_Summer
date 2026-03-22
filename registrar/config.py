import os

DUCKMAIL_BASE_URL = os.getenv("DUCKMAIL_BASE_URL", "https://sfj.blogsummer.cn")
DUCKMAIL_API_KEY = os.getenv("DUCKMAIL_API_KEY", "dk_b3932aec8f2e4d8199f963de2091d4c3")
REGISTRATION_PROXY = os.getenv("REGISTRATION_PROXY", "")
COOLDOWN_BASE = int(os.getenv("COOLDOWN_BASE", "10"))
COOLDOWN_JITTER = int(os.getenv("COOLDOWN_JITTER", "5"))
BREAKER_FAIL_THRESHOLD = int(os.getenv("BREAKER_FAIL_THRESHOLD", "3"))
BREAKER_WINDOW_SECONDS = int(os.getenv("BREAKER_WINDOW_SECONDS", "300"))
BREAKER_OPEN_SECONDS = int(os.getenv("BREAKER_OPEN_SECONDS", "600"))

# Exa
EXA_AUTH_URL = os.getenv("EXA_AUTH_URL", "https://dashboard.exa.ai")
EXA_DASHBOARD_URL = os.getenv("EXA_DASHBOARD_URL", "https://dashboard.exa.ai")
EXA_API_BASE = os.getenv("EXA_API_BASE", "https://api.exa.ai")

# Camoufox
REGISTER_HEADLESS = os.getenv("REGISTER_HEADLESS", "true").lower() == "true"
EMAIL_CODE_TIMEOUT = int(os.getenv("EMAIL_CODE_TIMEOUT", "90"))
API_KEY_TIMEOUT = int(os.getenv("API_KEY_TIMEOUT", "20"))
