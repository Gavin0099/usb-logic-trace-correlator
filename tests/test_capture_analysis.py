from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usb_logic_trace_correlator.bushound import UsbTransaction
from usb_logic_trace_correlator.capture_analysis import (
    build_normalized_timeline,
    correlate_sideband_transitions,
    diff_usb_transactions,
)
from usb_logic_trace_correlator.saleae import SaleaeI2CEvent
from usb_logic_trace_correlator.saleae_sal_native import DigitalTransition, NativeDigitalChannel


CAPTURE_START = datetime(2026, 9, 7, 10, 0, 0)


def _transaction(
    txn_id: int,
    *,
    timestamp: datetime,
    b_request: str = "ab",
    payload_hex: str = "80",
    status: str = "ok",
) -> UsbTransaction:
    return UsbTransaction(
        txn_id=txn_id,
        device="76.0",
        timestamp=timestamp,
        bm_request_type="40",
        b_request=b_request,
        w_value="6f94",
        w_index="0000",
        w_length="0001",
        data_direction="OUT",
        payload_hex=payload_hex,
        status=status,
        note="",
        delta_from_prev_ms=None,
        raw_events=[],
    )


def _channel(
    channel: int,
    name: str,
    initial_state: int,
    transitions: list[tuple[int, int, str]],
) -> NativeDigitalChannel:
    return NativeDigitalChannel(
        channel=channel,
        name=name,
        sample_rate_hz=1,
        initial_state=initial_state,
        end_sample=10,
        transitions=tuple(
            DigitalTransition(sample=sample, time_s=float(sample), state=state, edge=edge)
            for sample, state, edge in transitions
        ),
    )


def test_diff_ignores_capture_time_and_reports_changed_and_removed_transactions() -> None:
    pass_transactions = [
        _transaction(1, timestamp=CAPTURE_START + timedelta(seconds=1)),
        _transaction(2, timestamp=CAPTURE_START + timedelta(seconds=2)),
        _transaction(3, timestamp=CAPTURE_START + timedelta(seconds=3), b_request="ac"),
    ]
    fail_transactions = [
        _transaction(10, timestamp=CAPTURE_START + timedelta(seconds=10)),
        _transaction(20, timestamp=CAPTURE_START + timedelta(seconds=20), payload_hex="81", status="stall"),
    ]

    diff = diff_usb_transactions(pass_transactions, fail_transactions)

    assert [item.kind for item in diff] == ["unchanged", "changed", "removed"]
    assert diff[0].pass_index == 0
    assert diff[0].fail_index == 0
    assert diff[1].changed_fields == ("payload_hex", "status")
    assert diff[2].pass_transaction == pass_transactions[2]
    assert diff[2].fail_transaction is None


def test_diff_reports_inserted_transaction() -> None:
    pass_transactions = [_transaction(1, timestamp=CAPTURE_START)]
    fail_transactions = [
        _transaction(10, timestamp=CAPTURE_START + timedelta(seconds=5)),
        _transaction(20, timestamp=CAPTURE_START + timedelta(seconds=6), b_request="ac"),
    ]

    diff = diff_usb_transactions(pass_transactions, fail_transactions)

    assert [item.kind for item in diff] == ["unchanged", "added"]
    assert diff[1].pass_transaction is None
    assert diff[1].fail_transaction == fail_transactions[1]


def test_normalized_timeline_orders_usb_i2c_and_digital_events() -> None:
    usb_transaction = _transaction(7, timestamp=CAPTURE_START + timedelta(seconds=3))
    i2c_event = SaleaeI2CEvent(
        index=4,
        time_s=2.0,
        timestamp=CAPTURE_START + timedelta(seconds=2),
        address="0x67",
        rw="write",
        data_hex="3a",
        ack="ACK",
        raw_summary="0x67 write 3a ACK",
    )
    int_channel = _channel(2, "INT", 1, [(1, 0, "falling")])

    timeline = build_normalized_timeline(
        capture_start=CAPTURE_START,
        usb_transactions=[usb_transaction],
        i2c_events=[i2c_event],
        digital_channels=[int_channel],
    )

    assert [(event.time_s, event.kind, event.source) for event in timeline] == [
        (1.0, "digital_transition", "INT"),
        (2.0, "i2c_event", "saleae_i2c"),
        (3.0, "usb_transaction", "bushound"),
    ]


def test_sideband_correlation_includes_window_edges_and_normalizes_channel_names() -> None:
    int_channel = _channel(
        2,
        "INT",
        1,
        [(1, 0, "falling"), (3, 1, "rising")],
    )
    hub_channel = _channel(4, "HUB 5V", 0, [(2, 1, "rising")])
    sda_channel = _channel(5, "SDA", 1, [(2, 0, "falling")])
    transaction = _transaction(7, timestamp=CAPTURE_START + timedelta(seconds=2))

    correlations = correlate_sideband_transitions(
        [transaction],
        [int_channel, hub_channel, sda_channel],
        capture_start=CAPTURE_START,
        window_before_s=1.0,
        window_after_s=1.0,
        channel_names=["int", "hub_5v"],
    )

    assert len(correlations) == 1
    assert correlations[0].window_start_s == 1.0
    assert correlations[0].window_end_s == 3.0
    assert [observation.channel_name for observation in correlations[0].observations] == ["INT", "HUB 5V"]
    int_observation, hub_observation = correlations[0].observations
    assert int_observation.state_before_window == 1
    assert int_observation.state_after_window == 1
    assert [transition.sample for transition in int_observation.transitions] == [1, 3]
    assert hub_observation.state_before_window == 0
    assert hub_observation.state_after_window == 1
    assert [transition.sample for transition in hub_observation.transitions] == [2]


def test_sideband_correlation_rejects_negative_window() -> None:
    transaction = _transaction(7, timestamp=CAPTURE_START)

    with pytest.raises(ValueError, match="non-negative"):
        correlate_sideband_transitions(
            [transaction],
            [],
            capture_start=CAPTURE_START,
            window_before_s=-1.0,
        )