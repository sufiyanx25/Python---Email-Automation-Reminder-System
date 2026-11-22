"""
Email Automation & Reminder System
-----------------------------------
A modular Python system for contact management, email templating,
Asia/Kolkata timezone scheduling, safe email simulation, and audit reporting.
"""

from src.logger import logger, setup_logger
from src.contact_manager import ContactManager
from src.email_template import TemplateManager
from src.email_sender import EmailSender
from src.scheduler import ReminderScheduler, ProcessedTracker, get_current_time
from src.report_generator import ReportGenerator

__version__ = "1.0.0"
__all__ = [
    "logger",
    "setup_logger",
    "ContactManager",
    "TemplateManager",
    "EmailSender",
    "ReminderScheduler",
    "ProcessedTracker",
    "get_current_time",
    "ReportGenerator",
]
