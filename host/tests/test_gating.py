"""Tests for gating statistics on InstrumentController.

Exercises the droplet_classification bit-15 (droplet_positive) parsing and the
windowed gated-fraction computation. No hardware involved.
"""

import pandas as pd

from piccolo.controllers.controller import InstrumentController


class _StubController(InstrumentController):
    """Minimal concrete controller exposing a settable droplet_data buffer."""

    def __init__(self, df):
        self.droplet_data = df

    # Abstract methods — unused by the gating stats.
    def set_memory_variable(self, name, value): ...
    def start(self): ...
    def stop(self): ...
    def set_laser_on_state(self, name, state): ...
    def set_laser_power(self, name, power_mw): ...


# droplet_classification arrives as a binary string (bool dtype). Bit 15 is the
# gated/droplet_positive flag; bit 14 is sort_trig.
GATED = bin(0x8000)[2:]            # bit15 set                -> gated
GATED_AND_SORTED = bin(0xC000)[2:]  # bit15 + bit14 set        -> gated
SORT_ONLY = bin(0x4000)[2:]         # bit14 only (not gated)   -> not gated
NOT_GATED = bin(0x0)[2:]            # nothing set              -> not gated


def test_bit15_parsing_string_and_int():
    assert InstrumentController._droplet_is_gated(GATED) is True
    assert InstrumentController._droplet_is_gated(GATED_AND_SORTED) is True
    assert InstrumentController._droplet_is_gated(SORT_ONLY) is False
    assert InstrumentController._droplet_is_gated(NOT_GATED) is False
    # int form (some code paths may hand back an int)
    assert InstrumentController._droplet_is_gated(0x8000) is True
    assert InstrumentController._droplet_is_gated(0) is False
    # malformed / missing
    assert InstrumentController._droplet_is_gated(None) is False
    assert InstrumentController._droplet_is_gated("not binary") is False


def test_gating_stats_percentage():
    df = pd.DataFrame({"droplet_classification": [GATED, GATED, NOT_GATED, SORT_ONLY]})
    stats = _StubController(df).get_gating_stats()
    assert stats == {"total": 4, "gated": 2, "percent": 50.0}


def test_gating_stats_empty_buffer():
    stats = _StubController(pd.DataFrame()).get_gating_stats()
    assert stats == {"total": 0, "gated": 0, "percent": None}


def test_gating_stats_no_classification_column():
    # e.g. simulator buffer, which has no droplet_classification field
    df = pd.DataFrame({"cur_droplet_intensity[0]": [1, 2, 3]})
    stats = _StubController(df).get_gating_stats()
    assert stats == {"total": 3, "gated": 0, "percent": None}
