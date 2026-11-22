"""
email_template.py
-----------------
Handles email template management:
- Loads text templates from disk.
- Replaces placeholders such as {name}, {message}, {date}, and {subject}.
- Personalizes emails safely for each recipient.
- Handles missing placeholder variables gracefully with sensible defaults.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional
from src.logger import logger


class TemplateManager:
    """Manages loading, parsing, and rendering of personalized email templates."""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)

    def load_template(self, filename: str = "email_template.txt") -> str:
        """
        Loads the template content from file.

        Args:
            filename: Name of the template file in templates directory.

        Returns:
            str: Raw template string.
        """
        file_path = self.templates_dir / filename
        if not file_path.exists():
            error_msg = f"Template file not found at: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        content = file_path.read_text(encoding="utf-8")
        logger.info(f"Loaded email template successfully from: {file_path}")
        return content

    def render_template(
        self,
        template_str: str,
        context: Dict[str, Any],
        default_fallback: str = "[Not Specified]"
    ) -> str:
        """
        Replaces placeholders in template with context values.
        Supports {name}, {message}, {date}, {scheduled_time}, {subject}.
        Handles missing variables gracefully without throwing unhandled exceptions.

        Args:
            template_str: Raw template with {placeholder} tokens.
            context: Mapping of variable names to values.
            default_fallback: String to use if a variable is missing in context.

        Returns:
            str: Rendered personalized message.
        """
        # Ensure common placeholder aliases are present
        normalized_context = dict(context)

        # Alias 'date' and 'scheduled_time' so both work interchangeably
        if "date" in normalized_context and "scheduled_time" not in normalized_context:
            normalized_context["scheduled_time"] = normalized_context["date"]
        elif "scheduled_time" in normalized_context and "date" not in normalized_context:
            normalized_context["date"] = normalized_context["scheduled_time"]

        # Provide friendly default values for common keys if missing
        defaults = {
            "name": "Valued Contact",
            "message": "This is a reminder notification.",
            "date": "Upcoming",
            "scheduled_time": "Upcoming",
            "subject": "Notification"
        }

        # Safe substitution regex for {variable_name}
        def replace_token(match: re.Match) -> str:
            token = match.group(1).strip()
            if token in normalized_context and normalized_context[token] is not None:
                return str(normalized_context[token])
            if token in defaults:
                logger.warning(
                    f"Template placeholder '{{{token}}}' not found in context. "
                    f"Using default: '{defaults[token]}'."
                )
                return defaults[token]
            logger.warning(
                f"Unknown template placeholder '{{{token}}}' encountered. "
                f"Using fallback: '{default_fallback}'."
            )
            return default_fallback

        rendered = re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_token, template_str)
        return rendered

    def extract_subject_and_body(self, rendered_email: str) -> tuple:
        """
        Helper to separate a 'Subject: ...' header line from the rest of the body.

        Args:
            rendered_email: Rendered text containing optional 'Subject: ...' header.

        Returns:
            tuple: (subject, body)
        """
        lines = rendered_email.splitlines()
        subject = "Reminder Notification"
        body_lines = []

        is_header = True
        for line in lines:
            if is_header and line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
                is_header = False
                continue
            # First blank line after subject ends header section
            if is_header and not line.strip():
                is_header = False
                continue
            is_header = False
            body_lines.append(line)

        body = "\n".join(body_lines).strip()
        return subject, body
