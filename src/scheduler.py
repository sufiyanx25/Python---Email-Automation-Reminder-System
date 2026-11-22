"""
scheduler.py
------------
Manages reminder loading, scheduling, recurrence, and duplicate prevention.
- Parses dates and evaluates schedules using Asia/Kolkata timezone.
- Identifies due reminders and upcoming reminders.
- Supports one-time and recurring (daily, weekly) schedules.
- Prevents duplicate dispatches using an execution history tracker.
- Integrates with the `schedule` library for continuous job execution.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import pytz
import schedule

from src.logger import logger
from src.contact_manager import ContactManager

# Default project timezone
TIMEZONE_NAME = "Asia/Kolkata"
try:
    LOCAL_TZ = pytz.timezone(TIMEZONE_NAME)
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=5, minutes=30))


def get_current_time() -> datetime:
    """Returns the current aware datetime in Asia/Kolkata timezone."""
    try:
        return datetime.now(LOCAL_TZ)
    except Exception:
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))


class ProcessedTracker:
    """
    Tracks executed reminder IDs and dates to prevent duplicate email sending.
    Persists state in outputs/processed_reminders.json.
    """

    def __init__(self, storage_path: str = "outputs/processed_reminders.json"):
        self.storage_path = Path(storage_path)
        self.processed: Dict[str, List[str]] = {}
        self.load()

    def load(self):
        """Loads processed reminder records from file."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.processed = data if isinstance(data, dict) else {}
            except Exception as e:
                logger.warning(f"Could not load duplicate tracker file: {e}. Starting fresh.")
                self.processed = {}
        else:
            self.processed = {}

    def save(self):
        """Saves processed reminder records to file."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(self.processed, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not save duplicate tracker file: {e}")

    def is_already_processed(self, reminder_id: str, frequency: str, target_dt: datetime) -> bool:
        """
        Determines if a reminder has already been processed based on its recurrence rule.

        - One-time: Processed if reminder_id exists in history.
        - Daily: Processed if executed on the same date (YYYY-MM-DD).
        - Weekly: Processed if executed in the same calendar week (YYYY-WW).
        """
        exec_dates = self.processed.get(reminder_id, [])
        if not exec_dates:
            return False

        freq = (frequency or "one-time").strip().lower()

        if freq == "one-time":
            return len(exec_dates) > 0

        target_date_str = target_dt.strftime("%Y-%m-%d")

        if freq == "daily":
            return any(d.startswith(target_date_str) for d in exec_dates)

        if freq == "weekly":
            target_year, target_week, _ = target_dt.isocalendar()
            for d in exec_dates:
                try:
                    dt_rec = datetime.fromisoformat(d)
                    y, w, _ = dt_rec.isocalendar()
                    if y == target_year and w == target_week:
                        return True
                except Exception:
                    pass
            return False

        # Default fallback
        return len(exec_dates) > 0

    def mark_processed(self, reminder_id: str, executed_dt: Optional[datetime] = None):
        """Records an execution timestamp for the reminder."""
        if executed_dt is None:
            executed_dt = get_current_time()
        timestamp_str = executed_dt.isoformat()

        if reminder_id not in self.processed:
            self.processed[reminder_id] = []
        self.processed[reminder_id].append(timestamp_str)
        self.save()

    def reset(self):
        """Resets in-memory tracker and persistent state (useful for test runs)."""
        self.processed = {}
        self.save()


class ReminderScheduler:
    """Manages reminder datasets, date evaluation, and schedule triggers."""

    def __init__(
        self,
        filepath: str = "data/reminders.csv",
        tracker_path: str = "outputs/processed_reminders.json"
    ):
        self.filepath = Path(filepath)
        self.tracker = ProcessedTracker(storage_path=tracker_path)
        self.reminders_df = pd.DataFrame()
        self.load_reminders()

    def parse_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Parses a date/time string and localizes it to Asia/Kolkata timezone.
        Supports formats: 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DD HH:MM', 'YYYY-MM-DD'.
        """
        if not date_str or not isinstance(date_str, str):
            return None

        clean_str = date_str.strip()
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d-%m-%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S"
        ]

        for fmt in formats:
            try:
                naive_dt = datetime.strptime(clean_str, fmt)
                # Localize to Asia/Kolkata
                if hasattr(LOCAL_TZ, "localize"):
                    return LOCAL_TZ.localize(naive_dt)
                return naive_dt.replace(tzinfo=LOCAL_TZ)
            except ValueError:
                continue

        logger.warning(f"Failed to parse datetime string: '{date_str}'")
        return None

    def load_reminders(self) -> pd.DataFrame:
        """
        Reads reminders CSV with Pandas, parses dates, normalizes columns,
        and annotates records with due/completed status.
        """
        if not self.filepath.exists():
            logger.error(f"Reminders file not found at: {self.filepath}")
            self.reminders_df = pd.DataFrame(
                columns=["id", "recipient_email", "subject", "message", "scheduled_time", "frequency", "status"]
            )
            return self.reminders_df

        try:
            df = pd.read_csv(self.filepath, dtype=str)
        except Exception as e:
            logger.error(f"Error reading reminders file {self.filepath}: {e}")
            return pd.DataFrame()

        # Normalize column names
        df.columns = [col.strip().lower() for col in df.columns]

        # Generate IDs if missing or empty
        cleaned_ids = []
        if "id" not in df.columns:
            cleaned_ids = [f"REM-{i+1:03d}" for i in range(len(df))]
        else:
            for idx, val in enumerate(df["id"]):
                s_val = str(val).strip() if pd.notna(val) else ""
                cleaned_ids.append(s_val if s_val else f"REM-{idx+1:03d}")
        df["id"] = cleaned_ids

        if "frequency" not in df.columns:
            df["frequency"] = "one-time"
        else:
            df["frequency"] = df["frequency"].fillna("one-time").str.strip().str.lower()

        now = get_current_time()
        status_list = []
        parsed_dt_list = []

        for _, row in df.iterrows():
            rem_id = row.get("id", "")
            raw_time = row.get("scheduled_time", "")
            freq = row.get("frequency", "one-time")
            parsed_dt = self.parse_datetime(raw_time)
            parsed_dt_list.append(parsed_dt)

            if parsed_dt is None:
                status_list.append("Invalid Date")
                continue

            # Check duplicate / processed tracker
            already_done = self.tracker.is_already_processed(rem_id, freq, now)

            if already_done:
                status_list.append("Completed")
            elif parsed_dt <= now:
                status_list.append("Due")
            else:
                status_list.append("Upcoming")

        df["parsed_dt"] = parsed_dt_list
        df["status"] = status_list
        self.reminders_df = df
        logger.info(
            f"Loaded {len(df)} reminders: "
            f"{status_list.count('Due')} Due, "
            f"{status_list.count('Upcoming')} Upcoming, "
            f"{status_list.count('Completed')} Completed."
        )
        return self.reminders_df

    def get_due_reminders(self) -> List[Dict[str, Any]]:
        """Returns all reminders that are currently due and not yet processed."""
        # Refresh statuses against current time
        self.load_reminders()
        due_df = self.reminders_df[self.reminders_df["status"] == "Due"]
        return due_df.to_dict(orient="records")

    def get_upcoming_reminders(self) -> List[Dict[str, Any]]:
        """Returns all reminders scheduled for future dates."""
        self.load_reminders()
        upcoming_df = self.reminders_df[self.reminders_df["status"] == "Upcoming"]
        return upcoming_df.to_dict(orient="records")

    def get_summary(self) -> Dict[str, int]:
        """Provides counts of total, due, upcoming, and completed reminders."""
        self.load_reminders()
        statuses = self.reminders_df["status"].tolist() if "status" in self.reminders_df else []
        return {
            "total": len(self.reminders_df),
            "due": statuses.count("Due"),
            "upcoming": statuses.count("Upcoming"),
            "completed": statuses.count("Completed"),
            "invalid": statuses.count("Invalid Date")
        }

    def run_scheduler_tick(self, process_callback) -> int:
        """
        Executes one evaluation cycle for due reminders, invoking callback for each.
        Returns the number of processed reminders.
        """
        due_items = self.get_due_reminders()
        if not due_items:
            logger.info("Scheduler tick: No due reminders at this time.")
            return 0

        logger.info(f"Scheduler tick: Processing {len(due_items)} due reminder(s)...")
        count = 0
        for item in due_items:
            rem_id = item.get("id", "")
            process_callback(item)
            # Mark processed to prevent duplicate runs
            self.tracker.mark_processed(rem_id, get_current_time())
            count += 1

        # Reload status after processing
        self.load_reminders()
        return count
