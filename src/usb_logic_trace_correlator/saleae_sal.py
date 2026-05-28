from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any
import zipfile
import io


@dataclass
class SaleaeSalInfo:
    ok: bool
    message: str
    capture_start_local: str | None
    sample_rate_hz: int | None
    analyzers: list[str]
    channels: dict[str, Any]
    archive_entries: list[str]


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
            capture_start = meta.get("captureStartTime")
            try:
                dt = datetime.fromisoformat(capture_start) if capture_start else None
                capture_start_text = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if dt else None
            except ValueError:
                capture_start_text = capture_start

            analyzers_raw = meta.get("analyzers", [])
            analyzers: list[str] = []
            channels: dict[str, Any] = {}
            for item in analyzers_raw:
                label = str(item.get("type", "unknown"))
                analyzers.append(label)
                if "settings" in item:
                    channels[label] = item.get("settings", {})

            sample_rate_hz = None
            if isinstance(meta.get("sampleRate"), int):
                sample_rate_hz = int(meta["sampleRate"])

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
