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
- AI Governance framework nested checkout is at `1.3.0` / `10044277b99e68973130d23ce97697418de59d21`, and the parent lock value matches that working-tree HEAD. Official F-7 audit status is `partial`: the parent is not a registered submodule consumer, the lock is uncommitted, repo-specific AGENTS rules and validators are missing, and runtime/hooks remain unverified.

## Next Steps

- No known blockers.
- If CSV parse is still slow for 400 MB+ files, consider chunked pandas read instead of line-by-line.
- Keep `dist/` and `build/` out of git (add `.gitignore`).

- Governance 1.3.0 surfaces are installed and validated; framework lock remains uncommitted pending owner authorization. <!-- memory_record_projection:active-task-summary:3e7de3f4cbb59f7aa78d7708ecafafc71f13ade8aa41f99470786c6ba390d05d -->
- [x] Promoted memory: 將 AI Governance framework 1.3.0 完整導入 usb-logic-trace-correlator repository。

- Governance 1.3.0 validation refreshed: version, drift, readiness, hooks, quickstart, framework runtime-surface, and memory guard checks pass; framework lock remains uncommitted and application changes remain out of scope. <!-- memory_record_projection:active-task-summary:b1e2bde664dc7a4e964113a6f64d52a6cc54d8311ba58bf22f3ed671145195c3 -->
