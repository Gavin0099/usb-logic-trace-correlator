# Review Log

## Entries

- 2026-05-28 Qt packaging + runtime validation
	- Reproduced failure: `curl -i http://127.0.0.1:8501/` returned `HTTP/1.1 404 Not Found` while health endpoint was `200`.
	- Rebuild action: Qt onedir packaging with `--collect-all streamlit`.
	- Post-fix checks:
		- `curl -i http://127.0.0.1:8501/` returned `HTTP/1.1 200 OK`.
		- Response body contained Streamlit `index.html` with `static/js` and `static/css` links.
		- `http://127.0.0.1:8501/_stcore/health` returned `200`.

- 2026-05-28 large-file performance pass
	- Identified the main slowdown as full-stream reruns plus quadratic USB-to-I2C matching.
	- Applied linear sliding-window matching in `src/usb_logic_trace_correlator/compare.py`.
	- Added `st.cache_data` around large Bus Hound and Saleae parsing in `app.py`.
	- Added streaming parse paths (`_parse_bushound_stream`, `_parse_saleae_stream`) with `max_events` cap.
	- Added performance mode and table row cap controls in UI.
	- Validation: `app.py` and `compare.py` both passed workspace error checks after the change.

- 2026-05-28 upload limit + exe startup fix
	- Created `.streamlit/config.toml` (`maxUploadSize = 4096`).
	- Added `.streamlit` to PyInstaller spec `datas`.
	- Added `--server.maxUploadSize 4096` and `--server.maxMessageSize 4096` as CLI args in `qt_desktop.py`.
	- Fixed `KeyError: ['status'] not in index`: renamed `match_df.status` → `match_status` to avoid merge collision.
	- Full Traditional Chinese UI translation.
	- Added "有 I2C 對應的 USB 交易" matched-pairs table in Correlation tab.
