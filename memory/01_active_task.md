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
- Native Saleae `.sal` I2C ingress is implemented on `feat/native-saleae-sal-i2c`: validated digital-v2 RLE can be decoded directly and adapted into the existing Analyzer-CSV ingress contract.
- Native `.sal` support is deliberately bounded and fail-closed: ambiguous I2C analyzer selection, malformed digital chunks, missing sample rate, or unvalidated binary versions do not produce guessed I2C events.
- The existing Analyzer CSV path remains the preferred stable/canonical fallback and downstream `SaleaeI2CEvent` / correlation behavior is unchanged.

## Verification

- `tests/test_saleae_sal_native.py`: 4 tests pass locally, covering fixed expected decode, metadata/sample-rate detection, unsupported-version fail-closed behavior, and missing/ambiguous analyzer behavior.
- A private external `.sal` characterization capture was decoded locally and matched the independently inspected I2C sequence invariants; the capture and payloads were not committed.

## Next Steps

- Review and merge the native `.sal` I2C PR if the bounded compatibility policy is accepted.
- Follow up UI wording in `app.py`: some legacy labels still describe `.sal` as metadata-only even though the backend can now supply native I2C events.
- Keep sideband channels (for example INT/power) as a separate follow-up; the current PR only establishes native digital decoding for the existing I2C correlation boundary.
- If native parsing is later enabled for very large `.sal` captures, add an explicit streaming/size policy rather than assuming the current in-memory path scales to multi-GB sessions.
