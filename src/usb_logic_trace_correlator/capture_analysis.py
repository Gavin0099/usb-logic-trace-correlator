from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Literal

from .bushound import UsbTransaction
from .saleae import SaleaeI2CEvent
from .saleae_sal_native import DigitalTransition, NativeDigitalChannel


DiffKind = Literal["unchanged", "added", "removed", "changed"]
TimelineKind = Literal["usb_transaction", "i2c_event", "digital_transition"]

_TRANSACTION_FIELDS = (
    "device",
    "bm_request_type",
    "b_request",
    "w_value",
    "w_index",
    "w_length",
    "data_direction",
    "payload_hex",
    "status",
)


@dataclass(frozen=True)
class TransactionDiff:
    kind: DiffKind
    pass_index: int | None
    fail_index: int | None
    pass_transaction: UsbTransaction | None
    fail_transaction: UsbTransaction | None
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimelineEvent:
    time_s: float
    kind: TimelineKind
    source: str
    label: str
    value: str | None
    state: int | None
    reference_id: int | None


@dataclass(frozen=True)
class SidebandObservation:
    channel: int
    channel_name: str
    state_before_window: int
    state_after_window: int
    transitions: tuple[DigitalTransition, ...]


@dataclass(frozen=True)
class TransactionSidebandCorrelation:
    txn_id: int
    transaction_time_s: float
    window_start_s: float
    window_end_s: float
    observations: tuple[SidebandObservation, ...]


def normalized_transaction_signature(transaction: UsbTransaction) -> tuple[str, ...]:
    """Return the stable command/status fields used by PASS/FAIL sequence diff."""
    values = []
    for field_name in _TRANSACTION_FIELDS:
        value = getattr(transaction, field_name)
        values.append(" ".join(str(value or "").strip().casefold().split()))
    return tuple(values)


def _changed_transaction_fields(pass_txn: UsbTransaction, fail_txn: UsbTransaction) -> tuple[str, ...]:
    pass_values = normalized_transaction_signature(pass_txn)
    fail_values = normalized_transaction_signature(fail_txn)
    return tuple(
        field_name
        for field_name, pass_value, fail_value in zip(_TRANSACTION_FIELDS, pass_values, fail_values)
        if pass_value != fail_value
    )


def diff_usb_transactions(
    pass_transactions: Iterable[UsbTransaction],
    fail_transactions: Iterable[UsbTransaction],
) -> list[TransactionDiff]:
    """Compare PASS and FAIL transactions while ignoring capture timestamps."""
    pass_items = list(pass_transactions)
    fail_items = list(fail_transactions)
    pass_signatures = [normalized_transaction_signature(item) for item in pass_items]
    fail_signatures = [normalized_transaction_signature(item) for item in fail_items]
    matcher = SequenceMatcher(None, pass_signatures, fail_signatures, autojunk=False)
    result: list[TransactionDiff] = []

    for tag, pass_start, pass_end, fail_start, fail_end in matcher.get_opcodes():
        if tag == "equal":
            result.extend(
                TransactionDiff("unchanged", pass_index, fail_index, pass_items[pass_index], fail_items[fail_index])
                for pass_index, fail_index in zip(range(pass_start, pass_end), range(fail_start, fail_end))
            )
            continue

        if tag == "replace":
            paired_count = min(pass_end - pass_start, fail_end - fail_start)
            result.extend(
                TransactionDiff(
                    "changed" if (fields := _changed_transaction_fields(pass_items[pass_index], fail_items[fail_index])) else "unchanged",
                    pass_index,
                    fail_index,
                    pass_items[pass_index],
                    fail_items[fail_index],
                    fields,
                )
                for pass_index, fail_index in zip(
                    range(pass_start, pass_start + paired_count),
                    range(fail_start, fail_start + paired_count),
                )
            )
            for pass_index in range(pass_start + paired_count, pass_end):
                result.append(TransactionDiff("removed", pass_index, None, pass_items[pass_index], None))
            for fail_index in range(fail_start + paired_count, fail_end):
                result.append(TransactionDiff("added", None, fail_index, None, fail_items[fail_index]))
            continue

        if tag == "delete":
            result.extend(
                TransactionDiff("removed", pass_index, None, pass_items[pass_index], None)
                for pass_index in range(pass_start, pass_end)
            )
        elif tag == "insert":
            result.extend(
                TransactionDiff("added", None, fail_index, None, fail_items[fail_index])
                for fail_index in range(fail_start, fail_end)
            )

    return result


def _relative_seconds(timestamp: datetime, capture_start: datetime) -> float:
    try:
        return (timestamp - capture_start).total_seconds()
    except TypeError as exc:
        raise ValueError("capture_start and event timestamps must use compatible timezone information") from exc


def _channel_label(channel: NativeDigitalChannel) -> str:
    return channel.name or f"channel-{channel.channel}"


def build_normalized_timeline(
    *,
    capture_start: datetime | None = None,
    usb_transactions: Iterable[UsbTransaction] = (),
    i2c_events: Iterable[SaleaeI2CEvent] = (),
    digital_channels: Iterable[NativeDigitalChannel] = (),
) -> list[TimelineEvent]:
    """Combine USB, I2C, and named digital transitions on capture-relative time."""
    usb_items = list(usb_transactions)
    if usb_items and capture_start is None:
        raise ValueError("capture_start is required to normalize USB transaction timestamps")

    timeline: list[TimelineEvent] = []
    for transaction in usb_items:
        assert capture_start is not None
        timeline.append(
            TimelineEvent(
                time_s=_relative_seconds(transaction.timestamp, capture_start),
                kind="usb_transaction",
                source="bushound",
                label=transaction.status,
                value=transaction.payload_hex or None,
                state=None,
                reference_id=transaction.txn_id,
            )
        )

    for event in i2c_events:
        timeline.append(
            TimelineEvent(
                time_s=event.time_s,
                kind="i2c_event",
                source="saleae_i2c",
                label=" ".join(part for part in (event.address or "", event.rw or "") if part),
                value=event.data_hex or None,
                state=None,
                reference_id=event.index,
            )
        )

    for channel in digital_channels:
        for transition in channel.transitions:
            timeline.append(
                TimelineEvent(
                    time_s=transition.time_s,
                    kind="digital_transition",
                    source=_channel_label(channel),
                    label=transition.edge,
                    value=str(transition.state),
                    state=transition.state,
                    reference_id=channel.channel,
                )
            )

    kind_order = {"digital_transition": 0, "i2c_event": 1, "usb_transaction": 2}
    return sorted(
        timeline,
        key=lambda event: (event.time_s, kind_order[event.kind], event.reference_id or 0),
    )


def _normalized_channel_name(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())


def _state_at(channel: NativeDigitalChannel, time_s: float, *, include_at: bool = True) -> int:
    state = channel.initial_state
    for transition in channel.transitions:
        if transition.time_s > time_s or (not include_at and transition.time_s >= time_s):
            break
        state = transition.state
    return state


def correlate_sideband_transitions(
    usb_transactions: Iterable[UsbTransaction],
    digital_channels: Iterable[NativeDigitalChannel],
    *,
    capture_start: datetime,
    window_before_s: float = 0.0,
    window_after_s: float = 0.0,
    channel_names: Collection[str] | None = None,
) -> list[TransactionSidebandCorrelation]:
    """Attach named digital edges around each USB transaction.

    Channel-name matching ignores case and separators, so ``HUB 5V`` also
    matches ``hub_5v``. An empty observation means the requested channel was
    not present in the capture or had no edge inside the requested window.
    """
    if window_before_s < 0 or window_after_s < 0:
        raise ValueError("sideband windows must be non-negative")

    requested = None if channel_names is None else {
        _normalized_channel_name(name) for name in channel_names
    }
    channels = [
        channel
        for channel in digital_channels
        if requested is None
        or (channel.name is not None and _normalized_channel_name(channel.name) in requested)
    ]
    result: list[TransactionSidebandCorrelation] = []
    for transaction in usb_transactions:
        transaction_time_s = _relative_seconds(transaction.timestamp, capture_start)
        window_start_s = transaction_time_s - window_before_s
        window_end_s = transaction_time_s + window_after_s
        observations = tuple(
            SidebandObservation(
                channel=channel.channel,
                channel_name=_channel_label(channel),
                state_before_window=_state_at(channel, window_start_s, include_at=False),
                state_after_window=_state_at(channel, window_end_s),
                transitions=tuple(
                    transition
                    for transition in channel.transitions
                    if window_start_s <= transition.time_s <= window_end_s
                ),
            )
            for channel in channels
        )
        result.append(
            TransactionSidebandCorrelation(
                txn_id=transaction.txn_id,
                transaction_time_s=transaction_time_s,
                window_start_s=window_start_s,
                window_end_s=window_end_s,
                observations=observations,
            )
        )
    return result