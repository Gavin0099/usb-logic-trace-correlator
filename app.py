from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usb_logic_trace_correlator.bushound import group_usb_transactions, parse_bushound_txt
from usb_logic_trace_correlator.compare import compare_usb_vs_i2c
from usb_logic_trace_correlator.saleae import parse_saleae_i2c_csv
from usb_logic_trace_correlator.saleae_sal import inspect_sal_bytes


def _parse_capture_start(text: str) -> datetime | None:
    raw = text.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


st.set_page_config(page_title="USB vs Saleae Diff", layout="wide")
st.title("USB Bus Hound ↔ Saleae 差異比對")
st.caption("上傳 Bus Hound TXT 與 Saleae（.sal 或 I2C CSV），直接找出兩邊不一致的地方。")

left, right = st.columns(2)
with left:
    bushound_file = st.file_uploader("Bus Hound TXT", type=["txt"])
with right:
    saleae_source = st.file_uploader("Saleae Source（.sal 或 I2C CSV）", type=["sal", "csv", "txt"])

saleae_csv_export = st.file_uploader(
    "Saleae Analyzer CSV（若上面傳 .sal，請再傳匯出 CSV）",
    type=["csv", "txt"],
)

cfg1, cfg2, cfg3 = st.columns(3)
with cfg1:
    capture_start_text = st.text_input(
        "Saleae Capture Start（可選）",
        placeholder="2026-05-28 09:56:36.380",
        help="若 Saleae CSV 只有相對時間，填入 capture start 後可與 Bus Hound 絕對時間對齊。",
    )
with cfg2:
    shift_ms = st.number_input("I2C 時間偏移 (ms)", value=0, step=1)
with cfg3:
    window_ms = st.number_input("匹配視窗 (ms)", min_value=1, value=20, step=1)

if bushound_file and saleae_source:
    bushound_text = bushound_file.getvalue().decode("utf-8", errors="replace")

    saleae_name = saleae_source.name.lower()
    capture_start = _parse_capture_start(capture_start_text)
    saleae_text = None

    if saleae_name.endswith(".sal"):
        info = inspect_sal_bytes(saleae_source.getvalue())
        if info.ok:
            st.success(info.message)
            st.write(
                {
                    "capture_start": info.capture_start_local,
                    "sample_rate_hz": info.sample_rate_hz,
                    "analyzers": info.analyzers,
                }
            )
            if not capture_start and info.capture_start_local:
                capture_start = _parse_capture_start(info.capture_start_local)
            if saleae_csv_export is not None:
                saleae_text = saleae_csv_export.getvalue().decode("utf-8", errors="replace")
            else:
                st.warning("目前是 .sal 檔，請再上傳 Saleae 匯出的 Analyzer CSV 才能做事件差異比對。")
        else:
            st.error(info.message)
    else:
        saleae_text = saleae_source.getvalue().decode("utf-8", errors="replace")

    bus_events = parse_bushound_txt(bushound_text)
    usb_txns = group_usb_transactions(bus_events)

    i2c_events = parse_saleae_i2c_csv(saleae_text, capture_start=capture_start) if saleae_text else []

    match_results, unmatched_i2c = compare_usb_vs_i2c(
        usb_txns,
        i2c_events,
        window_ms=int(window_ms),
        i2c_time_shift_ms=int(shift_ms),
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bus Hound Events", len(bus_events))
    c2.metric("USB Transactions", len(usb_txns))
    c3.metric("Saleae I2C Events", len(i2c_events))
    c4.metric("I2C 未匹配 USB", len(unmatched_i2c))

    match_df = pd.DataFrame(
        [
            {
                "usb_txn_id": r.usb_txn_id,
                "usb_time": r.usb_time,
                "matched_i2c_count": r.matched_i2c_count,
                "first_i2c_time": r.first_i2c_time,
                "last_i2c_time": r.last_i2c_time,
                "status": r.status,
            }
            for r in match_results
        ]
    )

    txn_df = pd.DataFrame(
        [
            {
                "txn_id": t.txn_id,
                "time": t.timestamp,
                "request": t.b_request,
                "wValue": t.w_value,
                "wIndex": t.w_index,
                "wLength": t.w_length,
                "direction": t.data_direction,
                "payload": t.payload_hex,
                "status": t.status,
            }
            for t in usb_txns
        ]
    )

    unmatched_usb = match_df[match_df["matched_i2c_count"] == 0]

    unmatched_i2c_df = pd.DataFrame(
        [
            {
                "index": ev.index,
                "time_s": ev.time_s,
                "timestamp": ev.timestamp,
                "address": ev.address,
                "rw": ev.rw,
                "data_hex": ev.data_hex,
                "ack": ev.ack,
                "summary": ev.raw_summary,
            }
            for ev in unmatched_i2c
        ]
    )

    st.subheader("差異總覽")
    ov1, ov2, ov3 = st.columns(3)
    ov1.metric("USB 無對應 I2C", len(unmatched_usb))
    ov2.metric("I2C 無對應 USB", len(unmatched_i2c_df))
    ov3.metric("USB 異常狀態", int((txn_df["status"] != "ok").sum()) if not txn_df.empty else 0)

    tab1, tab2, tab3, tab4 = st.tabs(["USB 無對應 I2C", "I2C 無對應 USB", "全部 USB Transaction", "Raw 匹配結果"])

    with tab1:
        if unmatched_usb.empty:
            st.success("沒有發現 USB 無對應 I2C 事件。")
        else:
            show = unmatched_usb.merge(txn_df, left_on="usb_txn_id", right_on="txn_id", how="left")
            st.dataframe(show, use_container_width=True)

    with tab2:
        if unmatched_i2c_df.empty:
            st.success("沒有發現 I2C 無對應 USB 事件。")
        else:
            st.dataframe(unmatched_i2c_df, use_container_width=True)

    with tab3:
        st.dataframe(txn_df, use_container_width=True)

    with tab4:
        st.dataframe(match_df, use_container_width=True)

    if not match_df.empty:
        st.download_button(
            "下載 USB↔I2C 匹配結果 CSV",
            data=match_df.to_csv(index=False).encode("utf-8"),
            file_name="usb_i2c_match_results.csv",
            mime="text/csv",
        )
else:
    st.info("請先上傳 Bus Hound TXT 與 Saleae 檔案。")
