"""Структурированный отчёт о качестве входных выгрузок."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    count: int = 1
    supplier: str | None = None


@dataclass(slots=True)
class DataQualityReport:
    """Наблюдаемые метрики отдельно от интерпретации и рисков."""

    files: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[QualityIssue] = field(default_factory=list)

    def add_issue(
        self,
        code: str,
        severity: Literal["info", "warning", "error"],
        message: str,
        *,
        count: int = 1,
        supplier: str | None = None,
    ) -> None:
        if count > 0:
            self.issues.append(QualityIssue(code, severity, message, count, supplier))

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "metrics": self.metrics,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def write_json(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def write_markdown(self, path: Path) -> None:
        lines: list[str] = [
            "# Отчёт о качестве данных",
            "",
            "Отчёт сформирован без изменения исходных Excel-файлов.",
            "",
            "## Покрытие",
            "",
        ]
        for key, value in sorted(self.metrics.items()):
            rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
            lines.append(f"- `{key}`: {rendered}")

        lines.extend(["", "## Риски и ограничения", ""])
        if not self.issues:
            lines.append("Критичных проблем не обнаружено.")
        for issue in self.issues:
            supplier = f" [{issue.supplier}]" if issue.supplier else ""
            lines.append(
                f"- **{issue.severity.upper()} `{issue.code}`{supplier}:** "
                f"{issue.message} (строк/значений: {issue.count})"
            )

        lines.extend(["", "## Файлы", ""])
        lines.extend(f"- `{name}`" for name in self.files)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
