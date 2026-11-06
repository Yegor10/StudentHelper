"""Google Classroom and Drive integration for the desktop application."""

import json
import mimetypes
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from studenthelper.config import ConfigManager


CLASSROOM_API = "https://classroom.googleapis.com/v1"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
DESKTOP_OAUTH_CLIENT_ID = (
    "411370766360-fnhev2h5tti5q1p10t03n739vf1634hh.apps.googleusercontent.com"
)
SCOPES = (
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/drive.file",
)


@dataclass(frozen=True)
class ClassroomAssignment:
    course_id: str
    course_name: str
    coursework_id: str
    title: str
    description: str
    due_at: datetime | None
    alternate_link: str
    state: str
    submission_id: str | None
    attachments: tuple[str, ...]
    due_has_time: bool = True


def default_token_path() -> Path:
    app_data = os.getenv("APPDATA")
    root = Path(app_data) / "StudentHelper" if app_data else Path.home() / ".studenthelper"
    return root / "classroom-token.json"


def _due_datetime(due_date: Any, due_time: Any) -> datetime | None:
    if not isinstance(due_date, dict):
        return None
    try:
        return datetime(
            int(due_date["year"]),
            int(due_date["month"]),
            int(due_date["day"]),
            int((due_time or {}).get("hours", 0)),
            int((due_time or {}).get("minutes", 0)),
            int((due_time or {}).get("seconds", 0)),
            int((due_time or {}).get("nanos", 0)) // 1000,
            tzinfo=timezone.utc,
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("Google Classroom returned an invalid assignment deadline.")


def _is_overdue(
    due_at: datetime | None,
    due_has_time: bool,
    now: datetime | None = None,
) -> bool:
    if due_at is None:
        return False
    current = now or datetime.now().astimezone()
    due_local = due_at.replace(tzinfo=None)
    current_local = current.replace(tzinfo=None)
    if not due_has_time:
        return due_local.date() < current_local.date()
    return due_local <= current_local


class ClassroomService:
    def __init__(
        self,
        config: ConfigManager,
        token_path: Path | None = None,
    ) -> None:
        self.config = config
        self.token_path = token_path or default_token_path()
        self._session: AuthorizedSession | None = None

    def connect(self) -> None:
        self._credentials(interactive=True)

    def _credentials(self, *, interactive: bool = False) -> Credentials:
        if self._session is not None:
            return self._session.credentials

        if self.token_path.is_file():
            try:
                credentials = Credentials.from_authorized_user_file(
                    str(self.token_path), scopes=SCOPES
                )
            except (OSError, ValueError) as error:
                raise RuntimeError(
                    f"Could not read the saved Google sign-in: {error}"
                ) from error
            if not credentials.has_scopes(SCOPES):
                if not interactive:
                    raise RuntimeError(
                        "Google access needs to be reconnected with the required permissions."
                    )
                credentials = self._run_oauth_flow()
            elif credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save_credentials(credentials)
        elif interactive:
            credentials = self._run_oauth_flow()
        else:
            raise RuntimeError(
                "Connect your Google account first. Check the OAuth Desktop app JSON in Settings."
            )

        if not credentials.valid:
            raise RuntimeError("Google sign-in expired. Connect your account again.")
        self._session = AuthorizedSession(credentials)
        return credentials

    def _run_oauth_flow(self) -> Credentials:
        client_file = self.config.classroom_client_file
        if not client_file:
            raise RuntimeError(
                "Choose the OAuth client JSON for a Desktop app in Settings first."
            )
        path = Path(client_file).expanduser()
        if not path.is_file():
            raise FileNotFoundError(
                f"OAuth client JSON was not found: {path}. Select the file again in Settings."
            )
        try:
            client_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read the OAuth client JSON: {error}") from error
        if not isinstance(client_data, dict) or not isinstance(
            client_data.get("installed"), dict
        ):
            raise ValueError(
                "Select a Google OAuth client JSON with application type Desktop app."
            )
        if client_data["installed"].get("client_id") != DESKTOP_OAUTH_CLIENT_ID:
            raise ValueError(
                "The selected OAuth JSON does not match the configured Desktop app client ID."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            open_browser=True,
            success_message="Google sign-in complete. You can close this browser tab.",
        )
        self._save_credentials(credentials)
        return credentials

    def _save_credentials(self, credentials: Credentials) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.token_path.parent,
                prefix=f"{self.token_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                file.write(credentials.to_json())
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.token_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: bytes | str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._credentials()
        if self._session is None:
            raise RuntimeError("Google Classroom session was not initialized.")
        method = method.upper()
        can_retry = method == "GET"
        for attempt in range(3):
            response = self._session.request(
                method,
                url,
                params=params,
                data=data,
                headers=headers,
                timeout=30,
            )
            if response.ok:
                if not response.content:
                    return {}
                try:
                    result = response.json()
                except ValueError as error:
                    raise RuntimeError(
                        f"Google API returned unreadable data ({response.status_code})."
                    ) from error
                if not isinstance(result, dict):
                    raise RuntimeError("Google API returned an unexpected response.")
                return result

            if can_retry and response.status_code in {408, 429, 500, 502, 503, 504} and attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = min(max(float(retry_after), 0), 5)
                except ValueError:
                    delay = 0.5 * (2**attempt)
                time.sleep(delay)
                continue

            try:
                body = response.json()
            except ValueError:
                body = {}
            message = (
                body.get("error", {}).get("message")
                if isinstance(body, dict)
                else None
            )
            if response.status_code == 503:
                raise RuntimeError(
                    "Google Classroom is temporarily unavailable (503). Try again in a minute."
                )
            raise RuntimeError(
                f"{message or 'Google API request failed'} ({response.status_code})."
            )
        raise RuntimeError("Google API request failed after retries.")

    def _list_all(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        request_params = dict(params)
        while True:
            response = self._request("GET", url, params=request_params)
            for key in ("courses", "courseWork", "studentSubmissions"):
                page = response.get(key)
                if isinstance(page, list):
                    items.extend(item for item in page if isinstance(item, dict))
                    break
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                return items
            request_params["pageToken"] = next_page_token

    def fetch_assignments(self) -> list[ClassroomAssignment]:
        courses = self._list_all(
            f"{CLASSROOM_API}/courses",
            {"courseStates": "ACTIVE", "pageSize": 100},
        )
        assignments: list[ClassroomAssignment] = []
        for course in courses:
            course_id = course.get("id")
            if not course_id:
                continue
            course_path = quote(str(course_id), safe="")
            coursework = self._list_all(
                f"{CLASSROOM_API}/courses/{course_path}/courseWork",
                {"courseWorkStates": "PUBLISHED", "pageSize": 100},
            )
            for item in coursework:
                if item.get("workType") != "ASSIGNMENT" or not item.get("id"):
                    continue
                due_at = _due_datetime(item.get("dueDate"), item.get("dueTime"))
                due_has_time = bool(item.get("dueTime"))
                if _is_overdue(due_at, due_has_time):
                    continue
                coursework_id = str(item["id"])
                submissions = self._list_all(
                    f"{CLASSROOM_API}/courses/{course_path}/courseWork/"
                    f"{quote(coursework_id, safe='')}/studentSubmissions",
                    {"userId": "me", "pageSize": 100},
                )
                submission = submissions[0] if submissions else {}
                state = str(submission.get("state", "UNKNOWN"))
                if state in {"TURNED_IN", "RETURNED"}:
                    continue
                submission_data = submission.get("assignmentSubmission") or {}
                attachments = tuple(
                    str(
                        attachment.get("driveFile", {}).get("title")
                        or attachment.get("driveFile", {}).get("id")
                        or "file"
                    )
                    for attachment in submission_data.get("attachments", [])
                    if isinstance(attachment, dict)
                )
                assignments.append(
                    ClassroomAssignment(
                        course_id=str(course_id),
                        course_name=str(course.get("name") or "Classroom course"),
                        coursework_id=coursework_id,
                        title=str(item.get("title") or "Untitled assignment"),
                        description=str(item.get("description") or ""),
                        due_at=due_at,
                        alternate_link=str(item.get("alternateLink") or ""),
                        state=state,
                        submission_id=(
                            str(submission["id"]) if submission.get("id") else None
                        ),
                        attachments=attachments,
                        due_has_time=due_has_time,
                    )
                )
        return sorted(
            assignments,
            key=lambda item: item.due_at or datetime.max.replace(tzinfo=timezone.utc),
        )

    def attach_file(
        self, assignment: ClassroomAssignment, file_path: Path
    ) -> str:
        if not assignment.submission_id:
            raise ValueError("Google Classroom did not return this submission ID.")
        if assignment.state in {"TURNED_IN", "RETURNED"}:
            raise ValueError("This assignment can no longer be changed.")
        if not file_path.is_file():
            raise FileNotFoundError(f"Selected work file does not exist: {file_path}")
        file_size = file_path.stat().st_size
        if not file_size or file_size > MAX_UPLOAD_BYTES:
            raise ValueError("Choose a non-empty file no larger than 12 MB.")

        boundary = f"studenthelper-{uuid.uuid4()}"
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        metadata = json.dumps({"name": file_path.name}, ensure_ascii=False)
        with file_path.open("rb") as file:
            payload = (
                f"--{boundary}\r\n"
                "Content-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{metadata}\r\n"
                f"--{boundary}\r\n"
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8") + file.read() + f"\r\n--{boundary}--".encode()

        uploaded = self._request(
            "POST",
            f"{DRIVE_UPLOAD_API}?uploadType=multipart&fields=id,name,webViewLink",
            data=payload,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        )
        file_id = uploaded.get("id")
        if not file_id:
            raise RuntimeError("Google Drive did not return an uploaded file ID.")
        course_path = quote(assignment.course_id, safe="")
        coursework_path = quote(assignment.coursework_id, safe="")
        submission_path = quote(assignment.submission_id, safe="")
        try:
            self._request(
                "POST",
                f"{CLASSROOM_API}/courses/{course_path}/courseWork/{coursework_path}/"
                f"studentSubmissions/{submission_path}:modifyAttachments",
                data=json.dumps(
                    {
                        "addAttachments": [
                            {
                                "driveFile": {
                                    "id": file_id,
                                    "title": uploaded.get("name", file_path.name),
                                }
                            }
                        ]
                    }
                ),
                headers={"Content-Type": "application/json"},
            )
        except (OSError, RuntimeError) as error:
            link = uploaded.get("webViewLink") or file_id
            raise RuntimeError(
                f"The file was uploaded to Drive but Classroom could not attach it. "
                f"Drive file: {link}. {error}"
            ) from error
        return str(uploaded.get("name") or file_path.name)

    def turn_in(self, assignment: ClassroomAssignment) -> None:
        if not assignment.submission_id:
            raise ValueError("Google Classroom did not return this submission ID.")
        if assignment.state in {"TURNED_IN", "RETURNED"}:
            raise ValueError("This assignment has already been submitted or returned.")
        course_path = quote(assignment.course_id, safe="")
        coursework_path = quote(assignment.coursework_id, safe="")
        submission_path = quote(assignment.submission_id, safe="")
        self._request(
            "POST",
            f"{CLASSROOM_API}/courses/{course_path}/courseWork/{coursework_path}/"
            f"studentSubmissions/{submission_path}:turnIn",
            data="{}",
            headers={"Content-Type": "application/json"},
        )
