"""
Thin client for the Canvas LMS REST API.

Only reads the two endpoints this project needs:
  - GET /api/v1/courses                       (active enrollments)
  - GET /api/v1/courses/:id/assignments        (with submission status)

Handles Canvas's Link-header pagination generically so callers never
have to think about page size or cursors.
"""

from __future__ import annotations

import requests


class CanvasError(RuntimeError):
    """Raised when the Canvas API returns something we can't use."""


class CanvasClient:
    def __init__(self, domain: str, token: str, timeout: int = 20):
        if not domain or not token:
            raise CanvasError("CANVAS_DOMAIN and CANVAS_TOKEN are both required")
        self.base_url = f"https://{domain}/api/v1"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.timeout = timeout

    def _get_paginated(self, url: str, params: dict | None = None) -> list[dict]:
        """Follow Canvas's rel="next" Link header until pages run out."""
        results: list[dict] = []
        next_url, next_params = url, params
        while next_url:
            resp = self.session.get(next_url, params=next_params, timeout=self.timeout)
            if resp.status_code == 401:
                raise CanvasError(
                    "Canvas rejected the access token (401). It may be expired or revoked."
                )
            if resp.status_code == 404:
                raise CanvasError(f"Canvas API path not found: {next_url}")
            resp.raise_for_status()

            page = resp.json()
            if not isinstance(page, list):
                raise CanvasError(f"Expected a JSON list from {next_url}, got {type(page)}")
            results.extend(page)

            next_url = resp.links.get("next", {}).get("url")
            next_params = None  # the next_url already carries its own query string
        return results

    def get_active_courses(self) -> list[dict]:
        """Courses the user is currently, actively enrolled in (as a student)."""
        return self._get_paginated(
            f"{self.base_url}/courses",
            params={
                "enrollment_state": "active",
                "per_page": 100,
                "include[]": "term",
            },
        )

    def get_course_assignments(self, course_id: int) -> list[dict]:
        """
        Assignments for one course, including this user's submission status.

        Canvas represents graded quizzes and graded discussions as
        assignments too (via submission_types), so this single endpoint
        covers assignments, tests/quizzes, and graded discussions —
        everything a student is actually on the hook for. Plain
        announcements never appear here; they live on a separate
        endpoint this client never calls.
        """
        return self._get_paginated(
            f"{self.base_url}/courses/{course_id}/assignments",
            params={
                "per_page": 100,
                "order_by": "due_at",
                "include[]": "submission",
            },
        )

    def get_all_assignments(self, exclude_course_ids: set[int] | None = None) -> list[dict]:
        """
        Every assignment across every active course, each annotated with
        its parent course's id and name so downstream code doesn't need
        to look courses back up.
        """
        exclude_course_ids = exclude_course_ids or set()
        courses = self.get_active_courses()

        all_assignments: list[dict] = []
        for course in courses:
            course_id = course.get("id")
            if course_id is None or course_id in exclude_course_ids:
                continue
            course_name = course.get("name") or course.get("course_code") or f"Course {course_id}"

            try:
                assignments = self.get_course_assignments(course_id)
            except CanvasError:
                # One misbehaving course (e.g. concluded but still "active",
                # or a permissions quirk) shouldn't take down the whole run.
                continue

            for a in assignments:
                a["_course_id"] = course_id
                a["_course_name"] = course_name
                all_assignments.append(a)

        return all_assignments
