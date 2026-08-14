import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_PATH = ROOT / "config.json"


def load_config():
    cfg = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    cfg.setdefault("educoder_cookie", os.environ.get("EDUCODER_COOKIE", ""))
    cfg.setdefault("educoder_username", os.environ.get("EDUCODER_USERNAME", ""))
    cfg.setdefault("educoder_password", os.environ.get("EDUCODER_PASSWORD", ""))
    cfg.setdefault("mooc_cookie", os.environ.get("MOOC_COOKIE", ""))
    cfg.setdefault("wecom_webhook", os.environ.get("WECOM_WEBHOOK", ""))
    cfg.setdefault("serverchan_key", os.environ.get("SERVERCHAN_KEY", ""))
    cfg.setdefault("timezone", "Asia/Shanghai")
    # 平台开关：设为 false 则跳过该平台（检测 + 刷新都会跳过）
    cfg.setdefault("educoder_enabled", True)
    cfg.setdefault("mooc_enabled", True)
    return cfg
