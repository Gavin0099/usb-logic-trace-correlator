"""Validate the supported input boundary for the correlator."""

from __future__ import annotations

from pathlib import Path

from governance_tools.validator_interface import DomainValidator, ValidatorResult


class SourceBoundaryValidator(DomainValidator):
    """Reject inputs outside the v1 Saleae and Bus Hound contract."""

    SUPPORTED_EXTENSIONS = frozenset({".csv", ".txt"})

    @property
    def rule_ids(self) -> list[str]:
        return ["USB-INPUT-001", "USB-INPUT-002"]

    def validate(self, payload: dict) -> ValidatorResult:
        source_path = str(payload.get("source_path", ""))
        source_kind = str(payload.get("source_kind", "")).strip().lower()
        extension = Path(source_path).suffix.lower()
        violations: list[str] = []

        if extension == ".sal":
            violations.append("USB-INPUT-001: raw Saleae .sal files are outside the v1 input contract")
        elif extension and extension not in self.SUPPORTED_EXTENSIONS:
            violations.append(
                f"USB-INPUT-002: unsupported source extension {extension!r}; expected .csv or .txt"
            )

        if source_kind == "digital_export_csv":
            violations.append(
                "USB-INPUT-002: digital-export CSV is not a valid I2C correlation source"
            )

        return ValidatorResult(
            ok=not violations,
            rule_ids=self.rule_ids,
            violations=violations,
            evidence_summary="Checked the v1 source extension and Saleae source classification boundary",
            metadata={
                "source_path": source_path,
                "source_kind": source_kind,
                "supported_extensions": sorted(self.SUPPORTED_EXTENSIONS),
            },
        )