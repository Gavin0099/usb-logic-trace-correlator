PLAN：USB + Saleae Log Parse Tool
目標定義

建立一個工具，可以讀取：

Bus Hound txt log
Saleae Logic exported analyzer result

轉成共同格式後，產生：

USB command timeline
Saleae bus event timeline
USB ↔ I2C/SPI/UART correlation report
Vendor command transaction summary
Error / timeout / stall summary
Phase 0：先界定工具邊界
先不要做的事

這點很重要。

第一版不要直接 parse .sal raw file 當正式功能。

原因是 .sal 是 Saleae 內部格式，不適合長期依賴。比較穩的是：

.sal
  ↓ Saleae Logic 2 export
I2C/SPI/UART CSV
  ↓ parser
normalized timeline

所以第一版工具應該支援：

Bus Hound .txt
Saleae Analyzer Export .csv / .txt

而不是直接承諾完整支援 .sal。

Phase 1：建立 Repo 骨架

建議用 Python 起步，因為 parser / timeline / CSV / JSON 很快。

usb-logic-trace-correlator/
  README.md
  pyproject.toml
  src/
    usb_logic_trace_correlator/
      __init__.py
      cli.py
      models.py
      parsers/
        __init__.py
        bushound_txt.py
        saleae_i2c_csv.py
      normalize/
        usb_control.py
        timeline.py
      correlate/
        time_align.py
        matcher.py
      exporters/
        json_exporter.py
        csv_exporter.py
        markdown_report.py
  tests/
    fixtures/
      bushound_lenovo_p27u.txt
      saleae_i2c_sample.csv
    test_bushound_parser.py
    test_usb_transaction_grouping.py
    test_saleae_i2c_parser.py
    test_time_alignment.py
Phase 2：Bus Hound TXT Parser
目標

把 Bus Hound txt 解析成 structured event。

輸入：

76.0            CTL    40 ab 6f94 0000 0001    VENDOR REQ ab ...
76.0         1  OUT    80                      ...
76.0            CTL    c0 aa 6f94 0000 0001    VENDOR REQ aa ...
76.0         1  IN     92                      ...

輸出：

{
  "source": "bushound",
  "timestamp": "2026-05-28T09:56:39.658",
  "device": "76.0",
  "phase": "CTL",
  "data": "40 ab 6f94 0000 0001",
  "description": "VENDOR REQ ab",
  "delta": "7.1s",
  "cmd": "5.1.0"
}
需要處理的欄位
Device
Length
Phase
Data
Description
Delta
Cmd.Phase.Ofs(rep)
Date
Time
驗收條件

你的這份 Bus Hound txt 可以正確解析出：

CTL / IN / OUT / USTS
vendor request
data payload
timestamp
status error: canceled / stall pid
Phase 3：USB Control Transfer Grouping

這是工具價值開始出來的地方。

Bus Hound 原始資料是一列一列，但 USB control transfer 應該要 group 成 transaction。

例如

原始：

CTL 40 ab 6f94 0000 0001
OUT 80

轉成：

{
  "type": "usb_control_transfer",
  "direction": "host_to_device",
  "bmRequestType": "0x40",
  "bRequest": "0xab",
  "wValue": "0x6f94",
  "wIndex": "0x0000",
  "wLength": 1,
  "data_phase": {
    "direction": "OUT",
    "payload": ["0x80"]
  },
  "status": "ok"
}

另一種：

CTL c0 aa 6f94 0000 0001
IN 92

轉成：

{
  "type": "usb_control_transfer",
  "direction": "device_to_host",
  "bmRequestType": "0xc0",
  "bRequest": "0xaa",
  "wValue": "0x6f94",
  "wIndex": "0x0000",
  "wLength": 1,
  "data_phase": {
    "direction": "IN",
    "payload": ["0x92"]
  },
  "status": "ok"
}
特別要抓
USTS canceled
USTS stall pid
timeout-like gap
repeat count

這些對 debug 很有價值。

Phase 4：Saleae Analyzer Export Parser
第一版支援 I2C

因為你的 .sal 裡面是 I2C analyzer，所以第一版先做 I2C 最合理。

工具預期使用流程：

Saleae Logic 2
  → Export Analyzer Results
  → I2C CSV
  → saleae_i2c_csv parser

輸出共同格式：

{
  "source": "saleae",
  "protocol": "i2c",
  "timestamp_offset_sec": 3.124677,
  "address": "0x50",
  "rw": "write",
  "data": ["0x01", "0x02", "0x03"],
  "ack": true
}
先不要過度假設

Saleae 匯出的 CSV 格式可能依 analyzer 類型、版本、欄位設定不同而變。
所以 parser 要保留：

raw_row
parser_version
unsupported_fields

不要一開始就把欄位寫死到無法擴充。

Phase 5：共同資料模型

建立 internal normalized model。

TraceEvent
@dataclass
class TraceEvent:
    source: str
    timestamp_abs: datetime | None
    timestamp_offset_sec: float | None
    event_type: str
    protocol: str
    summary: str
    raw: dict
UsbControlTransfer
@dataclass
class UsbControlTransfer:
    timestamp_abs: datetime
    device: str
    bm_request_type: int
    b_request: int
    w_value: int
    w_index: int
    w_length: int
    data_direction: str
    payload: bytes | None
    status: str
SaleaeBusEvent
@dataclass
class SaleaeBusEvent:
    timestamp_offset_sec: float
    protocol: str
    address: int | None
    rw: str | None
    payload: bytes
    ack: bool | None
Phase 6：時間對齊

這是最核心的功能。

問題

Bus Hound 有 absolute timestamp：

2026-05-28 09:56:39.658

Saleae 可能有：

capture start time
relative sample time

所以要支援兩種對齊方式。

對齊模式
Mode A：使用 Saleae captureStartTime
saleae_abs_time = capture_start_time + timestamp_offset_sec
Mode B：手動指定 offset
tracecorr correlate \
  --bushound Lenovo_P27u.txt \
  --saleae saleae_i2c.csv \
  --saleae-start "2026-05-28T09:56:36.380+08:00"
Mode C：anchor event 對齊

如果兩邊時間不準，可以指定 anchor：

tracecorr correlate \
  --usb-anchor "2026-05-28T09:56:39.658" \
  --saleae-anchor 3.278

這個很重要，因為實務上 PC log 時間與 logic analyzer 時間未必完全準。

Phase 7：Correlation Report

輸出幾種報告。

1. Combined Timeline
09:56:39.658  USB  WRITE  bRequest=ab wValue=6f94 data=80
09:56:39.673  USB  READ   bRequest=aa wValue=6f94 data=92
09:56:39.681  I2C  WRITE  addr=0x50 data=...
09:56:45.799  USB  USTS   canceled
09:56:45.833  USB  ERROR  stall pid
2. USB Vendor Command Summary
bRequest=ab
  count: 101
  direction: OUT
  common wValue:
    0x6094
    0x6194
    0x6f94

bRequest=aa
  count: 31
  direction: IN
  common wValue:
    0x6f94
    0x6094
    0xf594
3. Error Summary
canceled:
  count: 2
  related command: 40 ab 7094 0000 0100
  delay: 6.0s

stall pid:
  count: 2
  related command: c0 d8 0000 0000 000a
4. Windowed Correlation

例如：

For each USB command, show Saleae events within +0ms ~ +50ms

輸出：

USB 09:56:39.658  WRITE ab 6f94 = 80
  +1.2ms  I2C WRITE addr=0x50 data=...
  +2.1ms  I2C READ  addr=0x50 data=...
Phase 8：CLI 設計

建議 CLI 名稱可以短一點：

tracecorr
指令
Parse Bus Hound
tracecorr parse-bushound Lenovo_P27u.txt --out bushound.json
Parse Saleae I2C CSV
tracecorr parse-saleae-i2c saleae_i2c.csv --out saleae.json
Correlate
tracecorr correlate \
  --bushound Lenovo_P27u.txt \
  --saleae-i2c saleae_i2c.csv \
  --saleae-start "2026-05-28T09:56:36.380+08:00" \
  --out report.md
Summary
tracecorr summarize-bushound Lenovo_P27u.txt
Phase 9：測試策略
必要測試
Bus Hound header detection
Bus Hound row parsing
CTL setup packet parsing
CTL + OUT grouping
CTL + IN grouping
CTL + USTS grouping
repeated command handling
delta time parsing
absolute timestamp parsing
Saleae CSV column detection
time alignment
correlation window matching
Fixture

把你的兩個檔案拆成小型 sample，不要整包都放測試。

tests/fixtures/
  bushound_small.txt
  bushound_error_case.txt
  saleae_i2c_small.csv
Phase 10：後續擴充
V2 可以加入
USBPcap support
Wireshark PDML / JSON support
Total Phase Beagle CSV
Saleae SPI / UART analyzer export
vendor command decoder plugin
register map annotation
HTML timeline viewer
Decoder Plugin

這會很適合你們公司內部使用。

例如：

vendor_decoders:
  - request: 0xab
    name: "vendor_write_register"
    wValue: "register_address"
    data: "register_value"

  - request: 0xaa
    name: "vendor_read_register"
    wValue: "register_address"
    response: "register_value"

這樣報告可以從：

USB WRITE ab 6f94 = 80

升級成：

WRITE_REG 0x946f = 0x80

這對 reverse command flow 很有幫助。

我建議的實作順序
Sprint 1：Bus Hound 可用
[ ] 建 repo
[ ] parse Bus Hound txt
[ ] output JSON / CSV
[ ] group USB control transfer
[ ] summary command count
[ ] error summary

這階段就已經有用。

Sprint 2：Saleae 匯出資料接入
[ ] 定義 Saleae I2C CSV parser
[ ] 支援 timestamp offset
[ ] 支援 capture start time
[ ] normalized Saleae events
Sprint 3：Timeline correlation
[ ] USB absolute time
[ ] Saleae absolute time
[ ] window matching
[ ] combined timeline markdown
[ ] per-command nearby bus event report
Sprint 4：Decoder / Annotation
[ ] vendor command YAML
[ ] register map YAML
[ ] decode bRequest aa / ab
[ ] readable report
最小可交付版本定義

我會把 MVP 定成：

Given:
  Bus Hound txt
  Saleae I2C CSV
  Saleae capture start time

Tool can produce:
  1. usb_transactions.json
  2. saleae_events.json
  3. combined_timeline.csv
  4. report.md

MVP 不承諾：

直接完整解析 .sal raw format
自動判斷所有 vendor command 語意
自動反推 register map
GUI