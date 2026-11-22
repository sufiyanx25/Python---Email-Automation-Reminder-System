"""
test_email_system.py
--------------------
Automated unit tests for the Email Automation & Reminder System.

Covers:
1. CSV loading for contacts and reminders
2. Email validation (valid and invalid formats)
3. Template personalization and graceful handling of missing placeholders
4. Date/time parsing and Asia/Kolkata timezone evaluation
5. Dry-run email simulation safety (no SMTP connection)
6. Duplicate reminder prevention and recurrence tracking
7. CSV audit report generation
"""

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
import pytz

from src.contact_manager import ContactManager
from src.email_template import TemplateManager
from src.email_sender import EmailSender
from src.scheduler import ReminderScheduler, ProcessedTracker, get_current_time, LOCAL_TZ
from src.report_generator import ReportGenerator


@pytest.fixture
def tmp_workspace(tmp_path):
    """Provides a temporary workspace with isolated sample CSVs and templates."""
    data_dir = tmp_path / "data"
    templates_dir = tmp_path / "templates"
    outputs_dir = tmp_path / "outputs"
    logs_dir = tmp_path / "logs"

    data_dir.mkdir()
    templates_dir.mkdir()
    outputs_dir.mkdir()
    logs_dir.mkdir()

    # Sample contacts CSV
    contacts_csv = data_dir / "contacts.csv"
    contacts_csv.write_text(
        "name,email\n"
        "Alice Johnson,alice@example.com\n"
        ",nameless@example.com\n"
        "Bad Email User,bad-email-without-at\n",
        encoding="utf-8"
    )

    # Sample reminders CSV
    reminders_csv = data_dir / "reminders.csv"
    reminders_csv.write_text(
        "id,recipient_email,subject,message,scheduled_time,frequency\n"
        "REM-101,alice@example.com,Team Standup,Daily standup meeting,2026-11-20 09:00:00,one-time\n"
        "REM-102,alice@example.com,Future Checkin,Upcoming quarterly review,2026-12-30 15:00:00,daily\n",
        encoding="utf-8"
    )

    # Sample template
    template_file = templates_dir / "email_template.txt"
    template_file.write_text(
        "Subject: {subject}\n\nHi {name},\n\n{message}\nDate: {date}",
        encoding="utf-8"
    )

    return {
        "root": tmp_path,
        "contacts_csv": str(contacts_csv),
        "reminders_csv": str(reminders_csv),
        "templates_dir": str(templates_dir),
        "outputs_dir": str(outputs_dir)
    }


def test_contact_loading_and_email_validation(tmp_workspace):
    """Tests contact loading, email validation regex, and missing name defaults."""
    # 1. Validation method directly
    assert ContactManager.validate_email("user@example.com") is True
    assert ContactManager.validate_email("bad-email") is False
    assert ContactManager.validate_email("") is False
    assert ContactManager.validate_email(None) is False

    # 2. ContactManager parsing
    mgr = ContactManager(filepath=tmp_workspace["contacts_csv"])
    summary = mgr.get_contacts_summary()

    assert summary["total"] == 3
    assert summary["valid"] == 2
    assert summary["invalid"] == 1

    # Check missing name fallback
    assert mgr.get_contact_name("alice@example.com") == "Alice Johnson"
    assert mgr.get_contact_name("nameless@example.com") == ContactManager.DEFAULT_NAME


def test_template_personalization_and_fallback(tmp_workspace):
    """Tests template loading, variable replacement, and graceful missing variable handling."""
    mgr = TemplateManager(templates_dir=tmp_workspace["templates_dir"])
    raw_template = mgr.load_template("email_template.txt")

    context = {
        "name": "Alice Johnson",
        "subject": "Project Sprint Update",
        "message": "Please review the sprint board.",
        "date": "2026-11-22"
    }

    personalized = mgr.render_template(raw_template, context)
    assert "Hi Alice Johnson" in personalized
    assert "Please review the sprint board." in personalized
    assert "Date: 2026-11-22" in personalized

    subj, body = mgr.extract_subject_and_body(personalized)
    assert subj == "Project Sprint Update"
    assert "Hi Alice Johnson" in body

    # Test graceful fallback when variables are missing
    incomplete_context = {"name": "Bob"}
    rendered_fallback = mgr.render_template(raw_template, incomplete_context)
    assert "Hi Bob" in rendered_fallback
    assert "Notification" in rendered_fallback or "Not Specified" in rendered_fallback or "reminder" in rendered_fallback.lower()


def test_datetime_and_timezone_handling(tmp_workspace):
    """Tests datetime parsing into aware Asia/Kolkata timezone."""
    scheduler = ReminderScheduler(
        filepath=tmp_workspace["reminders_csv"],
        tracker_path=str(Path(tmp_workspace["outputs_dir"]) / "tracker.json")
    )

    parsed = scheduler.parse_datetime("2026-11-22 14:30:00")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 11
    assert parsed.day == 22
    assert parsed.tzinfo is not None

    current_tz_time = get_current_time()
    assert current_tz_time.tzinfo is not None


def test_due_reminder_identification(tmp_workspace):
    """Tests distinguishing between due and upcoming reminders."""
    scheduler = ReminderScheduler(
        filepath=tmp_workspace["reminders_csv"],
        tracker_path=str(Path(tmp_workspace["outputs_dir"]) / "tracker.json")
    )

    due_items = scheduler.get_due_reminders()
    upcoming_items = scheduler.get_upcoming_reminders()

    # REM-101 was scheduled for 2026-11-20 (past) -> Due
    due_ids = [item["id"] for item in due_items]
    assert "REM-101" in due_ids

    # REM-102 was scheduled for 2026-12-30 (future) -> Upcoming
    upcoming_ids = [item["id"] for item in upcoming_items]
    assert "REM-102" in upcoming_ids


def test_dry_run_simulation_safety():
    """Verifies that EmailSender in dry-run mode simulates safely without SMTP network calls."""
    sender = EmailSender(dry_run=True)
    assert sender.dry_run is True

    # Sending in dry-run mode should succeed without error and return SIMULATED status
    success, status, msg = sender.send_email(
        recipient_email="test.contact@example.com",
        subject="Important Reminder",
        body="This is a test message.",
        recipient_name="Tester"
    )

    assert success is True
    assert status == "SIMULATED"
    assert "dry-run" in msg.lower()


def test_duplicate_prevention_tracker(tmp_workspace):
    """Tests tracking of executed reminders to avoid processing duplicate reminders."""
    tracker_path = Path(tmp_workspace["outputs_dir"]) / "test_tracker.json"
    tracker = ProcessedTracker(storage_path=str(tracker_path))

    target_dt = get_current_time()

    # Before processing
    assert tracker.is_already_processed("REM-TEST", "one-time", target_dt) is False

    # Mark as processed
    tracker.mark_processed("REM-TEST", target_dt)

    # After processing (one-time should now be True)
    assert tracker.is_already_processed("REM-TEST", "one-time", target_dt) is True

    # Re-loading tracker from disk should preserve status
    reloaded_tracker = ProcessedTracker(storage_path=str(tracker_path))
    assert reloaded_tracker.is_already_processed("REM-TEST", "one-time", target_dt) is True


def test_report_generator_and_csv_export(tmp_workspace):
    """Tests recording dispatch results and exporting summary reports to CSV."""
    report_gen = ReportGenerator(output_dir=tmp_workspace["outputs_dir"])

    report_gen.record_result(
        recipient_name="Alice Johnson",
        recipient_email="alice@example.com",
        subject="Project Update",
        reminder_date_time="2026-11-22 10:00:00",
        status="SIMULATED",
        error_message=""
    )

    report_gen.record_result(
        recipient_name="Unknown",
        recipient_email="bad-email",
        subject="Notice",
        reminder_date_time="2026-11-22 11:00:00",
        status="SKIPPED_INVALID_EMAIL",
        error_message="Invalid email address format"
    )

    df = report_gen.to_dataframe()
    assert len(df) == 2
    assert "recipient_name" in df.columns
    assert "status" in df.columns
    assert df.iloc[0]["status"] == "SIMULATED"
    assert df.iloc[1]["status"] == "SKIPPED_INVALID_EMAIL"

    # Export to CSV
    csv_file = report_gen.export_csv("unit_test_report.csv")
    assert csv_file.exists()
    assert csv_file.stat().st_size > 0
