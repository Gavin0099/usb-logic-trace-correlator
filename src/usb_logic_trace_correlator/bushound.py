from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Iterable


PHASES = {"CTL", "IN", "OUT", "USTS"}


@dataclass
class BusHoundEvent:
    device: str
    length: int | None
    phase: str
    data: str
    description: str
    delta_us: int | None
    cmd: str
    timestamp: datetime
    raw_line: str


@dataclass
class UsbTransaction:
    txn_id: int
    device: str
    timestamp: datetime
    bm_request_type: str
    b_request: str
    w_value: str
    w_index: str
    w_length: str
    data_direction: str | None
    payload_hex: str
    status: str
    note: str
    delta_from_prev_ms: float | None
    raw_events: list[BusHoundEvent]


def _parse_delta_to_us(delta: str) -> int | None:
    text = delta.strip().lower()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(us|ms|s)", text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "us":
        return int(value)
    if unit == "ms":
        return int(value * 1000)
    return int(value * 1_000_000)


def _parse_ctl_setup(data: str) -> tuple[str, str, str, str, str] | None:
    normalized = " ".join(data.strip().split())
    match = re.fullmatch(r"([0-9a-fA-F]{2})\s+([0-9a-fA-F]{2})\s+([0-9a-fA-F]{4})\s+([0-9a-fA-F]{4})\s+([0-9a-fA-F]{4})", normalized)
    if not match:
        return None
    return (
        match.group(1).lower(),
        match.group(2).lower(),
        match.group(3).lower(),
        match.group(4).lower(),
        match.group(5).lower(),
    )


def _iter_text_lines(content: str | Iterable[str]) -> Iterable[str]:
    if isinstance(content, str):
        yield from content.splitlines()
        return
    yield from content


def parse_bushound_txt(content: str | Iterable[str], max_events: int | None = None) -> list[BusHoundEvent]:
    events: list[BusHoundEvent] = []
    for raw_line in _iter_text_lines(content):
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("Bus Hound") or line.startswith("  Device") or line.startswith("------"):
            continue

        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 8:
            continue

        if len(parts) >= 8 and parts[1] in PHASES:
            device = parts[0]
            length = None
            phase = parts[1]
            data, desc, delta, cmd, date_text, time_text = parts[2:8]
        elif len(parts) >= 9 and parts[2] in PHASES:
            device = parts[0]
            length = int(parts[1]) if parts[1].isdigit() else None
            phase = parts[2]
            data, desc, delta, cmd, date_text, time_text = parts[3:9]
        else:
            continue

        try:
            ts = datetime.fromisoformat(f"{date_text}T{time_text}")
        except ValueError:
            continue

        events.append(
            BusHoundEvent(
                device=device,
                length=length,
                phase=phase,
                data=data.strip(),
                description=desc.strip(),
                delta_us=_parse_delta_to_us(delta),
                cmd=cmd.strip(),
                timestamp=ts,
                raw_line=line,
            )
        )
        if max_events is not None and len(events) >= max_events:
            break

    return events


def group_usb_transactions(events: Iterable[BusHoundEvent]) -> list[UsbTransaction]:
    txns: list[UsbTransaction] = []
    current: dict | None = None
    txn_id = 1

    def flush_current() -> None:
        nonlocal current, txn_id
        if not current:
            return
        txns.append(
            UsbTransaction(
                txn_id=txn_id,
                device=current["device"],
                timestamp=current["timestamp"],
                bm_request_type=current["setup"][0],
                b_request=current["setup"][1],
                w_value=current["setup"][2],
                w_index=current["setup"][3],
                w_length=current["setup"][4],
                data_direction=current["data_direction"],
                payload_hex=" ".join(current["payload"]).strip(),
                status=current["status"],
                note=current["note"],
                delta_from_prev_ms=None,
                raw_events=list(current["raw_events"]),
            )
        )
        txn_id += 1
        current = None

    for ev in events:
        if ev.phase == "CTL":
            setup = _parse_ctl_setup(ev.data)
            flush_current()
            if not setup:
                continue
            direction = "IN" if int(setup[0], 16) & 0x80 else "OUT"
            current = {
                "device": ev.device,
                "timestamp": ev.timestamp,
                "setup": setup,
                "data_direction": direction,
                "payload": [],
                "status": "ok",
                "note": "",
                "raw_events": [ev],
            }
            continue

        if not current or ev.device != current["device"]:
            continue

        current["raw_events"].append(ev)

        if ev.phase in {"IN", "OUT"}:
            if re.fullmatch(r"[0-9a-fA-F ]+", ev.data):
                current["payload"].append(" ".join(ev.data.split()).lower())
        elif ev.phase == "USTS":
            desc = ev.description.lower()
            if "stall" in desc:
                current["status"] = "stall"
                current["note"] = ev.description.strip()
            elif "cancel" in desc:
                current["status"] = "canceled"
                current["note"] = ev.description.strip()
            else:
                current["status"] = desc or "status"
                current["note"] = ev.description.strip()

    flush_current()

    prev_ts: datetime | None = None
    for txn in txns:
        if prev_ts is None:
            txn.delta_from_prev_ms = None
        else:
            txn.delta_from_prev_ms = (txn.timestamp - prev_ts).total_seconds() * 1000.0
        prev_ts = txn.timestamp

    return txns
