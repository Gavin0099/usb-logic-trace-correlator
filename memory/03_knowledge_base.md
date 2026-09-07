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

- Native Saleae `.sal` is an internal-format compatibility path, not a stable source contract. The project currently accepts only the digital-v2 binary layout that has been characterized; unknown binary versions must fail closed rather than reuse the same layout by assumption.
- Native digital-v2 decoding uses the `<SALEAE>` header, digital data type `100`, the validated chunk boundary at `0x33`, and run-length varints. Chunk continuity and decoded run coverage are checked before events are trusted.
- At modest digital sample rates, SDA/SCL edges can quantize to adjacent samples. Native I2C START/STOP detection therefore requires the SDA transition to sit inside an SCL-high interval with a small sample guard; this avoids promoting near-SCL-edge transitions into false bus markers.
- The native decoder intentionally adapts decoded frames back into the existing Analyzer-CSV ingress contract. This preserves `SaleaeI2CEvent` and USB↔I2C correlation behavior instead of creating a second downstream data model.
- Analyzer CSV remains the preferred stable fallback. Raw `.sal` decode should never be described as complete support for all Saleae versions or analyzer types.

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
- `src/usb_logic_trace_correlator/saleae_sal.py` — `.sal` metadata/embedded-CSV bridge and native decode fallback
- `src/usb_logic_trace_correlator/saleae_sal_native.py` — bounded native Saleae digital-v2 → I2C decoder
- `src/usb_logic_trace_correlator/compare.py` — USB↔I2C correlation
## 將 AI Governance framework 1.3.0 完整導入 usb-logic-trace-correlator repository。
- Captured: 2026-09-07T03:18:27.671642+00:00
- Approved by: governance-auto
- Risk: low
- Oversight: auto
- Summary: 將 AI Governance framework 1.3.0 完整導入 usb-logic-trace-correlator repository。
