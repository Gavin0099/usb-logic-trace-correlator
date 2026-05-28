# USB Bus Hound vs Saleae 比對工具 (GUI)

這個工具用來直接比較兩種來源的 log：

- Bus Hound `.txt`
- Saleae `.sal`（先讀 metadata）
- Saleae Logic 匯出的 I2C Analyzer `.csv`（正式比對）

重點是快速找出「不一樣的地方」：

- 哪些 USB transaction 沒有對應的 I2C 事件
- 哪些 I2C 事件沒有對應的 USB transaction
- USB 端是否有 `stall`、`canceled` 等異常狀態

## 安裝

```powershell
pip install -r requirements.txt
```

## 啟動 GUI

```powershell
streamlit run app.py
```

## 使用方式

1. 上傳 Bus Hound TXT。
2. 上傳 Saleae Source：可以是 `.sal` 或 I2C CSV。
3. 如果上傳 `.sal`，再上傳 Saleae Analyzer 匯出 CSV。
4. 如果 Saleae CSV 是相對時間，填入 Capture Start 時間（或讓 .sal metadata 自動帶入）。
5. 依實際情況調整：
   - `I2C 時間偏移 (ms)`
   - `匹配視窗 (ms)`
6. 查看三個重點頁籤：
   - `USB 無對應 I2C`
   - `I2C 無對應 USB`
   - `全部 USB Transaction`

## 注意

- `.sal` 目前只用來讀 metadata；事件解析仍以 Saleae 匯出的 Analyzer CSV 為主。
- 目前 Saleae 端先以 I2C CSV 為主；SPI/UART 可後續擴充。
