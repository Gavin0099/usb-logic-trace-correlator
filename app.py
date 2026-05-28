from __future__ import annotations

from collections import Counter
from datetime import datetime
import io
from pathlib import Path
import sys

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usb_logic_trace_correlator.bushound import group_usb_transactions, parse_bushound_txt
from usb_logic_trace_correlator.compare import compare_usb_vs_i2c
from usb_logic_trace_correlator.saleae import parse_saleae_i2c_csv
from usb_logic_trace_correlator.saleae_sal import extract_i2c_csv_from_sal_bytes, inspect_sal_bytes


LARGE_FILE_THRESHOLD_BYTES = 200 * 1024 * 1024
DEFAULT_LARGE_ROW_CAP = 200_000
DEFAULT_TABLE_ROW_CAP = 2_000


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


def _status_block(label: str, state: str, detail: str, tone: str) -> None:
    colors = {
        "ok": "#1f7a3e",
        "warn": "#9a6700",
        "error": "#a40e26",
        "muted": "#6b7280",
    }
    color = colors.get(tone, colors["muted"])
    st.markdown(
        f"""
        <div style=\"padding:0.8rem;border:1px solid #e5e7eb;border-radius:0.6rem;height:100%;\">
            <div style=\"font-size:0.85rem;color:#6b7280;\">{label}</div>
            <div style=\"font-size:1.05rem;font-weight:700;color:{color};\">{state}</div>
            <div style=\"font-size:0.82rem;color:#4b5563;\">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _payload_short(payload_hex: str, limit: int = 24) -> str:
    text = payload_hex.replace(" ", "")
    if not text:
        return "-"
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


@st.cache_data(show_spinner=False)
def _parse_bushound_cached(bushound_text: str) -> tuple[list, list]:
    bus_events = parse_bushound_txt(bushound_text)
    usb_txns = group_usb_transactions(bus_events)
    return bus_events, usb_txns


@st.cache_data(show_spinner=False)
def _parse_saleae_cached(saleae_text: str, capture_start: datetime | None) -> list:
    return parse_saleae_i2c_csv(saleae_text, capture_start=capture_start)


def _uploaded_size(uploaded_file) -> int | None:
    return getattr(uploaded_file, "size", None)


def _format_size(size: int | None) -> str:
    if size is None:
        return "unknown"
    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _parse_bushound_stream(uploaded_file, max_events: int | None = None):
    uploaded_file.seek(0)
    with io.TextIOWrapper(uploaded_file, encoding="utf-8", errors="replace") as stream:
        return parse_bushound_txt(stream, max_events=max_events)


def _parse_saleae_stream(uploaded_file, capture_start: datetime | None, max_events: int | None = None):
    uploaded_file.seek(0)
    with io.TextIOWrapper(uploaded_file, encoding="utf-8", errors="replace") as stream:
        return parse_saleae_i2c_csv(stream, capture_start=capture_start, max_events=max_events)


def _cap_df(df: pd.DataFrame, row_cap: int) -> tuple[pd.DataFrame, bool]:
    if len(df) <= row_cap:
        return df, False
    return df.head(row_cap), True


def _build_txn_df(usb_txns: list) -> pd.DataFrame:
    rows: list[dict] = []
    prev_key = None
    repeat_run = 0
    for txn in usb_txns:
        key = (txn.data_direction, txn.b_request, txn.w_value, txn.status)
        if key == prev_key:
            repeat_run += 1
        else:
            repeat_run = 1
            prev_key = key
        rows.append(
            {
                "txn_id": txn.txn_id,
                "time": txn.timestamp,
                "time_text": txn.timestamp.strftime("%H:%M:%S.%f")[:-3],
                "direction": txn.data_direction or "-",
                "request": txn.b_request,
                "wValue": txn.w_value,
                "wIndex": txn.w_index,
                "wLength": txn.w_length,
                "payload": _payload_short(txn.payload_hex),
                "payload_raw": txn.payload_hex,
                "status": txn.status,
                "delta_ms": None if txn.delta_from_prev_ms is None else round(txn.delta_from_prev_ms, 3),
                "note": txn.note,
                "repeat_run": repeat_run,
            }
        )
    return pd.DataFrame(rows)


def _nearest_i2c_delta_ms(usb_time: datetime, i2c_events: list, shift_ms: int) -> float | None:
    if not i2c_events:
        return None
    best: float | None = None
    for ev in i2c_events:
        if ev.timestamp is None:
            continue
        delta_ms = ((ev.timestamp.timestamp() + (shift_ms / 1000.0)) - usb_time.timestamp()) * 1000.0
        if best is None or abs(delta_ms) < abs(best):
            best = delta_ms
    return None if best is None else round(best, 3)


def _timeline_chart(txn_df: pd.DataFrame, i2c_events: list, shift_ms: int) -> None:
    if txn_df.empty:
        st.info("沒有可顯示的 USB transaction。")
        return

    points = []
    for _, row in txn_df.iterrows():
        lane = "USB"
        status = str(row["status"])
        if status in {"stall", "canceled"}:
            lane = "ERR"
        points.append(
            {
                "timestamp": row["time"],
                "lane": lane,
                "type": f"USB {row['direction']} req={row['request']} status={status}",
            }
        )

    for ev in i2c_events:
        if ev.timestamp is None:
            continue
        points.append(
            {
                "timestamp": datetime.fromtimestamp(ev.timestamp.timestamp() + (shift_ms / 1000.0)),
                "lane": "I2C",
                "type": f"I2C {ev.rw} addr={ev.address} data={ev.data_hex}",
            }
        )

    chart_df = pd.DataFrame(points)
    if chart_df.empty:
        st.info("沒有可顯示的 timeline 事件。")
        return

    color_scale = alt.Scale(domain=["USB", "I2C", "ERR"], range=["#2563eb", "#16a34a", "#dc2626"])
    chart = (
        alt.Chart(chart_df)
        .mark_tick(thickness=2, size=18)
        .encode(
            x=alt.X("timestamp:T", title="Time"),
            y=alt.Y("lane:N", title="Lane"),
            color=alt.Color("lane:N", scale=color_scale, legend=None),
            tooltip=["timestamp:T", "lane:N", "type:N"],
        )
        .properties(height=180)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_saleae_export_guide(
    saleae_mode: str,
    saleae_info,
    saleae_text: str | None,
    i2c_events: list,
    sal_auto_csv_text: str | None,
) -> None:
    st.markdown("#### Saleae Export Guide")

    if saleae_mode == "sal":
        st.info("目前是 .sal metadata 模式。若要啟用 correlation，請匯出 I2C Analyzer CSV。")
        if sal_auto_csv_text:
            st.success("已在 .sal 內找到可用 CSV 內容，並可直接使用或下載檢查。")
            st.download_button(
                "下載自動抽取 CSV",
                data=sal_auto_csv_text.encode("utf-8"),
                file_name="extracted_from_sal_i2c.csv",
                mime="text/csv",
            )
        else:
            st.warning("此 .sal 未包含可直接解析的 Analyzer CSV（這是常見情況）。")
            if saleae_info and getattr(saleae_info, "archive_entries", None):
                with st.expander("檢視 .sal 封包內容"):
                    for name in saleae_info.archive_entries:
                        st.text(name)
    elif saleae_mode == "csv" and saleae_text and not i2c_events:
        st.warning("已提供 CSV，但目前解析不到 I2C 事件。請檢查欄位名稱或匯出格式。")
    else:
        st.info("尚未提供可用的 Saleae I2C Analyzer CSV。")

    if saleae_info and getattr(saleae_info, "ok", False):
        st.write(
            {
                "detected_analyzers": saleae_info.analyzers,
                "capture_start": saleae_info.capture_start_local,
            }
        )

    st.markdown("1. 在 Saleae Logic 2 開啟該 capture")
    st.markdown("2. 確認已加上 I2C analyzer（SCL/SDA channel 正確）")
    st.markdown("3. 從 analyzer 結果執行 Export，格式選 CSV")
    st.markdown("4. 建議檔名：capture_i2c_analyzer.csv")
    st.markdown("5. 回到此工具上傳 Saleae Analyzer CSV")

    st.caption("CSV 最少要有 Time 與事件內容欄位（Address/Data 或 Summary）。")
    st.code("Time [s],Address,Read/Write,Data,ACK,Summary")

    st.download_button(
        "下載 CSV Header 範例",
        data="Time [s],Address,Read/Write,Data,ACK,Summary\n",
        file_name="saleae_i2c_export_template.csv",
        mime="text/csv",
    )


st.set_page_config(page_title="USB 追蹤除錯工作台", layout="wide")
st.title("USB Bus Hound ↔ Saleae 追蹤除錯工作台")
st.caption("以交易為中心，診斷 USB 廠商命令與外部匯流排行為。")

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

bushound_size = _uploaded_size(bushound_file)
saleae_source_size = _uploaded_size(saleae_source) if saleae_source else None
saleae_csv_export_size = _uploaded_size(saleae_csv_export)
detected_large_files = any(
    size is not None and size >= LARGE_FILE_THRESHOLD_BYTES
    for size in [bushound_size, saleae_source_size, saleae_csv_export_size]
)

large_mode = st.checkbox(
    "大檔案模式（串流 + 資料列上限）",
    value=detected_large_files,
    help="當輸入檔案達數百 MB 以上時建議開啟。避免額外文字複製，並在達到列數上限後停止解析。",
)

large_row_cap = None
if large_mode:
    large_row_cap = int(
        st.number_input(
            "解析列數上限",
            min_value=1_000,
            value=DEFAULT_LARGE_ROW_CAP,
            step=10_000,
            help="僅在大檔案模式下使用。每個來源解析到此列數後停止。",
        )
    )

perf_mode = st.checkbox(
    "效能模式（UI 更快，限制渲染量）",
    value=large_mode,
    help="限制表格渲染量，並略過可能導致 UI 凍結的高成本運算。",
)

table_row_cap = int(
    st.number_input(
        "UI 表格列數上限",
        min_value=200,
        value=DEFAULT_TABLE_ROW_CAP,
        step=200,
        help="每張表格最多顯示的列數，數值越大 UI 越慢。",
    )
)

if detected_large_files:
    st.warning(
        "偵測到大型上傳："
        f"Bus Hound={_format_size(bushound_size)}，"
        f"Saleae 來源={_format_size(saleae_source_size)}，"
        f"Saleae CSV 匯出={_format_size(saleae_csv_export_size)}。"
    )

if bushound_file:
    capture_start = _parse_capture_start(capture_start_text)
    saleae_text = None
    saleae_info = None
    saleae_mode = "missing"
    sal_auto_csv_used = False
    sal_auto_csv_text = None

    if large_mode:
        bus_events = _parse_bushound_stream(bushound_file, max_events=large_row_cap)
        usb_txns = group_usb_transactions(bus_events)
    else:
        bushound_text = bushound_file.getvalue().decode("utf-8", errors="replace")
        bus_events, usb_txns = _parse_bushound_cached(bushound_text)

    if saleae_source:
        saleae_name = saleae_source.name.lower()
        if saleae_name.endswith(".sal"):
            saleae_mode = "sal"
            sal_bytes = saleae_source.getvalue()
            saleae_info = inspect_sal_bytes(sal_bytes)
            if saleae_info.ok:
                if not capture_start and saleae_info.capture_start_local:
                    capture_start = _parse_capture_start(saleae_info.capture_start_local)

                if saleae_csv_export is not None:
                    if large_mode:
                        saleae_text = _parse_saleae_stream(saleae_csv_export, capture_start, max_events=large_row_cap)
                    else:
                        saleae_text = saleae_csv_export.getvalue().decode("utf-8", errors="replace")
                else:
                    sal_auto_csv_text = extract_i2c_csv_from_sal_bytes(sal_bytes)
                    if sal_auto_csv_text:
                        sal_auto_csv_used = True
                        if large_mode:
                            saleae_text = parse_saleae_i2c_csv(
                                sal_auto_csv_text,
                                capture_start=capture_start,
                                max_events=large_row_cap,
                            )
                        else:
                            saleae_text = sal_auto_csv_text
                    else:
                        saleae_text = None
            else:
                st.error(saleae_info.message)
        else:
            saleae_mode = "csv"
            if large_mode:
                saleae_text = _parse_saleae_stream(saleae_source, capture_start, max_events=large_row_cap)
            else:
                saleae_text = saleae_source.getvalue().decode("utf-8", errors="replace")
    elif saleae_csv_export is not None:
        saleae_mode = "csv"
        if large_mode:
            saleae_text = _parse_saleae_stream(saleae_csv_export, capture_start, max_events=large_row_cap)
        else:
            saleae_text = saleae_csv_export.getvalue().decode("utf-8", errors="replace")

    txn_df = _build_txn_df(usb_txns)

    if large_mode and isinstance(saleae_text, list):
        i2c_events = saleae_text
    else:
        i2c_events = _parse_saleae_cached(saleae_text, capture_start) if saleae_text else []
    correlation_ready = len(i2c_events) > 0

    if correlation_ready:
        match_results, unmatched_i2c = compare_usb_vs_i2c(
            usb_txns,
            i2c_events,
            window_ms=int(window_ms),
            i2c_time_shift_ms=int(shift_ms),
        )
    else:
        match_results, unmatched_i2c = [], []

    match_df = pd.DataFrame(
        [
            {
                "usb_txn_id": r.usb_txn_id,
                "usb_time": r.usb_time,
                "matched_i2c_count": r.matched_i2c_count,
                "first_i2c_time": r.first_i2c_time,
                "last_i2c_time": r.last_i2c_time,
                "match_status": r.status,
            }
            for r in match_results
        ]
    )

    unmatched_usb = match_df[match_df["matched_i2c_count"] == 0] if not match_df.empty else pd.DataFrame()

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

    out_count = int((txn_df["direction"] == "OUT").sum()) if not txn_df.empty else 0
    in_count = int((txn_df["direction"] == "IN").sum()) if not txn_df.empty else 0
    status_counter = Counter(txn_df["status"].tolist()) if not txn_df.empty else Counter()
    top_reqs = ", ".join([req for req, _ in Counter(txn_df["request"].tolist()).most_common(3)]) if not txn_df.empty else "-"
    long_gap_threshold_ms = 1000.0
    long_gap_count = int((txn_df["delta_ms"].fillna(0) > long_gap_threshold_ms).sum()) if not txn_df.empty else 0
    usb_error_count = int((txn_df["status"] != "ok").sum()) if not txn_df.empty else 0

    st.subheader("資料就緒狀態")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        if bus_events:
            _status_block("Bus Hound TXT", "已解析", f"{len(bus_events)} 事件 / {len(usb_txns)} 交易", "ok")
        else:
            _status_block("Bus Hound TXT", "缺少", "需要上傳", "error")
    with s2:
        if saleae_mode == "sal" and saleae_info and saleae_info.ok:
            analyzer_text = ", ".join(saleae_info.analyzers) if saleae_info.analyzers else "none"
            _status_block("Saleae .sal", "僅 Metadata", f"Analyzers: {analyzer_text}", "warn")
        elif saleae_mode == "csv":
            _status_block("Saleae .sal", "可選", "以 CSV 為來源", "muted")
        else:
            _status_block("Saleae .sal", "未提供", "可選 Metadata", "muted")
    with s3:
        if correlation_ready:
            source = "自 .sal 自動抽取" if sal_auto_csv_used else "Analyzer CSV 已解析"
            _status_block("Saleae CSV", "就緒", f"{len(i2c_events)} 個 I2C 事件（{source}）", "ok")
        else:
            _status_block("Saleae CSV", "缺少", "比對需要此檔", "error")
    with s4:
        if correlation_ready:
            _status_block("比對結果", "已啟用", f"window={int(window_ms)}ms，shift={int(shift_ms)}ms", "ok")
        else:
            _status_block("比對結果", "已停用", "需要已解析 I2C 事件", "warn")

    st.subheader("診斷摘要")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("USB 交易數", len(usb_txns), f"{out_count} OUT / {in_count} IN")
    c2.metric("比對狀態", "就緒" if correlation_ready else "未就緒", f"Top req: {top_reqs}")
    c3.metric(
        "USB 錯誤",
        usb_error_count,
        f"{status_counter.get('canceled', 0)} canceled / {status_counter.get('stall', 0)} stall",
    )
    c4.metric("可疑時間窗口", long_gap_count, f"長間隔 > {int(long_gap_threshold_ms)}ms")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["概覽", "USB 瀏覽器", "錯誤與逓時", "比對結果", "原始資料"])

    with tab1:
        if not correlation_ready:
            st.warning(
                "目前只能解析 Bus Hound transaction。Saleae 尚未提供可用 Analyzer CSV，因此 USB ↔ I2C 差異比對尚未成立。"
            )
        if saleae_mode == "sal" and saleae_info and saleae_info.ok:
            st.write(
                {
                    "capture_start": saleae_info.capture_start_local,
                    "sample_rate_hz": saleae_info.sample_rate_hz,
                    "analyzers": saleae_info.analyzers,
                }
            )
        if perf_mode and (len(txn_df) > table_row_cap or len(i2c_events) > table_row_cap):
            st.info("效能模式：大型資料集不顯示時間軸。")
        else:
            _timeline_chart(txn_df, i2c_events if correlation_ready else [], int(shift_ms))

    with tab2:
        if txn_df.empty:
            st.info("沒有可顯示的 USB transaction。")
        else:
            f1, f2, f3 = st.columns([2, 1, 1])
            with f1:
                search_text = st.text_input("搜尋", placeholder="request / wValue / payload / status")
            with f2:
                dir_filter = st.multiselect("方向", options=sorted(txn_df["direction"].dropna().unique().tolist()), default=[])
            with f3:
                status_filter = st.multiselect("狀態", options=sorted(txn_df["status"].dropna().unique().tolist()), default=[])

            f4, f5 = st.columns(2)
            with f4:
                request_filter = st.multiselect("請求指令", options=sorted(txn_df["request"].dropna().unique().tolist()), default=[])
            with f5:
                only_errors = st.checkbox("僅顯示錯誤", value=False)
                only_long_gap = st.checkbox("長間隔 > 1 秒", value=False)
                only_repeated = st.checkbox("重複命令", value=False)

            filtered = txn_df.copy()
            if dir_filter:
                filtered = filtered[filtered["direction"].isin(dir_filter)]
            if status_filter:
                filtered = filtered[filtered["status"].isin(status_filter)]
            if request_filter:
                filtered = filtered[filtered["request"].isin(request_filter)]
            if only_errors:
                filtered = filtered[filtered["status"] != "ok"]
            if only_long_gap:
                filtered = filtered[filtered["delta_ms"].fillna(0) > 1000.0]
            if only_repeated:
                filtered = filtered[filtered["repeat_run"] > 1]

            if search_text.strip():
                q = search_text.strip().lower()

                def _row_match(row: pd.Series) -> bool:
                    return any(
                        q in str(row[col]).lower()
                        for col in ["request", "wValue", "payload", "status", "note", "wIndex", "wLength"]
                    )

                filtered = filtered[filtered.apply(_row_match, axis=1)]

            left_panel, right_panel = st.columns([1.8, 1.2])
            with left_panel:
                st.caption(f"筛選後交易數：{len(filtered)}")
                filtered_view, filtered_trimmed = _cap_df(filtered, table_row_cap)
                if filtered_trimmed:
                    st.caption(f"UI 僅顯示前 {table_row_cap} 列。")
                st.dataframe(
                    filtered_view[["txn_id", "time_text", "direction", "request", "wValue", "payload", "status", "delta_ms", "note"]],
                    use_container_width=True,
                    hide_index=True,
                )

            with right_panel:
                if filtered.empty:
                    st.info("目前篩選條件下沒有 transaction。")
                else:
                    txn_map = {t.txn_id: t for t in usb_txns}
                    ids = filtered_view["txn_id"].tolist()
                    selected_id = st.selectbox(
                        "選取交易查看",
                        options=ids,
                        format_func=lambda i: (
                            f"#{i} {txn_map[i].timestamp.strftime('%H:%M:%S.%f')[:-3]} "
                            f"{txn_map[i].data_direction} req={txn_map[i].b_request} {txn_map[i].status}"
                        ),
                    )
                    selected = txn_map[selected_id]
                    st.markdown(f"### USB 交易 #{selected.txn_id}")
                    st.write({"time": selected.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "status": selected.status})
                    st.code(
                        "\n".join(
                            [
                                f"bmRequestType: 0x{selected.bm_request_type}",
                                f"bRequest:      0x{selected.b_request}",
                                f"wValue:        0x{selected.w_value}",
                                f"wIndex:        0x{selected.w_index}",
                                f"wLength:       0x{selected.w_length}",
                            ]
                        )
                    )
                    st.write({"payload": selected.payload_hex or "-", "note": selected.note or "-"})

                    if correlation_ready:
                        matched = next((r for r in match_results if r.usb_txn_id == selected.txn_id), None)
                        if matched and matched.matched_i2c_count > 0:
                            st.success(f"已匹配 I2C 事件：{matched.matched_i2c_count} 個")
                        else:
                            nearest = _nearest_i2c_delta_ms(selected.timestamp, i2c_events, int(shift_ms))
                            msg = "目前視窗內無 I2C 事件"
                            if nearest is not None:
                                msg += f"。最近 I2C：{nearest:+.3f} ms"
                            st.warning(msg)
                    else:
                        st.info("Saleae 事件不可用：缺少 Analyzer CSV 或解析到 0 個事件。")

                    with st.expander("原始資料列"):
                        for ev in selected.raw_events:
                            st.text(ev.raw_line)

    with tab3:
        if txn_df.empty:
            st.info("沒有可分析的 transaction。")
        else:
            err_df = txn_df[(txn_df["status"] != "ok") | (txn_df["delta_ms"].fillna(0) > 1000.0) | (txn_df["repeat_run"] > 1)].copy()
            err_df["flags"] = ""
            err_df.loc[err_df["status"].isin(["canceled", "stall"]), "flags"] += "usb_error "
            err_df.loc[err_df["delta_ms"].fillna(0) > 1000.0, "flags"] += "long_gap "
            err_df.loc[err_df["repeat_run"] > 1, "flags"] += "repeated "

            err_view, err_trimmed = _cap_df(err_df, table_row_cap)
            if err_trimmed:
                st.caption(f"UI 僅顯示前 {table_row_cap} 列錯誤。")

            st.dataframe(
                err_view[["txn_id", "time_text", "direction", "request", "wValue", "status", "delta_ms", "repeat_run", "flags", "note"]],
                use_container_width=True,
                hide_index=True,
            )

            repeat_pattern = (
                txn_df[txn_df["repeat_run"] > 1]
                .groupby(["direction", "request", "wValue", "status"], as_index=False)
                .size()
                .sort_values("size", ascending=False)
            )
            st.markdown("#### 重複模式")
            if repeat_pattern.empty:
                st.success("沒有偵測到重複命令模式。")
            else:
                repeat_view, repeat_trimmed = _cap_df(repeat_pattern, table_row_cap)
                if repeat_trimmed:
                    st.caption(f"UI 僅顯示前 {table_row_cap} 列重複模式。")
                st.dataframe(repeat_view, use_container_width=True, hide_index=True)

    with tab4:
        if not correlation_ready:
            st.markdown("### 尚未開始 USB ↔ I2C correlation")
            lines = []
            if saleae_mode == "sal" and saleae_info and saleae_info.ok:
                lines.append(f"- 已讀到 .sal metadata: analyzers={saleae_info.analyzers or ['none']}")
                lines.append(f"- Capture start: {saleae_info.capture_start_local or 'unknown'}")
            lines.append("- 下一步：請從 Saleae Logic 2 匯出 I2C Analyzer CSV 後上傳")
            st.markdown("\n".join(lines))
            _render_saleae_export_guide(saleae_mode, saleae_info, saleae_text, i2c_events, sal_auto_csv_text)
        else:
            st.success("比對已啟用")
            corr_df = txn_df.merge(match_df, left_on="txn_id", right_on="usb_txn_id", how="left")
            if perf_mode:
                corr_df["unmatched_reason"] = corr_df["matched_i2c_count"].fillna(0).apply(
                    lambda c: "" if c > 0 else "視窗內無 I2C 事件"
                )
            else:
                corr_df["nearest_i2c_delta_ms"] = corr_df["time"].apply(
                    lambda t: _nearest_i2c_delta_ms(t, i2c_events, int(shift_ms))
                )
                corr_df["unmatched_reason"] = corr_df.apply(
                    lambda row: (
                        ""
                        if row.get("matched_i2c_count", 0) and row.get("matched_i2c_count", 0) > 0
                        else (
                            "視窗內無 I2C 事件"
                            if pd.isna(row.get("nearest_i2c_delta_ms"))
                            else f"視窗內無 I2C，最近為 {row['nearest_i2c_delta_ms']:+.3f}ms"
                        )
                    ),
                    axis=1,
                )

            m1, m2, m3 = st.columns(3)
            m1.metric("有 I2C 對應的 USB", int((corr_df["matched_i2c_count"].fillna(0) > 0).sum()))
            m2.metric("無 I2C 對應的 USB", int((corr_df["matched_i2c_count"].fillna(0) == 0).sum()))
            m3.metric("無 USB 對應的 I2C", len(unmatched_i2c_df))

            st.markdown("#### 有 I2C 對應的 USB 交易")
            matched_usb = corr_df[corr_df["matched_i2c_count"].fillna(0) > 0][
                ["txn_id", "time_text", "direction", "request", "wValue", "status", "matched_i2c_count", "first_i2c_time", "last_i2c_time"]
            ]
            if matched_usb.empty:
                st.warning("沒有 USB 交易在視窗內匹配到 I2C 事件。")
            else:
                matched_usb_view, matched_usb_trimmed = _cap_df(matched_usb, table_row_cap)
                if matched_usb_trimmed:
                    st.caption(f"UI 僅顯示前 {table_row_cap} 列已匹配 USB。")
                st.dataframe(matched_usb_view, use_container_width=True, hide_index=True)

            st.markdown("#### 無 I2C 對應的 USB 交易")
            show_usb = corr_df[corr_df["matched_i2c_count"].fillna(0) == 0][
                ["txn_id", "time_text", "direction", "request", "wValue", "status", "unmatched_reason"]
            ]
            show_usb_view, show_usb_trimmed = _cap_df(show_usb, table_row_cap)
            if show_usb_trimmed:
                st.caption(f"UI 僅顯示前 {table_row_cap} 列未匹配 USB。")
            st.dataframe(show_usb_view, use_container_width=True, hide_index=True)

            st.markdown("#### 無 USB 對應的 I2C 事件")
            if unmatched_i2c_df.empty:
                st.success("沒有 I2C 無對應 USB 事件。")
            else:
                unmatched_i2c_view, unmatched_i2c_trimmed = _cap_df(unmatched_i2c_df, table_row_cap)
                if unmatched_i2c_trimmed:
                    st.caption(f"UI 僅顯示前 {table_row_cap} 列未匹配 I2C。")
                st.dataframe(unmatched_i2c_view, use_container_width=True)

    with tab5:
        render_raw_tables = True
        if perf_mode:
            render_raw_tables = st.checkbox("顯示原始資料表（速度較慢）", value=False)

        if not render_raw_tables:
            st.info("效能模式：已略過原始資料表，勾選上方核取方塊可顯示。")
        else:
            st.markdown("#### Bus Hound 事件")
            bus_df = pd.DataFrame(
                [
                    {
                        "time": ev.timestamp,
                        "device": ev.device,
                        "phase": ev.phase,
                        "data": ev.data,
                        "description": ev.description,
                        "delta_us": ev.delta_us,
                        "cmd": ev.cmd,
                    }
                    for ev in bus_events
                ]
            )
            bus_view, bus_trimmed = _cap_df(bus_df, table_row_cap)
            if bus_trimmed:
                st.caption(f"UI 僅顯示前 {table_row_cap} 列 Bus Hound 事件。")
            st.dataframe(bus_view, use_container_width=True, hide_index=True)

            st.markdown("#### Saleae I2C 原始資料")
            i2c_df = pd.DataFrame(
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
                    for ev in i2c_events
                ]
            )
            if i2c_df.empty:
                st.info("目前沒有可用的 Saleae I2C 事件。")
            else:
                i2c_view, i2c_trimmed = _cap_df(i2c_df, table_row_cap)
                if i2c_trimmed:
                    st.caption(f"UI 僅顯示前 {table_row_cap} 列 Saleae I2C 資料。")
                st.dataframe(i2c_view, use_container_width=True, hide_index=True)

    if not match_df.empty:
        st.download_button(
            "下載 USB↔I2C 匹配結果 CSV",
            data=match_df.to_csv(index=False).encode("utf-8"),
            file_name="usb_i2c_match_results.csv",
            mime="text/csv",
        )
else:
    st.info("請先上傳 Bus Hound TXT。Saleae .sal / Analyzer CSV 可後續補上以啟用比對功能。")
