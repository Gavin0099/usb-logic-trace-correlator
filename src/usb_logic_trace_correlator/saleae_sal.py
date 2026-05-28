from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any
import zipfile
import io


def _to_local_timestamp_text(capture_start: Any) -> str | None:
    if capture_start is None:
        return None

    if isinstance(capture_start, str):
        try:
            dt = datetime.fromisoformat(capture_start)
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except ValueError:
            return capture_start

    if isinstance(capture_start, dict):
        ms = capture_start.get("unixTimeMilliseconds")
        frac_ms = capture_start.get("fractionalMilliseconds", 0)
        if isinstance(ms, (int, float)):
            try:
                epoch_s = float(ms) / 1000.0 + float(frac_ms) / 1000.0
                dt = datetime.fromtimestamp(epoch_s)
                return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            except (ValueError, OSError):
                return None

    return None


def _extract_sample_rate_hz(meta_payload: dict[str, Any], bin_data: Any) -> int | None:
    # Newer exports may keep sample rate under captureSettings; older may use top-level fields.
    candidates = [
        meta_payload.get("sampleRate"),
        (meta_payload.get("captureSettings") or {}).get("sampleRate"),
        (meta_payload.get("captureSettings") or {}).get("sampleRateHz"),
    ]

    if isinstance(bin_data, list):
        for item in bin_data:
            if isinstance(item, dict):
                candidates.extend([item.get("sampleRate"), item.get("sampleRateHz")])
    elif isinstance(bin_data, dict):
        candidates.extend([bin_data.get("sampleRate"), bin_data.get("sampleRateHz")])

    for value in candidates:
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return int(value)
    return None


def _normalize_analyzer_settings(settings: Any) -> list[dict[str, Any]]:
    if not isinstance(settings, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in settings:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        setting = item.get("setting") or {}
        value = setting.get("value") if isinstance(setting, dict) else None
        normalized.append({"title": title, "value": value})
    return normalized


@dataclass
class SaleaeSalInfo:
    ok: bool
    message: str
    capture_start_local: str | None
    sample_rate_hz: int | None
    analyzers: list[str]
    channels: dict[str, Any]
    archive_entries: list[str]


def extract_i2c_csv_from_sal_bytes(data: bytes) -> str | None:
    """Best-effort extraction of analyzer CSV-like content from .sal archives.

    Most Saleae .sal captures do not contain analyzer export CSV by default,
    but some workflows may bundle additional text/CSV files.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            for name in zf.namelist():
                lower = name.lower()
                if not (lower.endswith(".csv") or lower.endswith(".txt")):
                    continue
                if "i2c" not in lower and "analyzer" not in lower and "export" not in lower:
                    continue

                text = zf.read(name).decode("utf-8", errors="replace")
                header = text.splitlines()[0].lower() if text.splitlines() else ""
                if "time" in header and ("address" in header or "data" in header):
                    return text
    except zipfile.BadZipFile:
        return None

    return None


def inspect_sal_bytes(data: bytes) -> SaleaeSalInfo:
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            entries = zf.namelist()
            if "meta.json" not in entries:
                return SaleaeSalInfo(
                    ok=False,
                    message=".sal 中找不到 meta.json，無法判定 analyzer 設定。",
                    capture_start_local=None,
                    sample_rate_hz=None,
                    analyzers=[],
                    channels={},
                    archive_entries=entries,
                )

            meta = json.loads(zf.read("meta.json").decode("utf-8", errors="replace"))
            meta_payload = meta.get("data") if isinstance(meta.get("data"), dict) else meta
            capture_start_text = _to_local_timestamp_text(meta_payload.get("captureStartTime"))

            analyzers_raw = meta_payload.get("analyzers", [])
            analyzers: list[str] = []
            channels: dict[str, Any] = {}
            for item in analyzers_raw:
                label = str(item.get("type", "unknown"))
                analyzers.append(label)
                if "settings" in item:
                    channels[label] = _normalize_analyzer_settings(item.get("settings"))

            sample_rate_hz = _extract_sample_rate_hz(meta_payload, meta.get("binData"))

            return SaleaeSalInfo(
                ok=True,
                message="已讀取 .sal metadata；正式比對仍需 Saleae 匯出的 Analyzer CSV。",
                capture_start_local=capture_start_text,
                sample_rate_hz=sample_rate_hz,
                analyzers=analyzers,
                channels=channels,
                archive_entries=entries,
            )
    except zipfile.BadZipFile:
        return SaleaeSalInfo(
            ok=False,
            message="檔案不是合法的 .sal/.zip 格式。",
            capture_start_local=None,
            sample_rate_hz=None,
            analyzers=[],
            channels={},
            archive_entries=[],
        )
