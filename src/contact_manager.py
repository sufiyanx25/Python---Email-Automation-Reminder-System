"""
contact_manager.py
------------------
Manages contact information:
- Reads contacts from CSV using Pandas.
- Validates email address format.
- Handles missing contact names with friendly defaults.
- Flags invalid email addresses and logs warnings.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
from src.logger import logger

# RFC 5322 compliant simplified email validation regex
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)


class ContactManager:
    """Manages loading, validation, and retrieval of contacts."""

    DEFAULT_NAME = "Valued Contact"

    def __init__(self, filepath: str = "data/contacts.csv"):
        self.filepath = Path(filepath)
        self.df = pd.DataFrame()
        self.valid_contacts: Dict[str, str] = {}
        self.invalid_contacts: List[Dict[str, str]] = []
        self.load_contacts()

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validates if an email string conforms to a valid email address pattern.

        Args:
            email: Email address string to test.

        Returns:
            bool: True if format is valid, False otherwise.
        """
        if not email or not isinstance(email, str):
            return False
        return bool(EMAIL_REGEX.match(email.strip()))

    def load_contacts(self) -> pd.DataFrame:
        """
        Loads contacts from CSV using Pandas, performs validation,
        handles missing values, and builds lookup dictionaries.

        Returns:
            pd.DataFrame: Processed contacts DataFrame.
        """
        if not self.filepath.exists():
            logger.error(f"Contacts file not found at: {self.filepath}")
            self.df = pd.DataFrame(columns=["name", "email", "is_valid", "validation_status"])
            return self.df

        try:
            # Read CSV with pandas
            raw_df = pd.read_csv(self.filepath, dtype=str)
        except Exception as e:
            logger.error(f"Error reading CSV {self.filepath}: {e}")
            self.df = pd.DataFrame(columns=["name", "email", "is_valid", "validation_status"])
            return self.df

        # Normalize column names
        raw_df.columns = [col.strip().lower() for col in raw_df.columns]
        if "email" not in raw_df.columns:
            logger.error(f"Contacts CSV missing required 'email' column.")
            return self.df

        processed_rows = []
        self.valid_contacts = {}
        self.invalid_contacts = []

        for _, row in raw_df.iterrows():
            raw_name = row.get("name", "")
            raw_email = row.get("email", "")

            # Handle missing or empty names
            clean_name = raw_name.strip() if pd.notna(raw_name) and str(raw_name).strip() else self.DEFAULT_NAME

            # Handle email validation
            clean_email = str(raw_email).strip().lower() if pd.notna(raw_email) else ""
            is_valid = self.validate_email(clean_email)

            if is_valid:
                validation_status = "Valid"
                self.valid_contacts[clean_email] = clean_name
            else:
                validation_status = "Invalid Email"
                self.invalid_contacts.append({
                    "name": clean_name,
                    "email": clean_email,
                    "reason": "Malformed or empty email address"
                })
                logger.warning(
                    f"[INVALID CONTACT] Name: '{clean_name}' | Email: '{clean_email}' -> "
                    f"Skipping due to invalid email address format."
                )

            processed_rows.append({
                "name": clean_name,
                "email": clean_email,
                "is_valid": is_valid,
                "validation_status": validation_status
            })

        self.df = pd.DataFrame(processed_rows)
        logger.info(
            f"Contacts loaded successfully: {len(self.valid_contacts)} valid, "
            f"{len(self.invalid_contacts)} invalid."
        )
        return self.df

    def get_contact_name(self, email: str, default: str = DEFAULT_NAME) -> str:
        """
        Retrieves the contact's name by email, falling back to default if not found.

        Args:
            email: Contact email address.
            default: Fallback name if contact is not registered.

        Returns:
            str: Contact name.
        """
        clean_email = email.strip().lower() if email else ""
        return self.valid_contacts.get(clean_email, default)

    def get_contacts_summary(self) -> Dict[str, int]:
        """Returns counts of total, valid, and invalid contacts."""
        return {
            "total": len(self.df),
            "valid": len(self.valid_contacts),
            "invalid": len(self.invalid_contacts)
        }
