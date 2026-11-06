import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from studenthelper.classroom import (
    CLASSROOM_API,
    DESKTOP_OAUTH_CLIENT_ID,
    ClassroomService,
    _due_datetime,
    _is_overdue,
)
from studenthelper.config import ConfigManager


class FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.content = b"{}"
        self.ok = status_code < 400

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, routes: dict[str, dict]) -> None:
        self.routes = routes
        self.credentials = object()
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return FakeResponse(self.routes[url])


class ClassroomServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self.temp_dir.name) / ".env")
        self.service = ClassroomService(
            self.config, Path(self.temp_dir.name) / "token.json"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_deadlines_parse_classroom_date_and_time(self) -> None:
        due_at = _due_datetime(
            {"year": 2026, "month": 11, "day": 7},
            {"hours": 14, "minutes": 5, "nanos": 123_000_000},
        )
        self.assertEqual(
            due_at,
            datetime(2026, 11, 7, 14, 5, 0, 123_000, tzinfo=timezone.utc),
        )
        self.assertIsNone(_due_datetime(None, None))
        with self.assertRaisesRegex(ValueError, "invalid assignment deadline"):
            _due_datetime({"year": "bad"}, None)

    def test_overdue_filter_respects_deadline_time_and_date_only_due_dates(self) -> None:
        now = datetime(2026, 11, 6, 15, 30)
        today = {"year": 2026, "month": 11, "day": 6}
        self.assertTrue(
            _is_overdue(
                _due_datetime(today, {"hours": 15, "minutes": 29}),
                True,
                now,
            )
        )
        self.assertFalse(
            _is_overdue(
                _due_datetime(today, {"hours": 15, "minutes": 31}),
                True,
                now,
            )
        )
        self.assertFalse(_is_overdue(_due_datetime(today, None), False, now))
        yesterday = now.date() - timedelta(days=1)
        self.assertTrue(
            _is_overdue(
                _due_datetime(
                    {"year": yesterday.year, "month": yesterday.month, "day": yesterday.day},
                    None,
                ),
                False,
                now,
            )
        )
        self.assertFalse(_is_overdue(None, False, now))

    def test_assignments_filter_submitted_and_sort_by_nearest_deadline(self) -> None:
        course_url = f"{CLASSROOM_API}/courses"
        coursework_url = f"{CLASSROOM_API}/courses/course-1/courseWork"
        tomorrow = datetime.now().date() + timedelta(days=1)
        yesterday = datetime.now().date() - timedelta(days=1)
        assignment_ids = [
            "no-date",
            "late",
            "early",
            "overdue",
            "turned-in",
            "returned",
        ]
        routes = {
            course_url: {"courses": [{"id": "course-1", "name": "Science"}]},
            coursework_url: {
                "courseWork": [
                    {
                        "id": assignment_id,
                        "title": assignment_id,
                        "workType": "ASSIGNMENT",
                        **(
                            {
                                "dueDate": {
                                    "year": yesterday.year,
                                    "month": yesterday.month,
                                    "day": yesterday.day,
                                }
                            }
                            if assignment_id == "overdue"
                            else {
                                "dueDate": {
                                    "year": tomorrow.year,
                                    "month": tomorrow.month,
                                    "day": tomorrow.day,
                                },
                                "dueTime": {"hours": hour},
                            }
                            if hour is not None
                            else {}
                        ),
                    }
                    for assignment_id, hour in zip(
                        assignment_ids, [None, 16, 9, None, 10, 11]
                    )
                ]
            },
        }
        for assignment_id in assignment_ids:
            routes[
                f"{coursework_url}/{assignment_id}/studentSubmissions"
            ] = {
                "studentSubmissions": [
                    {
                        "id": f"submission-{assignment_id}",
                        "state": {
                            "turned-in": "TURNED_IN",
                            "returned": "RETURNED",
                        }.get(assignment_id, "NEW"),
                        "assignmentSubmission": {
                            "attachments": [
                                {"driveFile": {"title": "work.pdf"}}
                            ]
                        },
                    }
                ]
            }
        session = FakeSession(routes)
        self.service._session = session

        assignments = self.service.fetch_assignments()

        self.assertEqual(
            [assignment.title for assignment in assignments],
            ["early", "late", "no-date"],
        )
        self.assertEqual(assignments[0].attachments, ("work.pdf",))
        self.assertFalse(assignments[-1].due_has_time)
        self.assertTrue(assignments[0].due_has_time)
        self.assertTrue(all(call[0] == "GET" for call in session.calls))

    def test_get_request_retries_temporary_service_errors(self) -> None:
        class RetrySession(FakeSession):
            def __init__(self) -> None:
                super().__init__({})
                self.statuses = [503, 503, 200]

            def request(self, method: str, url: str, **kwargs) -> FakeResponse:
                self.calls.append((method, url, kwargs))
                status = self.statuses.pop(0)
                return FakeResponse(
                    {"courses": []}
                    if status == 200
                    else {"error": {"message": "unavailable"}},
                    status,
                )

        session = RetrySession()
        self.service._session = session
        with patch("studenthelper.classroom.time.sleep"):
            result = self.service._request("GET", f"{CLASSROOM_API}/courses")
        self.assertEqual(result, {"courses": []})
        self.assertEqual(len(session.calls), 3)

    def test_persistent_503_has_actionable_error(self) -> None:
        class UnavailableSession(FakeSession):
            def request(self, method: str, url: str, **kwargs) -> FakeResponse:
                return FakeResponse(
                    {"error": {"message": "Service is currently unavailable"}},
                    503,
                )

        self.service._session = UnavailableSession({})
        with patch("studenthelper.classroom.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, r"temporarily unavailable \(503\)"):
                self.service._request("GET", f"{CLASSROOM_API}/courses")

    def test_post_request_is_not_retried(self) -> None:
        class PostSession(FakeSession):
            def request(self, method: str, url: str, **kwargs) -> FakeResponse:
                self.calls.append((method, url, kwargs))
                return FakeResponse(
                    {"error": {"message": "Permission denied"}}, 503
                )

        session = PostSession({})
        self.service._session = session
        with self.assertRaisesRegex(RuntimeError, r"temporarily unavailable \(503\)"):
            self.service._request("POST", f"{CLASSROOM_API}/submit", data="{}")
        self.assertEqual(len(session.calls), 1)

    def test_upload_rejects_empty_or_oversized_files(self) -> None:
        from studenthelper.classroom import ClassroomAssignment, MAX_UPLOAD_BYTES

        assignment = ClassroomAssignment(
            "course",
            "Science",
            "work",
            "Assignment",
            "",
            None,
            "",
            "NEW",
            "submission",
            (),
        )
        empty_path = Path(self.temp_dir.name) / "empty.txt"
        empty_path.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "non-empty file"):
            self.service.attach_file(assignment, empty_path)
        large_path = Path(self.temp_dir.name) / "large.bin"
        with large_path.open("wb") as file:
            file.truncate(MAX_UPLOAD_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "no larger than 12 MB"):
            self.service.attach_file(assignment, large_path)

    def test_oauth_json_must_match_the_configured_desktop_client_id(self) -> None:
        client_path = Path(self.temp_dir.name) / "oauth-client.json"
        client_path.write_text(
            '{"installed":{"client_id":"different.apps.googleusercontent.com"}}',
            encoding="utf-8",
        )
        self.config.save(classroom_client_file=str(client_path))
        with patch(
            "studenthelper.classroom.InstalledAppFlow.from_client_secrets_file"
        ) as create_flow:
            with self.assertRaisesRegex(ValueError, "does not match"):
                self.service.connect()
        create_flow.assert_not_called()
        self.assertIn("apps.googleusercontent.com", DESKTOP_OAUTH_CLIENT_ID)


if __name__ == "__main__":
    unittest.main()
