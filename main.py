"""
main.py
-------
Command-line interface (CLI) entry point for the Email Automation & Reminder System.

Demonstrates:
- Loading contacts & validating email addresses
- Parsing reminders with Asia/Kolkata timezone support
- Personalizing email templates with fallback variables
- Safe dry-run email simulation (no live SMTP calls by default)
- Continuous job scheduling using the `schedule` library
- Automated CSV execution report generation
"""

import argparse
import sys
import time
from pathlib import Path

import schedule

from src.logger import logger
from src.contact_manager import ContactManager
from src.email_template import TemplateManager
from src.email_sender import EmailSender
from src.scheduler import ReminderScheduler, get_current_time
from src.report_generator import ReportGenerator


def print_banner():
    """Prints a clean ASCII banner."""
    print("=" * 75)
    print("       EMAIL AUTOMATION & REMINDER SYSTEM - CLI INTERFACE")
    print("               Timezone: Asia/Kolkata (IST)")
    print("=" * 75)


def process_single_reminder(
    reminder: dict,
    contact_mgr: ContactManager,
    template_mgr: TemplateManager,
    raw_template: str,
    sender: EmailSender,
    report_gen: ReportGenerator
) -> bool:
    """
    Processes an individual reminder: validates contact, renders template,
    sends/simulates email, and records audit report.

    Returns:
        bool: True if sent/simulated successfully, False otherwise.
    """
    recipient_email = reminder.get("recipient_email", "").strip().lower()
    subject = reminder.get("subject", "Reminder Notification")
    message = reminder.get("message", "")
    scheduled_time = reminder.get("scheduled_time", "Upcoming")
    rem_id = reminder.get("id", "N/A")

    # 1. Validate email address format
    if not ContactManager.validate_email(recipient_email):
        error_msg = f"Invalid email format: '{recipient_email}'"
        logger.warning(f"[SKIPPED] Reminder {rem_id}: {error_msg}")
        report_gen.record_result(
            recipient_name="Unknown",
            recipient_email=recipient_email,
            subject=subject,
            reminder_date_time=scheduled_time,
            status="SKIPPED_INVALID_EMAIL",
            error_message=error_msg
        )
        return False

    # 2. Retrieve contact name (or default fallback)
    contact_name = contact_mgr.get_contact_name(recipient_email)

    # 3. Personalize email template
    context = {
        "name": contact_name,
        "subject": subject,
        "message": message,
        "date": scheduled_time,
        "scheduled_time": scheduled_time
    }
    personalized_email = template_mgr.render_template(raw_template, context)
    extracted_subject, email_body = template_mgr.extract_subject_and_body(personalized_email)

    # 4. Dispatch email (Safe simulation by default)
    success, status, status_msg = sender.send_email(
        recipient_email=recipient_email,
        subject=extracted_subject,
        body=email_body,
        recipient_name=contact_name
    )

    # 5. Record result in audit report
    report_gen.record_result(
        recipient_name=contact_name,
        recipient_email=recipient_email,
        subject=extracted_subject,
        reminder_date_time=scheduled_time,
        status=status,
        error_message="" if success else status_msg
    )

    return success


def run_batch_simulation(
    reminders: list,
    contact_mgr: ContactManager,
    template_mgr: TemplateManager,
    raw_template: str,
    sender: EmailSender,
    report_gen: ReportGenerator,
    mark_as_processed: bool = False,
    scheduler: ReminderScheduler = None
):
    """Processes a list of reminders in sequence."""
    if not reminders:
        print("\nNo reminders to process.")
        return

    print(f"\nProcessing {len(reminders)} reminder(s)...")
    success_count = 0

    for rem in reminders:
        rem_id = rem.get("id", "N/A")
        print(f" -> [{rem_id}] To: {rem.get('recipient_email')} | Subject: {rem.get('subject')}")
        ok = process_single_reminder(
            rem, contact_mgr, template_mgr, raw_template, sender, report_gen
        )
        if ok:
            success_count += 1
            if mark_as_processed and scheduler is not None:
                scheduler.tracker.mark_processed(rem_id, get_current_time())

    print(f"\nBatch processing finished: {success_count}/{len(reminders)} processed successfully.")


def run_continuous_scheduler(
    interval_seconds: int,
    contact_mgr: ContactManager,
    template_mgr: TemplateManager,
    raw_template: str,
    sender: EmailSender,
    report_gen: ReportGenerator,
    scheduler: ReminderScheduler
):
    """Runs a continuous polling schedule loop using the `schedule` library."""
    print(f"\n[SCHEDULER STARTED] Checking for due reminders every {interval_seconds} seconds.")
    print("Press Ctrl+C to stop the scheduler.\n")

    def job():
        now_str = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now_str}] Checking for due reminders...")
        due_items = scheduler.get_due_reminders()
        if due_items:
            print(f" -> Found {len(due_items)} due reminder(s)!")
            run_batch_simulation(
                due_items, contact_mgr, template_mgr, raw_template,
                sender, report_gen, mark_as_processed=True, scheduler=scheduler
            )
            report_gen.export_csv("scheduler_execution_report.csv")
        else:
            print(" -> No due reminders at this time.")

    # Schedule the recurring check
    schedule.every(interval_seconds).seconds.do(job)

    # Initial check on start
    job()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SCHEDULER STOPPED] Gracefully exited by user.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Email Automation & Reminder System - Command Line Interface"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt live email sending (Disabled by default; requires .env credentials and whitelist)"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Process due reminders once and exit"
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Process/simulate all reminders in the dataset for demonstration"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run continuous scheduler loop using the schedule library"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Polling interval in seconds for the scheduler (default: 10)"
    )
    parser.add_argument(
        "--show-contacts",
        action="store_true",
        help="Display loaded contacts and validation status"
    )
    parser.add_argument(
        "--show-reminders",
        action="store_true",
        help="Display all reminders and their schedule/due status"
    )
    parser.add_argument(
        "--reset-tracker",
        action="store_true",
        help="Reset duplicate reminder tracking history"
    )

    args = parser.parse_args()

    print_banner()

    # Determine execution mode
    is_dry_run = not args.live

    # Initialize components
    logger.info("Initializing system components...")
    contact_mgr = ContactManager("data/contacts.csv")
    template_mgr = TemplateManager("templates")
    sender = EmailSender(dry_run=is_dry_run)
    scheduler = ReminderScheduler("data/reminders.csv")
    report_gen = ReportGenerator("outputs")

    if args.reset_tracker:
        scheduler.tracker.reset()
        print("Duplicate reminder history has been reset.")
        scheduler.load_reminders()

    # Load email template
    try:
        raw_template = template_mgr.load_template("email_template.txt")
    except FileNotFoundError:
        print("Error: Could not find templates/email_template.txt. Exiting.")
        sys.exit(1)

    # Mode 1: Show Contacts
    if args.show_contacts:
        print("\n--- Loaded Contacts ---")
        print(contact_mgr.df.to_string(index=False))
        summary = contact_mgr.get_contacts_summary()
        print(f"\nTotal: {summary['total']} | Valid: {summary['valid']} | Invalid: {summary['invalid']}")
        return

    # Mode 2: Show Reminders
    if args.show_reminders:
        print("\n--- Loaded Reminders ---")
        display_df = scheduler.reminders_df[["id", "recipient_email", "subject", "scheduled_time", "frequency", "status"]]
        print(display_df.to_string(index=False))
        rem_summary = scheduler.get_summary()
        print(f"\nTotal: {rem_summary['total']} | Due: {rem_summary['due']} | Upcoming: {rem_summary['upcoming']} | Completed: {rem_summary['completed']}")
        return

    # Mode 3: Continuous Scheduler
    if args.schedule:
        run_continuous_scheduler(
            args.interval, contact_mgr, template_mgr, raw_template,
            sender, report_gen, scheduler
        )
        return

    # Mode 4: Run All (Simulate/test every reminder)
    if args.run_all:
        all_reminders = scheduler.reminders_df.to_dict(orient="records")
        print(f"\n[DEMO MODE] Processing all {len(all_reminders)} reminders in dataset:")
        run_batch_simulation(
            all_reminders, contact_mgr, template_mgr, raw_template,
            sender, report_gen, mark_as_processed=False
        )
        report_file = report_gen.export_csv("cli_run_all_report.csv")
        print(f"\nAudit Report generated: {report_file}")
        return

    # Default Mode: Process Due Reminders Once (--run-once or default)
    due_items = scheduler.get_due_reminders()
    print(f"\nCurrent Time (Asia/Kolkata): {get_current_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Due Reminders Found: {len(due_items)}")

    if due_items:
        run_batch_simulation(
            due_items, contact_mgr, template_mgr, raw_template,
            sender, report_gen, mark_as_processed=True, scheduler=scheduler
        )
    else:
        print("No reminders are currently due.")
        upcoming_items = scheduler.get_upcoming_reminders()
        print(f"Upcoming Reminders: {len(upcoming_items)}")

    report_file = report_gen.export_csv("cli_execution_report.csv")
    print(f"\nAudit report exported to: {report_file}")
    print("=" * 75)
    print("Run completed successfully.")


if __name__ == "__main__":
    main()
