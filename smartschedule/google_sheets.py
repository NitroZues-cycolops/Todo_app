import os
import json
from typing import List, Optional
from datetime import date, datetime

from dotenv import load_dotenv

load_dotenv()

_GOOGLE_AVAILABLE = None


def _check_google_libs():
    global _GOOGLE_AVAILABLE
    if _GOOGLE_AVAILABLE is not None:
        return _GOOGLE_AVAILABLE
    try:
        import google.oauth2.service_account
        import googleapiclient.discovery
        _GOOGLE_AVAILABLE = True
    except ImportError:
        _GOOGLE_AVAILABLE = False
    return _GOOGLE_AVAILABLE


def _get_google_credentials():
    """Load Google service account credentials from file or JSON string."""
    if not _check_google_libs():
        return None
    creds = None
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    if service_account_file and os.path.exists(service_account_file):
        try:
            creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
        except Exception:
            creds = None
    elif service_account_json:
        try:
            info = json.loads(service_account_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        except Exception:
            return None
    return creds


def is_google_sheets_configured() -> bool:
    """Check if Google Sheets is properly configured."""
    if not _check_google_libs():
        return False
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
    if not sheet_id or sheet_id.startswith("PUT_YOUR_"):
        return False
    creds = _get_google_credentials()
    return bool(sheet_id) and creds is not None


def _get_service():
    """Get Google Sheets API service instance."""
    if not _check_google_libs():
        return None
    creds = _get_google_credentials()
    if not creds:
        return None
    from googleapiclient.discovery import build
    return build("sheets", "v4", credentials=creds)


def _sheet_exists(service, spreadsheet_id: str, sheet_name: str) -> bool:
    """Check if a sheet (tab) exists in the spreadsheet."""
    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get("sheets", [])
        for s in sheets:
            if s.get("properties", {}).get("title") == sheet_name:
                return True
        return False
    except Exception:
        return False


def _create_sheet(service, spreadsheet_id: str, sheet_name: str, headers: List[str]):
    """Create a new sheet tab with headers."""
    try:
        body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
        range_name = f"{sheet_name}!A1:{chr(65 + len(headers) - 1)}1"
        values = [headers]
        body = {"values": values}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption="RAW", body=body
        ).execute()
        return True
    except Exception as e:
        print(f"Error creating sheet {sheet_name}: {e}")
        return False


def _date_to_str(d) -> str:
    if d is None:
        return ""
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def _datetime_to_str(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


TASK_HEADERS = ["ID", "Title", "Description", "Completed", "Priority", "Due Date", "Due Time", "Category", "Created At", "Updated At"]
EVENT_HEADERS = ["ID", "Title", "Description", "Start Date", "Start Time", "End Date", "End Time", "All Day", "Location", "Color", "Category", "Created At", "Updated At"]


def sync_tasks_to_sheets(tasks) -> int:
    """Sync all tasks to Google Sheets."""
    if not is_google_sheets_configured():
        return 0
    service = _get_service()
    if not service:
        return 0
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    sheet_name = os.getenv("GOOGLE_SHEET_TASKS_TAB", "Tasks")

    if not _sheet_exists(service, spreadsheet_id, sheet_name):
        _create_sheet(service, spreadsheet_id, sheet_name, TASK_HEADERS)

    values = [TASK_HEADERS]
    for t in tasks:
        values.append([
            t.id, t.title, t.description or "",
            "YES" if t.completed else "NO",
            t.priority or "medium",
            _date_to_str(t.due_date),
            t.due_time or "",
            t.category or "General",
            _datetime_to_str(t.created_at),
            _datetime_to_str(t.updated_at),
        ])

    range_name = f"{sheet_name}!A1:{chr(65 + len(TASK_HEADERS) - 1)}{len(values)}"
    body = {"values": values}
    try:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption="RAW", body=body
        ).execute()
        return len(tasks)
    except Exception as e:
        print(f"Error syncing tasks: {e}")
        return 0


def sync_events_to_sheets(events) -> int:
    """Sync all events to Google Sheets."""
    if not is_google_sheets_configured():
        return 0
    service = _get_service()
    if not service:
        return 0
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    sheet_name = os.getenv("GOOGLE_SHEET_EVENTS_TAB", "Events")

    if not _sheet_exists(service, spreadsheet_id, sheet_name):
        _create_sheet(service, spreadsheet_id, sheet_name, EVENT_HEADERS)

    values = [EVENT_HEADERS]
    for e in events:
        values.append([
            e.id, e.title, e.description or "",
            _date_to_str(e.start_date),
            e.start_time or "09:00",
            _date_to_str(e.end_date),
            e.end_time or "10:00",
            "YES" if e.all_day else "NO",
            e.location or "",
            e.color or "#4772fa",
            e.category or "General",
            _datetime_to_str(e.created_at),
            _datetime_to_str(e.updated_at),
        ])

    range_name = f"{sheet_name}!A1:{chr(65 + len(EVENT_HEADERS) - 1)}{len(values)}"
    body = {"values": values}
    try:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption="RAW", body=body
        ).execute()
        return len(events)
    except Exception as e:
        print(f"Error syncing events: {e}")
        return 0
