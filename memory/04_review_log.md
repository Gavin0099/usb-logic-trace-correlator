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

<!-- memory_record_projection:review-log:3e7de3f4cbb59f7aa78d7708ecafafc71f13ade8aa41f99470786c6ba390d05d -->
### Canonical memory checkpoint — copilot-20260907-governance-adoption

- Writer: `governance_tools.memory_record`
- Record identity: `3e7de3f4cbb59f7aa78d7708ecafafc71f13ade8aa41f99470786c6ba390d05d`
- Commit binding: `UNCOMMITTED` (unbound)
- Record: 完成 AI Governance 1.3.0 external_contract_repo 導入：官方 F-7、hooks、Copilot lifecycle、canonical governance docs、Plan metadata、contract validator、runtime version manifest；readiness 與 drift 通過。
- Validation boundary: artifacts/evidence/test-results/governance-readiness-final.json (exit_code=0); external_repo_readiness ready=True; governance_drift_checker ok=True; quickstart_smoke ok=True; governance_version_check verdict=compatible; runtime_surface_manifest_smoke ok=True
- Next action: 取得授權後提交本次治理檔案，以解除 framework lock consistency 的未提交狀態。
- PLAN reconciliation: `updated`
## Promotion: 將 AI Governance framework 1.3.0 完整導入 usb-logic-trace-correlator repository。
- Approved by: governance-auto
- Candidate: E:\BackUp\Git_EE\usb-logic-trace-correlator\memory\candidates\session_20260907T031827Z.json
- Risk: low
- Oversight: auto


<!-- memory_record_projection:review-log:b1e2bde664dc7a4e964113a6f64d52a6cc54d8311ba58bf22f3ed671145195c3 -->
### Canonical memory checkpoint — copilot-20260907-governance-validation-20260907

- Writer: `governance_tools.memory_record`
- Record identity: `b1e2bde664dc7a4e964113a6f64d52a6cc54d8311ba58bf22f3ed671145195c3`
- Commit binding: `UNCOMMITTED` (unbound)
- Record: Governance 1.3.0 validation refreshed: version, drift, readiness, hooks, quickstart, framework runtime-surface, and memory guard checks pass; framework lock remains uncommitted and application changes remain out of scope.
- Validation boundary: artifacts/evidence/test-results/governance-readiness-final.json; governance_version_check compatible; governance_drift_checker ok; external_repo_readiness ready; quickstart ok; runtime_surface_manifest_smoke ok; memory_workflow guard ran
- Next action: Obtain owner authorization before staging governance files; then commit scoped governance changes and rerun lock and readiness checks.
- PLAN reconciliation: `updated`
