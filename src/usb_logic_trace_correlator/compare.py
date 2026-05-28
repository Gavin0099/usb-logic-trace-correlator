from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .bushound import UsbTransaction
from .saleae import SaleaeI2CEvent


@dataclass
class MatchResult:
    usb_txn_id: int
    usb_time: datetime
    matched_i2c_count: int
    first_i2c_time: datetime | None
    last_i2c_time: datetime | None
    status: str


def compare_usb_vs_i2c(
    usb_txns: list[UsbTransaction],
    i2c_events: list[SaleaeI2CEvent],
    window_ms: int = 20,
    i2c_time_shift_ms: int = 0,
) -> tuple[list[MatchResult], list[SaleaeI2CEvent]]:
    window_s = window_ms / 1000.0
    shift_s = i2c_time_shift_ms / 1000.0

    usable_i2c = [ev for ev in i2c_events if ev.timestamp is not None]
    usable_i2c.sort(key=lambda ev: ev.timestamp.timestamp() + shift_s)

    matched_i2c_idx: set[int] = set()
    results: list[MatchResult] = []
    i2c_start = 0

    for txn in usb_txns:
        usb_s = txn.timestamp.timestamp()
        window_start = usb_s
        window_end = usb_s + window_s

        while i2c_start < len(usable_i2c):
            first_i2c_s = usable_i2c[i2c_start].timestamp.timestamp() + shift_s
            if first_i2c_s >= window_start:
                break
            i2c_start += 1

        hits: list[SaleaeI2CEvent] = []
        scan_idx = i2c_start
        while scan_idx < len(usable_i2c):
            ev = usable_i2c[scan_idx]
            i2c_s = ev.timestamp.timestamp() + shift_s
            if i2c_s > window_end:
                break
            hits.append(ev)
            matched_i2c_idx.add(ev.index)
            scan_idx += 1

        status = "matched" if hits else "usb_without_i2c"
        if txn.status in {"stall", "canceled"}:
            status = f"{status}|{txn.status}"

        results.append(
            MatchResult(
                usb_txn_id=txn.txn_id,
                usb_time=txn.timestamp,
                matched_i2c_count=len(hits),
                first_i2c_time=hits[0].timestamp if hits else None,
                last_i2c_time=hits[-1].timestamp if hits else None,
                status=status,
            )
        )

    unmatched_i2c = [ev for ev in usable_i2c if ev.index not in matched_i2c_idx]
    return results, unmatched_i2c
