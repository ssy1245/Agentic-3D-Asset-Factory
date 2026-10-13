"""Fail-closed runtime mode and vendor call boundary."""
import os


def load_test_enabled():
    value = os.getenv("STUDIO_LOAD_TEST", "0")
    if value not in ("0", "1"):
        raise ValueError("STUDIO_LOAD_TEST must be exactly 0 or 1")
    return value == "1"


def require_real_calls():
    if load_test_enabled():
        raise RuntimeError("压测模式禁止真实供应商 API 调用。")
