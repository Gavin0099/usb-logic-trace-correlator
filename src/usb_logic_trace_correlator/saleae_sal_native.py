from __future__ import annotations

from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import csv
import io
import json
import struct
from typing import Any
import zipfile

_MAGIC = b"<SALEAE>"
_DIGITAL_TYPE = 100
_SUPPORTED_VERSIONS = {2}
_FILE_HEADER_SIZE = 0x33
_CHUNK = struct.Struct("<QQHHIH")
_EDGE_GUARD_SAMPLES = 2


class SaleaeSalDecodeError(ValueError):
    """Native .sal data is unsupported, ambiguous, or malformed."""


@dataclass
class NativeI2CSupport:
    decodable: bool
    reason: str
    sample_rate_hz: int | None
    digital_channel_names: dict[int, str]


@dataclass(frozen=True)
class DigitalTransition:
    sample: int
    time_s: float
    state: int
    edge: str


@dataclass(frozen=True)
class NativeDigitalChannel:
    channel: int
    name: str | None
    sample_rate_hz: int
    initial_state: int
    end_sample: int
    transitions: tuple[DigitalTransition, ...]


@dataclass
class _Trace:
    initial_state: int
    end_sample: int
    transitions: array


@dataclass
class _Frame:
    start: int
    end: int
    termination: str
    address: int
    rw: str
    payload: list[int]
    ack_bits: list[int]
    trailing_bits: int


def _meta_parts(zf: zipfile.ZipFile) -> tuple[dict[str, Any], dict[str, Any]]:
    if "meta.json" not in zf.namelist():
        raise SaleaeSalDecodeError(".sal is missing meta.json")
    try:
        meta = json.loads(zf.read("meta.json").decode("utf-8", errors="strict"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SaleaeSalDecodeError("meta.json is not valid UTF-8 JSON") from exc
    if not isinstance(meta, dict):
        raise SaleaeSalDecodeError("meta.json root is not an object")
    payload = meta.get("data") if isinstance(meta.get("data"), dict) else meta
    return meta, payload


def _sample_rate(payload: dict[str, Any]) -> int | None:
    legacy = payload.get("legacySettings") or {}
    rate = legacy.get("sampleRate") if isinstance(legacy, dict) else None
    value = rate.get("digital") if isinstance(rate, dict) else None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    return None


def _i2c_channels(payload: dict[str, Any]) -> tuple[int, int] | None:
    found: list[tuple[int, int]] = []
    for analyzer in payload.get("analyzers", []):
        if not isinstance(analyzer, dict):
            continue
        kind = str(analyzer.get("type") or analyzer.get("name") or "").strip().lower()
        if kind != "i2c":
            continue
        settings: dict[str, Any] = {}
        for item in analyzer.get("settings", []):
            if not isinstance(item, dict):
                continue
            setting = item.get("setting") or {}
            if isinstance(setting, dict):
                settings[str(item.get("title") or "").strip().upper()] = setting.get("value")
        sda, scl = settings.get("SDA"), settings.get("SCL")
        if isinstance(sda, int) and isinstance(scl, int):
            found.append((sda, scl))
    return found[0] if len(found) == 1 else None


def _file_map(meta: dict[str, Any], payload: dict[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    items: list[Any] = []
    for source in (meta.get("binData"), payload.get("binData")):
        if isinstance(source, list):
            items.extend(source)
    for item in items:
        if not isinstance(item, dict) or str(item.get("type", "")).lower() != "digital":
            continue
        channel, filename = item.get("deviceChannel"), item.get("file")
        if isinstance(channel, int) and isinstance(filename, str):
            result[channel] = filename.removeprefix("./")
    return result


def _channel_names(payload: dict[str, Any], available: set[int]) -> dict[int, str]:
    result: dict[int, str] = {}
    for row in payload.get("rowsSettings", []):
        if not isinstance(row, dict):
            continue
        channel = row.get("channel") or {}
        if not isinstance(channel, dict) or str(channel.get("type", "")).lower() != "digital":
            continue
        index, name = channel.get("deviceChannel"), row.get("name")
        if isinstance(index, int) and index in available and isinstance(name, str):
            result[index] = name
    return result


def inspect_native_i2c_support(data: bytes) -> NativeI2CSupport:
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            meta, payload = _meta_parts(zf)
            rate = _sample_rate(payload)
            files = _file_map(meta, payload)
            names = _channel_names(payload, set(files))
            channels = _i2c_channels(payload)
            if channels is None:
                return NativeI2CSupport(False, "需要且目前僅支援一組具明確 SDA/SCL channel 的 I2C analyzer。", rate, names)
            if rate is None:
                return NativeI2CSupport(False, "找不到有效的 digital sample rate。", None, names)
            for role, channel in zip(("SDA", "SCL"), channels):
                filename = files.get(channel, f"digital-{channel}.bin")
                if filename not in zf.namelist():
                    return NativeI2CSupport(False, f"找不到 {role} channel {channel} 的 digital binary。", rate, names)
                header = zf.read(filename)[:16]
                if len(header) < 16 or header[:8] != _MAGIC:
                    return NativeI2CSupport(False, f"{role} digital binary header 無法識別。", rate, names)
                version, data_type = struct.unpack_from("<II", header, 8)
                if data_type != _DIGITAL_TYPE:
                    return NativeI2CSupport(False, f"{role} channel 不是 digital data type。", rate, names)
                if version not in _SUPPORTED_VERSIONS:
                    return NativeI2CSupport(False, f"Saleae digital binary version {version} 尚未驗證，拒絕猜測解碼。", rate, names)
            return NativeI2CSupport(True, "可使用已驗證的 Saleae digital v2 RLE 路徑原生解碼 I2C。", rate, names)
    except (zipfile.BadZipFile, SaleaeSalDecodeError):
        return NativeI2CSupport(False, "檔案不是可原生解碼的 Saleae .sal。", None, {})


def _varint(buf: memoryview, offset: int) -> tuple[int, int]:
    if offset >= len(buf):
        raise SaleaeSalDecodeError("truncated digital RLE varint")
    first = int(buf[offset])
    if first < 0x40:
        return first + 1, offset + 1
    if (first & 0xC0) != 0x40:
        raise SaleaeSalDecodeError(f"invalid digital RLE varint start 0x{first:02x}")
    value, offset = first & 0x3F, offset + 1
    while True:
        if offset >= len(buf):
            raise SaleaeSalDecodeError("truncated multi-byte digital RLE varint")
        byte, offset = int(buf[offset]), offset + 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            return value + 1, offset


def _decode_digital(data: bytes) -> _Trace:
    if len(data) < _FILE_HEADER_SIZE or data[:8] != _MAGIC:
        raise SaleaeSalDecodeError("invalid Saleae digital header")
    version, data_type = struct.unpack_from("<II", data, 8)
    if version not in _SUPPORTED_VERSIONS:
        raise SaleaeSalDecodeError(f"unsupported Saleae digital binary version {version}")
    if data_type != _DIGITAL_TYPE:
        raise SaleaeSalDecodeError(f"unexpected Saleae data type {data_type}")

    offset, expected_start = _FILE_HEADER_SIZE, None
    transitions, first_chunk = array("Q"), True
    initial_state = current_state = end_sample = 0
    while offset < len(data):
        if len(data) - offset < _CHUNK.size:
            raise SaleaeSalDecodeError("truncated Saleae digital chunk header")
        start, end, chunk_state, byte_size, _reserved, _tail = _CHUNK.unpack_from(data, offset)
        offset += _CHUNK.size
        if chunk_state not in (0, 1) or end < start:
            raise SaleaeSalDecodeError("invalid Saleae digital chunk")
        if expected_start is not None and start != expected_start:
            raise SaleaeSalDecodeError("Saleae digital chunks are not contiguous")
        if offset + byte_size > len(data):
            raise SaleaeSalDecodeError("truncated Saleae digital chunk payload")
        payload = memoryview(data)[offset : offset + byte_size]
        offset += byte_size

        if first_chunk:
            first_chunk = False
            initial_state = current_state = chunk_state
        elif chunk_state != current_state:
            transitions.append(start)
            current_state = chunk_state

        position = start
        p = 0
        while p < len(payload):
            run, p = _varint(payload, p)
            if position + run > end:
                raise SaleaeSalDecodeError("digital RLE run exceeds chunk end")
            position += run
            if position < end:
                transitions.append(position)
                current_state ^= 1
        if position != end:
            raise SaleaeSalDecodeError("digital RLE coverage mismatch")
        expected_start = end_sample = end

    if first_chunk:
        raise SaleaeSalDecodeError("Saleae digital file contains no chunks")
    return _Trace(initial_state, end_sample, transitions)


def _public_transitions(trace: _Trace, sample_rate_hz: int) -> tuple[DigitalTransition, ...]:
    state = trace.initial_state
    transitions: list[DigitalTransition] = []
    for sample in trace.transitions:
        state ^= 1
        transitions.append(
            DigitalTransition(
                sample=int(sample),
                time_s=float(sample) / sample_rate_hz,
                state=state,
                edge="rising" if state else "falling",
            )
        )
    return tuple(transitions)


def decode_digital_channels_from_sal_bytes(data: bytes) -> list[NativeDigitalChannel]:
    """Decode every mapped digital-v2 channel from a supported `.sal` archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            meta, payload = _meta_parts(zf)
            sample_rate_hz = _sample_rate(payload)
            if sample_rate_hz is None:
                raise SaleaeSalDecodeError("missing digital sample rate")
            files = _file_map(meta, payload)
            if not files:
                raise SaleaeSalDecodeError(".sal contains no mapped digital channels")
            names = _channel_names(payload, set(files))
            channels: list[NativeDigitalChannel] = []
            for channel, filename in sorted(files.items()):
                if filename not in zf.namelist():
                    raise SaleaeSalDecodeError(f"missing digital channel file for channel {channel}")
                trace = _decode_digital(zf.read(filename))
                channels.append(
                    NativeDigitalChannel(
                        channel=channel,
                        name=names.get(channel),
                        sample_rate_hz=sample_rate_hz,
                        initial_state=trace.initial_state,
                        end_sample=trace.end_sample,
                        transitions=_public_transitions(trace, sample_rate_hz),
                    )
                )
            return channels
    except zipfile.BadZipFile as exc:
        raise SaleaeSalDecodeError("file is not a valid .sal/.zip archive") from exc


def _markers(sda: _Trace, scl: _Trace) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    j, scl_state, last_scl_edge = 0, scl.initial_state, 0
    for i, sample in enumerate(sda.transitions):
        while j < len(scl.transitions) and scl.transitions[j] <= sample:
            scl_state ^= 1
            last_scl_edge = int(scl.transitions[j])
            j += 1
        next_scl_edge = int(scl.transitions[j]) if j < len(scl.transitions) else scl.end_sample
        if scl_state != 1 or sample - last_scl_edge < _EDGE_GUARD_SAMPLES or next_scl_edge - sample < _EDGE_GUARD_SAMPLES:
            continue
        before = sda.initial_state ^ (i & 1)
        if before == 1:
            result.append((int(sample), "start"))
        else:
            result.append((int(sample), "stop"))
    return result


def _rises(trace: _Trace) -> array:
    result, state = array("Q"), trace.initial_state
    for sample in trace.transitions:
        state ^= 1
        if state == 1:
            result.append(sample)
    return result


def _frames(sda: _Trace, scl: _Trace) -> list[_Frame]:
    spans: list[tuple[int, int, str]] = []
    current: int | None = None
    for sample, kind in _markers(sda, scl):
        if kind == "start":
            if current is not None and sample > current:
                spans.append((current, sample, "repeated_start"))
            current = sample
        elif current is not None and sample > current:
            spans.append((current, sample, "stop"))
            current = None

    rises = _rises(scl)
    result: list[_Frame] = []
    for start, end, termination in spans:
        lo, hi = bisect_right(rises, start), bisect_left(rises, end)
        if lo >= hi:
            continue
        sda_index = bisect_right(sda.transitions, start)
        sda_state = sda.initial_state ^ (sda_index & 1)
        bits: list[int] = []
        for edge_index in range(lo, hi):
            edge = int(rises[edge_index])
            while sda_index < len(sda.transitions) and sda.transitions[sda_index] <= edge:
                sda_state ^= 1
                sda_index += 1
            bits.append(sda_state)

        byte_count = len(bits) // 9
        if byte_count == 0:
            continue
        values, acks = [], []
        for byte_index in range(byte_count):
            block = bits[byte_index * 9 : (byte_index + 1) * 9]
            value = 0
            for bit in block[:8]:
                value = (value << 1) | bit
            values.append(value)
            acks.append(block[8])
        address_byte = values[0]
        result.append(_Frame(start, end, termination, address_byte >> 1, "read" if address_byte & 1 else "write", values[1:], acks, len(bits) % 9))
    return result


def decode_i2c_csv_from_sal_bytes(data: bytes) -> str:
    """Decode one supported I2C bus from raw `.sal` digital data.

    This is a bounded compatibility path for validated Saleae digital-v2 RLE,
    not a claim that Saleae's internal file format is stable. Unknown versions
    and ambiguous analyzer selection fail closed.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            meta, payload = _meta_parts(zf)
            channels = _i2c_channels(payload)
            if channels is None:
                raise SaleaeSalDecodeError("native decode requires exactly one I2C analyzer with explicit SDA/SCL channels")
            rate = _sample_rate(payload)
            if rate is None:
                raise SaleaeSalDecodeError("missing digital sample rate")
            files = _file_map(meta, payload)
            traces = []
            for channel in channels:
                filename = files.get(channel, f"digital-{channel}.bin")
                if filename not in zf.namelist():
                    raise SaleaeSalDecodeError(f"missing digital channel file for channel {channel}")
                traces.append(_decode_digital(zf.read(filename)))
            sda, scl = traces
            if sda.end_sample != scl.end_sample:
                raise SaleaeSalDecodeError("SDA/SCL capture lengths differ")
            frames = _frames(sda, scl)
    except zipfile.BadZipFile as exc:
        raise SaleaeSalDecodeError("file is not a valid .sal/.zip archive") from exc

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Time [s]", "Address", "Read/Write", "Data", "ACK", "Summary"])
    for frame in frames:
        address_ack = frame.ack_bits[0] if frame.ack_bits else 1
        writer.writerow([
            f"{frame.start / rate:.9f}",
            f"0x{frame.address:02X}",
            frame.rw,
            " ".join(f"{value:02X}" for value in frame.payload),
            "ACK" if address_ack == 0 else "NACK",
            f"native_sal; termination={frame.termination}; trailing_bits={frame.trailing_bits}",
        ])
    return output.getvalue()
