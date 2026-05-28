# Knowledge Base

## Gotchas

- Symptom: Qt app opens but embedded page shows `Not Found`, while `/_stcore/health` still returns `200`.
- Root cause: Streamlit frontend static assets were missing from the packaged Qt onedir output.
- Reliable fix: build Qt onedir with Streamlit full collection via `usb-logic-trace-correlator-qt-app.spec`.

- Symptom: `KeyError: ['status'] not in index` after CSV load in Correlation tab.
- Root cause: `match_df` and `txn_df` both had a `status` column; pandas merge renamed them to `status_x`/`status_y`.
- Fix: rename `match_df`'s status column to `match_status` before merge.

- Symptom: `failed to start embedded python interpreter` on exe launch.
- Root cause: `.streamlit/config.toml` was not included in PyInstaller spec `datas`.
- Fix: add `('.streamlit', '.streamlit')` to `datas` in spec; also pass `--server.maxUploadSize 4096` as CLI arg in `qt_desktop.py` so config is not path-dependent.

- Symptom: 48MB Bus Hound TXT + 468MB Saleae CSV causes memory pressure and slow UI.
- Fix: large-file mode streams parse + caps rows; performance mode skips expensive per-row I2C scan and timeline.

## Build Command

```powershell
taskkill /IM usb-logic-trace-correlator-qt-app.exe /F
Remove-Item -Recurse -Force .\dist\usb-logic-trace-correlator-qt-app
pyinstaller --noconfirm --clean usb-logic-trace-correlator-qt-app.spec
```

## Key Files

- `app.py` — Streamlit UI, all parsing, correlation, Chinese labels
- `qt_desktop.py` — Qt entry point, launches Streamlit with CLI args
- `usb-logic-trace-correlator-qt-app.spec` — PyInstaller spec (onedir, windowed)
- `.streamlit/config.toml` — upload size limits (also passed via CLI args)
- `src/usb_logic_trace_correlator/bushound.py` — Bus Hound TXT parser
- `src/usb_logic_trace_correlator/saleae.py` — Saleae I2C CSV parser
- `src/usb_logic_trace_correlator/compare.py` — USB↔I2C correlation
