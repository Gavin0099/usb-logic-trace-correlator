from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import csv
import io
import re
from typing import Iterable


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


@dataclass
class SaleaeCsvClassification:
    csv_kind: str          # i2c_analyzer_csv | digital_export_csv | unknown_time_series_csv | invalid_csv
    valid_for_correlation: bool
    confidence: str        # high | medium | low
    detected_columns: list[str] = field(default_factory=list)
    missing_i2c_columns: list[str] = field(default_factory=list)
    reason: str = ""
    sample_address_values: list[str] = field(default_factory=list)


# ── I2C address heuristic (valid 7-bit: 0x00..0x7F) ──────────────────────────
_HEX_ADDR_RE = re.compile(r"^0?[xX]?([0-9a-fA-F]{1,2})$")


def _looks_like_i2c_address(values: list[str]) -> bool:
    valid = 0
    for v in values:
        m = _HEX_ADDR_RE.match(v.strip())
        if m:
            n = int(m.group(1), 16)
            if n <= 0x7F:
                valid += 1
    return valid >= max(1, len(values) // 2)


def classify_saleae_csv(content: str | Iterable[str]) -> SaleaeCsvClassification:
    """
    Inspect the CSV headers (and a few rows) to determine whether it is a
    genuine Saleae I2C Analyzer export or something else (e.g. digital export).

    Returns a SaleaeCsvClassification.  Only csv_kind == 'i2c_analyzer_csv'
    should be used as a correlation source.
    """
    reader = csv.DictReader(_as_text_reader(content))
    if not reader.fieldnames:
        return SaleaeCsvClassification(
            csv_kind="invalid_csv",
            valid_for_correlation=False,
            confidence="high",
            reason="CSV has no headers or is empty",
        )

    cols = list(reader.fieldnames)
    detected = cols[:]

    time_col = _find_col(cols, ["Time [s]", "Time", "Start Time [s]"])
    addr_col = _find_col(cols, ["Address", "Addr", "Device Address"])
    rw_col   = _find_col(cols, ["Read/Write", "R/W", "Direction"])
    data_col = _find_col(cols, ["Data", "Data Bytes", "Payload"])
    ack_col  = _find_col(cols, ["ACK", "Ack", "Acknowledged"])
    sum_col  = _find_col(cols, ["Summary", "Description", "Info"])

    # ── Must have Time ────────────────────────────────────────────────────────
    if time_col is None:
        return SaleaeCsvClassification(
            csv_kind="invalid_csv",
            valid_for_correlation=False,
            confidence="high",
            detected_columns=detected,
            missing_i2c_columns=["Time"],
            reason="No Time column found",
        )

    # ── Score I2C semantic evidence ───────────────────────────────────────────
    i2c_cols_present = [c for c in [addr_col, rw_col, data_col, ack_col, sum_col] if c]
    missing = [
        name for name, col in [("Address", addr_col), ("Data", data_col), ("Summary", sum_col)]
        if col is None
    ]

    if not i2c_cols_present:
        return SaleaeCsvClassification(
            csv_kind="digital_export_csv",
            valid_for_correlation=False,
            confidence="high",
            detected_columns=detected,
            missing_i2c_columns=missing,
            reason="No I2C semantic columns (Address/Data/ACK/Summary) found — looks like a digital channel export",
        )

    # ── Sample first 200 rows to check data quality ───────────────────────────
    sample_addrs: list[str] = []
    has_data_rows = False
    for _, row in zip(range(200), reader):
        has_data_rows = True
        if addr_col and row.get(addr_col, "").strip():
            sample_addrs.append(row[addr_col].strip())

    if not has_data_rows:
        return SaleaeCsvClassification(
            csv_kind="invalid_csv",
            valid_for_correlation=False,
            confidence="high",
            detected_columns=detected,
            reason="CSV has headers but no data rows",
        )

    # ── Validate address values ───────────────────────────────────────────────
    if addr_col and sample_addrs:
        addr_ok = _looks_like_i2c_address(sample_addrs[:50])
        if not addr_ok:
            return SaleaeCsvClassification(
                csv_kind="digital_export_csv",
                valid_for_correlation=False,
                confidence="medium",
                detected_columns=detected,
                missing_i2c_columns=missing,
                sample_address_values=sample_addrs[:5],
                reason=f"Address column found but values don't look like I2C 7-bit addresses: {sample_addrs[:3]}",
            )

    # ── Looks like a valid I2C Analyzer CSV ──────────────────────────────────
    confidence = "high" if (addr_col and data_col) or sum_col else "medium"
    return SaleaeCsvClassification(
        csv_kind="i2c_analyzer_csv",
        valid_for_correlation=True,
        confidence=confidence,
        detected_columns=detected,
        missing_i2c_columns=missing,
        sample_address_values=sample_addrs[:5],
        reason="Time + I2C semantic columns detected" + ("" if confidence == "high" else " (partial; some columns missing)"),
    )


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


def _as_text_reader(content: str | Iterable[str]):
    if isinstance(content, str):
        return io.StringIO(content)
    return content


def parse_saleae_i2c_csv(
    content: str | Iterable[str],
    capture_start: datetime | None = None,
    max_events: int | None = None,
) -> list[SaleaeI2CEvent]:
    reader = csv.DictReader(_as_text_reader(content))
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
        if max_events is not None and len(events) >= max_events:
            break

    return events
