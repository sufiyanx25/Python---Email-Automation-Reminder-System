"""
report_generator.py
-------------------
Generates execution audit reports:
- Records outcomes (SIMULATED, SENT, FAILED, SKIPPED)
- Captures recipient name, email, subject, reminder date/time, status, timestamp, and error message
- Saves summary CSV reports into the outputs/ directory
- Provides Pandas DataFrame integration for Streamlit dashboard and direct CSV download
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from src.logger import logger


class ReportGenerator:
    """Manages dispatch result logging and CSV audit report exports."""

    COLUMNS = [
        "recipient_name",
        "recipient_email",
        "subject",
        "reminder_date_time",
        "status",
        "timestamp",
        "error_message"
    ]

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.records: List[Dict[str, Any]] = []

    def record_result(
        self,
        recipient_name: str,
        recipient_email: str,
        subject: str,
        reminder_date_time: str,
        status: str,
        error_message: str = ""
    ) -> Dict[str, Any]:
        """
        Records the outcome of an individual reminder dispatch attempt.

        Args:
            recipient_name: Contact name.
            recipient_email: Contact email address.
            subject: Email subject.
            reminder_date_time: Scheduled reminder date/time string.
            status: Status code (e.g., 'SIMULATED', 'SENT', 'FAILED', 'SKIPPED').
            error_message: Optional error message or explanation.

        Returns:
            Dict[str, Any]: The recorded dictionary entry.
        """
        entry = {
            "recipient_name": recipient_name or "Valued Contact",
            "recipient_email": recipient_email,
            "subject": subject,
            "reminder_date_time": reminder_date_time,
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_message": error_message
        }
        self.records.append(entry)
        logger.info(
            f"[AUDIT RECORD] {recipient_email} | Status: {status} | "
            f"Subject: '{subject}' {f'| Error: {error_message}' if error_message else ''}"
        )
        return entry

    def to_dataframe(self) -> pd.DataFrame:
        """Converts in-memory execution records into a Pandas DataFrame."""
        if not self.records:
            return pd.DataFrame(columns=self.COLUMNS)
        return pd.DataFrame(self.records)

    def export_csv(self, filename: Optional[str] = None) -> Path:
        """
        Writes all recorded results into a CSV report in outputs/.

        Args:
            filename: Target CSV filename (default: timestamped name).

        Returns:
            Path: Path to the generated CSV file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"execution_report_{timestamp}.csv"

        report_path = self.output_dir / filename
        df = self.to_dataframe()

        df.to_csv(report_path, index=False, encoding="utf-8")
        logger.info(f"Execution report successfully generated at: {report_path}")
        return report_path

    def get_summary_counts(self) -> Dict[str, int]:
        """Returns summary counts of statuses in current run."""
        if not self.records:
            return {"total": 0, "simulated": 0, "sent": 0, "failed": 0, "skipped": 0}

        df = self.to_dataframe()
        status_counts = df["status"].value_counts().to_dict()
        return {
            "total": len(df),
            "simulated": status_counts.get("SIMULATED", 0),
            "sent": status_counts.get("SENT", 0),
            "failed": status_counts.get("FAILED", 0),
            "skipped": sum(count for status, count in status_counts.items() if status.startswith("SKIPPED"))
        }
