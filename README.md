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

## Build Windows 執行檔

目前只建議執行這個穩定版：

```text
dist/usb-logic-trace-correlator-qt-app/usb-logic-trace-correlator-qt-app.exe
```

其他 `dist/` 產物都是歷史測試版、除錯版或舊封裝版，先不要優先使用。

```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --name usb-logic-trace-correlator launcher.py --add-data "app.py;." --add-data "src;src"
```

輸出執行檔：

```text
dist/usb-logic-trace-correlator.exe
```

啟動後會開啟本機 Streamlit 服務（預設 8501），可用瀏覽器開：

```text
http://localhost:8501
```

## Build 真正桌面視窗版（內嵌 WebView）

這一版會開啟原生桌面視窗，不需要手動開瀏覽器。

```powershell
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name usb-logic-trace-correlator-desktop desktop_launcher.py --add-data "app.py;." --add-data "src;src" --copy-metadata streamlit --copy-metadata pywebview
```

輸出執行檔：

```text
dist/usb-logic-trace-correlator-desktop.exe
```

## Build Qt 桌面版（推薦）

這一版使用 Qt WebEngine 內嵌視窗，作為原生桌面 GUI。

注意：正式交付時請以 onedir 版為準，不要優先跑 onefile 版。

```powershell
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --onedir --name usb-logic-trace-correlator-qt-app qt_desktop.py --add-data "app.py;." --add-data "src;src" --collect-all streamlit
```

輸出執行檔：

```text
dist/usb-logic-trace-correlator-qt-app/usb-logic-trace-correlator-qt-app.exe
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
- 如果 Bus Hound TXT 或 Saleae CSV 已經到數百 MB 以上，建議開啟 Large file mode，讓工具改走 streaming parse + row cap，避免每次 rerun 都重做完整載入。
- 如果 trace log 未來會到幾 GB，這個 GUI 仍建議搭配時間窗或分段輸出使用，不要一次全量匯入。
- 上傳上限由 `.streamlit/config.toml` 控制，目前設定為 `4096 MB`。如需更大可再調整 `server.maxUploadSize` 與 `server.maxMessageSize`。
