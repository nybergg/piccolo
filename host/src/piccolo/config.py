import json
import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class PiccoloConfig:
    # Mode
    simulate: bool = True
    launch_rp: bool = True
    camera_enabled: bool = True

    # Red Pitaya
    rp_ip: str = ""
    rp_username: str = "root"
    rp_password: str = ""
    rp_dir: str = "piccolo_testing"
    rp_script: str = "piccolo_rp.py"

    # Data
    buffer_size: int = 1000
    adc_samples: int = 4096

    # Calibration
    calibration: dict = field(default_factory=lambda: {
        "CH1": [-10, 1.0],
        "CH2": [-10, 1.0],
        "CH3": [-10, 1.0],
        "CH4": [-10, 1.0],
    })

    # UI
    server_url: str = "http://127.0.0.1:8050/"
    server_port: int = 8050
    update_interval_ms: int = 250
    counter_interval_ms: int = 1000

    # Laser config (loaded separately)
    laser_config_path: Optional[str] = None

    @classmethod
    def load(cls, yaml_path: str, rp_login_path: Optional[str] = None) -> "PiccoloConfig":
        """Load config from a YAML file, optionally merging RP login credentials."""
        config_data = {}

        if os.path.exists(yaml_path):
            with open(yaml_path, "r") as f:
                config_data = yaml.safe_load(f) or {}

        # Load RP login credentials if provided
        if rp_login_path:
            if not os.path.exists(rp_login_path):
                raise FileNotFoundError(
                    f"RP login file not found: {rp_login_path}\n"
                    f"  (resolved to: {os.path.abspath(rp_login_path)})\n"
                    f"  Hint: if running from host/, try --rp-login ../config/rp_login.json"
                )
            with open(rp_login_path, "r") as f:
                rp_login = json.load(f)
            config_data["rp_ip"] = rp_login.get("ip", "")
            config_data["rp_username"] = rp_login.get("username", "root")
            config_data["rp_password"] = rp_login.get("password", "")

        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in config_data.items() if k in known_fields}

        return cls(**filtered)
