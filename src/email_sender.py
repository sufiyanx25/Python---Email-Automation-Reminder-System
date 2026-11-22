"""
email_sender.py
---------------
Safe email dispatching module implementing:
- smtplib and email.message.EmailMessage
- Configuration loaded exclusively from environment variables (via python-dotenv)
- Strict safety guardrails:
  * Default DRY-RUN mode (safe simulation without network calls)
  * Double-lock protection: Live sending requires both dry_run=False and ENABLE_ACTUAL_SENDING=True
  * Strict test recipient whitelist (ALLOWED_TEST_RECIPIENTS) in live mode
  * Zero password printing or leakage in logs
  * Comprehensive error handling for SMTP, network, and authentication failures
"""

import os
import ssl
import smtplib
from email.message import EmailMessage
from typing import Tuple, List, Optional
from dotenv import load_dotenv

from src.logger import logger

# Load environment variables from .env if present
load_dotenv()


class EmailSender:
    """
    Handles sending emails via SMTP with comprehensive safety guardrails
    and dry-run simulation mode.
    """

    def __init__(
        self,
        dry_run: Optional[bool] = None,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
        sender_name: Optional[str] = None,
        allowed_test_recipients: Optional[List[str]] = None
    ):
        # 1. Evaluate dry_run setting (Default is ALWAYS True)
        env_dry_run_str = os.getenv("DRY_RUN", "True").strip().lower()
        env_dry_run = env_dry_run_str not in ("false", "0", "no")

        if dry_run is not None:
            self.dry_run = dry_run
        else:
            self.dry_run = env_dry_run

        # 2. Evaluate double-lock for actual sending
        env_enable_actual = os.getenv("ENABLE_ACTUAL_SENDING", "False").strip().lower() in ("true", "1", "yes")
        self.enable_actual_sending = env_enable_actual

        # 3. SMTP configuration (Never hardcoded)
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(smtp_port or os.getenv("SMTP_PORT", 587))
        self.sender_email = sender_email or os.getenv("SENDER_EMAIL", "no-reply@example.com")
        self.sender_name = sender_name or os.getenv("SENDER_NAME", "Automated Reminder System")
        self.sender_password = sender_password or os.getenv("SMTP_PASSWORD", os.getenv("SENDER_PASSWORD", ""))

        # 4. Whitelist of allowed test recipients
        if allowed_test_recipients is not None:
            self.allowed_test_recipients = [r.strip().lower() for r in allowed_test_recipients]
        else:
            raw_whitelist = os.getenv("ALLOWED_TEST_RECIPIENTS", "")
            self.allowed_test_recipients = [
                r.strip().lower() for r in raw_whitelist.split(",") if r.strip()
            ]

        # Log operational mode without exposing credentials
        if self.dry_run:
            logger.info(
                "EmailSender initialized in [DRY-RUN SIMULATION] mode. "
                "No live emails will be dispatched."
            )
        else:
            if not self.enable_actual_sending:
                logger.warning(
                    "EmailSender initialized with dry_run=False, but ENABLE_ACTUAL_SENDING is False. "
                    "Live emails remain blocked by system safety guard."
                )
            else:
                logger.warning(
                    f"EmailSender initialized in [LIVE SENDING] mode. "
                    f"Whitelist restricted to {len(self.allowed_test_recipients)} recipient(s)."
                )

    def is_recipient_allowed(self, recipient_email: str) -> bool:
        """Checks if a recipient is on the explicit test whitelist."""
        clean_email = recipient_email.strip().lower()
        return clean_email in self.allowed_test_recipients

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        recipient_name: str = ""
    ) -> Tuple[bool, str, str]:
        """
        Dispatches an email or safely simulates sending.

        Args:
            recipient_email: Recipient email address.
            subject: Subject line.
            body: Full email message body.
            recipient_name: Optional recipient display name.

        Returns:
            Tuple[bool, str, str]: (success, status, message)
        """
        clean_email = recipient_email.strip().lower()

        # =====================================================================
        # 1. DRY-RUN SIMULATION (Default & Safe Mode)
        # =====================================================================
        if self.dry_run:
            log_msg = (
                f"[SIMULATION SUCCESS] Simulated email to: {clean_email} | "
                f"Subject: '{subject}'"
            )
            logger.info(log_msg)
            return True, "SIMULATED", "Email successfully simulated in dry-run mode."

        # =====================================================================
        # 2. SAFETY CHECKS FOR LIVE MODE
        # =====================================================================
        if not self.enable_actual_sending:
            err_msg = (
                "Live sending blocked: ENABLE_ACTUAL_SENDING is set to False in configuration. "
                "Enable it only when explicitly intended."
            )
            logger.warning(f"[SAFETY BLOCK] {err_msg}")
            return False, "SKIPPED_UNAUTHORIZED", err_msg

        # Whitelist protection
        if not self.is_recipient_allowed(clean_email):
            err_msg = (
                f"Recipient '{clean_email}' is not in the ALLOWED_TEST_RECIPIENTS whitelist. "
                f"Actual email blocked to prevent unauthorized or bulk sending."
            )
            logger.warning(f"[SAFETY WHITELIST] {err_msg}")
            return False, "SKIPPED_UNAUTHORIZED", err_msg

        # Credential checks
        if not self.sender_password or not self.sender_email or not self.smtp_server:
            err_msg = "SMTP configuration incomplete (missing server, email, or password in environment)."
            logger.error(f"[CONFIG ERROR] {err_msg}")
            return False, "FAILED", err_msg

        # =====================================================================
        # 3. LIVE SMTP DISPATCH (With Complete Error Handling)
        # =====================================================================
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"{self.sender_name} <{self.sender_email}>"
            msg["To"] = f"{recipient_name} <{clean_email}>" if recipient_name else clean_email
            msg.set_content(body)

            logger.info(f"Connecting to SMTP server {self.smtp_server}:{self.smtp_port} for {clean_email}...")

            # Secure connection via STARTTLS (port 587) or SSL (port 465)
            if self.smtp_port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context, timeout=15) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                    server.ehlo()
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)

            success_msg = f"Live email successfully sent to {clean_email}"
            logger.info(f"[LIVE SENT] {success_msg}")
            return True, "SENT", success_msg

        except smtplib.SMTPAuthenticationError as auth_err:
            err_msg = f"SMTP Authentication failed for user {self.sender_email}. Please check your credentials/app password."
            logger.error(f"[AUTH ERROR] {err_msg}")
            return False, "FAILED", err_msg

        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError) as net_err:
            err_msg = f"Network or SMTP connection failed connecting to {self.smtp_server}:{self.smtp_port} ({net_err})."
            logger.error(f"[NETWORK ERROR] {err_msg}")
            return False, "FAILED", err_msg

        except smtplib.SMTPRecipientsRefused as rec_err:
            err_msg = f"Recipient {clean_email} was refused by the SMTP server: {rec_err}"
            logger.error(f"[RECIPIENT REFUSED] {err_msg}")
            return False, "FAILED", err_msg

        except smtplib.SMTPException as smtp_err:
            err_msg = f"SMTP protocol error occurred: {smtp_err}"
            logger.error(f"[SMTP ERROR] {err_msg}")
            return False, "FAILED", err_msg

        except Exception as general_err:
            err_msg = f"Unexpected error during email transmission: {general_err}"
            logger.error(f"[GENERAL ERROR] {err_msg}")
            return False, "FAILED", err_msg
