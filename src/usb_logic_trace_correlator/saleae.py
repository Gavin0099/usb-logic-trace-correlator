from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import csv
import io
import re


@dataclass
class SaleaeI2CEvent:
    index: int
    time_s: float
    timestamp: datetime | None
    address: str | None
    rw: str | None
    data_hex: str
    ack: str | None
    raw_summary: str


def _find_col(columns: list[str], candidates: list[str]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for c in candidates:
        if c.lower() in lowered:
            return lowered[c.lower()]
    for col in columns:
        norm = col.lower().replace(" ", "")
        for c in candidates:
            if c.lower().replace(" ", "") in norm:
                return col
    return None


def _normalize_data_hex(text: str) -> str:
    bytes_found = re.findall(r"[0-9a-fA-F]{2}", text)
    return " ".join(b.lower() for b in bytes_found)


def parse_saleae_i2c_csv(content: str, capture_start: datetime | None = None) -> list[SaleaeI2CEvent]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return []

    time_col = _find_col(list(reader.fieldnames), ["Time [s]", "Time", "Start Time [s]"])
    addr_col = _find_col(list(reader.fieldnames), ["Address", "Addr", "Device Address"])
    rw_col = _find_col(list(reader.fieldnames), ["Read/Write", "R/W", "Direction"])
    data_col = _find_col(list(reader.fieldnames), ["Data", "Data Bytes", "Payload"])
    ack_col = _find_col(list(reader.fieldnames), ["ACK", "Ack", "Acknowledged"])

    events: list[SaleaeI2CEvent] = []
    for idx, row in enumerate(reader, start=1):
        if not time_col or row.get(time_col) in (None, ""):
            continue
        try:
            time_s = float(str(row[time_col]).strip())
        except ValueError:
            continue

        ts = capture_start + timedelta(seconds=time_s) if capture_start else None
        address = str(row.get(addr_col, "")).strip() if addr_col else None
        rw = str(row.get(rw_col, "")).strip().lower() if rw_col else None
        data_raw = str(row.get(data_col, "")).strip() if data_col else ""
        ack = str(row.get(ack_col, "")).strip() if ack_col else None

        summary = " | ".join(
            part for part in [address or "", rw or "", data_raw, ack or ""] if part
        )
        events.append(
            SaleaeI2CEvent(
                index=idx,
                time_s=time_s,
                timestamp=ts,
                address=address or None,
                rw=rw or None,
                data_hex=_normalize_data_hex(data_raw),
                ack=ack or None,
                raw_summary=summary,
            )
        )

    return events
