"""Tests for piccolo.config — config loading, defaults, and validation."""

import json

import pytest
import yaml

from piccolo.config import PiccoloConfig


class TestDefaults:
    def test_default_simulate(self):
        cfg = PiccoloConfig()
        assert cfg.simulate is True

    def test_default_port(self):
        cfg = PiccoloConfig()
        assert cfg.server_port == 8050

    def test_default_calibration(self):
        cfg = PiccoloConfig()
        assert "CH1" in cfg.calibration
        assert len(cfg.calibration) == 4
        for ch in ["CH1", "CH2", "CH3", "CH4"]:
            assert len(cfg.calibration[ch]) == 2


class TestLoadFromYaml:
    def test_load_overrides_defaults(self, tmp_path):
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml.dump({
            "simulate": False,
            "server_port": 9000,
            "buffer_size": 500,
        }))
        cfg = PiccoloConfig.load(str(yaml_path))
        assert cfg.simulate is False
        assert cfg.server_port == 9000
        assert cfg.buffer_size == 500

    def test_unknown_keys_ignored(self, tmp_path):
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml.dump({
            "simulate": True,
            "unknown_key": "should_be_ignored",
            "another_unknown": 42,
        }))
        cfg = PiccoloConfig.load(str(yaml_path))
        assert cfg.simulate is True
        assert not hasattr(cfg, "unknown_key")

    def test_missing_yaml_uses_defaults(self):
        cfg = PiccoloConfig.load("/nonexistent/path.yaml")
        assert cfg.simulate is True
        assert cfg.server_port == 8050

    def test_empty_yaml_uses_defaults(self, tmp_path):
        yaml_path = tmp_path / "empty.yaml"
        yaml_path.write_text("")
        cfg = PiccoloConfig.load(str(yaml_path))
        assert cfg.simulate is True


class TestRpLoginMerge:
    def test_rp_login_merged(self, tmp_path):
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml.dump({"simulate": False}))

        rp_path = tmp_path / "rp_login.json"
        rp_path.write_text(json.dumps({
            "ip": "192.168.1.100",
            "username": "root",
            "password": "secret",
        }))

        cfg = PiccoloConfig.load(str(yaml_path), rp_login_path=str(rp_path))
        assert cfg.rp_ip == "192.168.1.100"
        assert cfg.rp_username == "root"
        assert cfg.rp_password == "secret"

    def test_yaml_values_take_precedence_over_rp_login(self, tmp_path):
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml.dump({
            "rp_ip": "10.0.0.1",
        }))

        rp_path = tmp_path / "rp_login.json"
        rp_path.write_text(json.dumps({
            "ip": "192.168.1.100",
        }))

        cfg = PiccoloConfig.load(str(yaml_path), rp_login_path=str(rp_path))
        # YAML value should win because setdefault only sets if not already present
        assert cfg.rp_ip == "10.0.0.1"

    def test_missing_rp_login_no_error(self, tmp_path):
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml.dump({"simulate": True}))
        cfg = PiccoloConfig.load(str(yaml_path), rp_login_path="/nonexistent.json")
        assert cfg.rp_ip == ""
