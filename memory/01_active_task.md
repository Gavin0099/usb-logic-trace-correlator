# Active Task

## Current Status

- Qt desktop deliverable stabilized on Windows using onedir packaging.
- Recommended exe: `dist/usb-logic-trace-correlator-qt-app/usb-logic-trace-correlator-qt-app.exe`.
- Large-file streaming mode added: `app.py` uses `_parse_bushound_stream` / `_parse_saleae_stream` with `max_events` cap.
- Performance mode added: limits table rendering and skips expensive per-row I2C scan.
- Upload limit raised to 4 GB via `.streamlit/config.toml` AND `--server.maxUploadSize 4096` CLI arg in `qt_desktop.py`.
- Full Traditional Chinese UI: all labels, tabs, captions translated.
- `match_df` column rename: `status` → `match_status` to avoid pandas merge column collision with `txn_df.status`.
- Correlation tab now shows three sections: matched USB↔I2C / unmatched USB / unmatched I2C.

## Next Steps

- No known blockers.
- If CSV parse is still slow for 400 MB+ files, consider chunked pandas read instead of line-by-line.
- Keep `dist/` and `build/` out of git (add `.gitignore`).
