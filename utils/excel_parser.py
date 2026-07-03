"""
Excel and CSV parser for participant data.
Supports .xlsx, .xls, and .csv file formats.
Expected columns: Name, Email, Prize Position (case-insensitive).
Any additional columns are stored as extra_data.
"""

import csv
import io
import os

import openpyxl


class ParsedParticipant:
    """Represents a single parsed participant record."""

    def __init__(self, name, email, prize_position, extra_data=None, row_num=None):
        self.name = name
        self.email = email
        self.prize_position = prize_position or "Participation"
        self.extra_data = extra_data or {}
        self.row_num = row_num
        self.errors = []

    def is_valid(self):
        if not self.name or not self.name.strip():
            self.errors.append(f"Row {self.row_num}: Name is required")
        if not self.email or not self.email.strip():
            self.errors.append(f"Row {self.row_num}: Email is required")
        elif "@" not in self.email:
            self.errors.append(f"Row {self.row_num}: Invalid email format: {self.email}")
        return len(self.errors) == 0

    def to_dict(self):
        return {
            "name": self.name.strip() if self.name else "",
            "email": self.email.strip() if self.email else "",
            "prize_position": self.prize_position.strip() if self.prize_position else "Participation",
            "extra_data": self.extra_data,
        }


class ParseResult:
    """Result of parsing a file."""

    def __init__(self):
        self.participants = []
        self.errors = []
        self.column_mapping = {}
        self.total_rows = 0
        self.valid_count = 0
        self.invalid_count = 0

    def add_participant(self, participant):
        self.participants.append(participant)
        if participant.is_valid():
            self.valid_count += 1
        else:
            self.invalid_count += 1
            self.errors.extend(participant.errors)


def normalize_header(header):
    """Normalize a header string for matching."""
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def detect_column_mapping(headers):
    """Detect which columns map to name, email, prize_position."""
    mapping = {
        "name": None,
        "email": None,
        "prize_position": None,
    }

    for i, header in enumerate(headers):
        normalized = normalize_header(header)

        if normalized in ("name", "participant_name", "full_name", "participant name", "candidate_name"):
            mapping["name"] = i
        elif normalized in ("email", "e_mail", "mail", "email_address", "email address"):
            mapping["email"] = i
        elif normalized in (
            "prize",
            "prize_position",
            "prize position",
            "position",
            "award",
            "rank",
            "result",
            "prize_position",
        ):
            mapping["prize_position"] = i

    return mapping


def parse_csv_file(file_path):
    """Parse a CSV file and return a ParseResult."""
    result = ParseResult()

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = next(reader, None)

            if not headers:
                result.errors.append("CSV file is empty or has no headers")
                return result

            headers = [h.strip() for h in headers]
            result.column_mapping = detect_column_mapping(headers)

            for row_num, row in enumerate(reader, start=2):
                result.total_rows += 1

                if not any(cell.strip() for cell in row):
                    continue  # Skip empty rows

                name_idx = result.column_mapping.get("name")
                email_idx = result.column_mapping.get("email")
                prize_idx = result.column_mapping.get("prize_position")

                name = row[name_idx].strip() if name_idx is not None and name_idx < len(row) else ""
                email = row[email_idx].strip() if email_idx is not None and email_idx < len(row) else ""
                prize = row[prize_idx].strip() if prize_idx is not None and prize_idx < len(row) else "Participation"

                # Collect extra data
                extra_data = {}
                for i, header in enumerate(headers):
                    if i not in (name_idx, email_idx, prize_idx) and i < len(row):
                        val = row[i].strip()
                        if val:
                            extra_data[header] = val

                participant = ParsedParticipant(name, email, prize, extra_data, row_num)
                result.add_participant(participant)

    except Exception as e:
        result.errors.append(f"Error reading CSV file: {str(e)}")

    return result


def parse_xlsx_file(file_path):
    """Parse an XLSX file and return a ParseResult."""
    result = ParseResult()

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows or not rows[0]:
            result.errors.append("XLSX file is empty or has no headers")
            wb.close()
            return result

        headers = [str(h).strip() if h else "" for h in rows[0]]
        result.column_mapping = detect_column_mapping(headers)

        for row_num, row in enumerate(rows[1:], start=2):
            result.total_rows += 1

            if not any(cell and str(cell).strip() for cell in row):
                continue  # Skip empty rows

            name_idx = result.column_mapping.get("name")
            email_idx = result.column_mapping.get("email")
            prize_idx = result.column_mapping.get("prize_position")

            name = str(row[name_idx]).strip() if name_idx is not None and name_idx < len(row) and row[name_idx] else ""
            email = str(row[email_idx]).strip() if email_idx is not None and email_idx < len(row) and row[email_idx] else ""
            prize = str(row[prize_idx]).strip() if prize_idx is not None and prize_idx < len(row) and row[prize_idx] else "Participation"

            # Collect extra data
            extra_data = {}
            for i, header in enumerate(headers):
                if i not in (name_idx, email_idx, prize_idx) and i < len(row):
                    val = str(row[i]).strip() if row[i] else ""
                    if val:
                        extra_data[header] = val

            participant = ParsedParticipant(name, email, prize, extra_data, row_num)
            result.add_participant(participant)

        wb.close()

    except Exception as e:
        result.errors.append(f"Error reading XLSX file: {str(e)}")

    return result


def parse_file(file_path):
    """Parse a participant data file based on its extension."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        return parse_csv_file(file_path)
    elif ext in (".xlsx", ".xls"):
        return parse_xlsx_file(file_path)
    else:
        result = ParseResult()
        result.errors.append(f"Unsupported file format: {ext}. Supported formats: .csv, .xlsx, .xls")
        return result
