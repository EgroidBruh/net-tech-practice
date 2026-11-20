import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class EndpointTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requests = []

    def startTest(self, test):
        super().startTest(test)
        self.failure_count = len(self.errors) + len(self.failures)

    def stopTest(self, test):
        failed = len(self.errors) + len(self.failures) > self.failure_count
        for request in test.requests:
            self.requests.append({**request, "test_result": "failed" if failed else "passed"})
        super().stopTest(test)


class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ["BASE_URL"].rstrip("/")
        cls.opener = build_opener(NoRedirect())

    def setUp(self):
        self.requests = []

    def request(self, method, path, status=200, *, payload=None, form=None):
        report = {
            "test_name": self.id().rsplit(".", 1)[-1],
            "endpoint": path,
            "method": method,
            "result": "failed",
            "expected_status": status,
            "http_status": None,
        }
        self.requests.append(report)
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if form is not None:
            body = urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            report["http_status"] = response.code
            result = response.read().decode()
            self.assertEqual(response.code, status, f"{method} {path}: {result[:500]}")
            if response.headers.get_content_type() == "application/json":
                result = json.loads(result)
            report["result"] = "passed"
            return result, response.headers

    def api(self, method, path, status=200, *, payload=None):
        result, _ = self.request(method, path, status, payload=payload)
        return result

    def employee_data(self, number, role="SPECIALIST"):
        return {
            "first_name": "Анна",
            "last_name": "Иванова",
            "email": f"Employee{number}@example.com",
            "position": "Инженер",
            "role": role,
            "work_phone": f"+7343000{number:03d}",
            "mobile_phone": f"+7900000{number:03d}",
        }

    def incident_data(self, title):
        return {
            "source": "monitoring",
            "error_code": "DB_TIMEOUT",
            "title": title,
            "description": "Превышено время ожидания",
            "severity": "WARNING",
        }

    def test_employee_crud_and_conflicts(self):
        data = self.employee_data(1)
        created = self.api("POST", "/employees", 201, payload=data)
        path = f"/employees/{created['id']}"
        self.assertEqual(created["email"], data["email"].lower())
        self.assertEqual(self.api("GET", path), created)
        self.assertIn(created, self.api("GET", "/employees"))

        second = self.employee_data(2)
        self.api("POST", "/employees", 409, payload={**second, "email": created["email"]})
        self.api("POST", "/employees", 409, payload={**second, "work_phone": data["mobile_phone"]})
        self.api("POST", "/employees", 422, payload={**second, "email": "invalid"})
        self.api("GET", "/employees/invalid", 422)
        self.api("PATCH", path, 422, payload={"first_name": None})
        updated = self.api("PATCH", path, payload={"position": "Старший инженер"})
        self.assertEqual(updated, {**created, "position": "Старший инженер"})
        self.assertEqual(self.api("GET", path), updated)

        self.assertEqual(self.api("DELETE", path, 204), "")
        self.api("GET", path, 404)
        self.assertNotIn(created["id"], [employee["id"] for employee in self.api("GET", "/employees")])

    def test_current_duty_and_shift_lifecycle(self):
        self.api("GET", "/duty/current", 503)
        specialist = self.api("POST", "/employees", 201, payload=self.employee_data(3))
        lead = self.api("POST", "/employees", 201, payload=self.employee_data(4, "SHIFT_LEAD"))
        specialist_id = specialist["id"]
        lead_id = lead["id"]
        lead_path = f"/employees/{lead_id}"

        default = {"employee_id": lead_id}
        self.api("PUT", "/duty/default", 422, payload={"employee_id": specialist_id})
        self.assertEqual(self.api("PUT", "/duty/default", payload=default), default)
        self.assertEqual(self.api("PATCH", "/duty/default", payload=default), default)
        current = self.api("GET", "/duty/current")
        self.assertEqual((current["employee_id"], current["source"]), (lead_id, "default"))
        self.api("DELETE", lead_path, 409)
        self.api("PATCH", lead_path, 409, payload={"role": "SPECIALIST"})

        now = datetime.now(timezone.utc)
        data = {
            "employee_id": specialist_id,
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        }
        self.api("POST", "/duty/shifts", 404, payload={**data, "employee_id": str(uuid4())})
        shift = self.api("POST", "/duty/shifts", 201, payload=data)
        shift_path = f"/duty/shifts/{shift['id']}"
        self.assertIn(shift, self.api("GET", "/duty/shifts"))
        self.api("POST", "/duty/shifts", 409, payload=data)
        self.api("PATCH", shift_path, 422, payload={"end_time": data["start_time"]})
        self.api("DELETE", f"/employees/{specialist_id}", 409)

        current = self.api("GET", "/duty/current")
        self.assertEqual((current["employee_id"], current["source"]), (specialist_id, "schedule"))
        self.assertEqual(current["phone_number"], specialist["mobile_phone"])
        end = now + timedelta(hours=2)
        updated = self.api("PATCH", shift_path, payload={"end_time": end.isoformat()})
        self.assertEqual(datetime.fromisoformat(updated["end_time"]), end)
        self.assertIn(updated, self.api("GET", "/duty/shifts"))

        self.api("DELETE", shift_path, 204)
        self.api("PATCH", shift_path, 404, payload={"end_time": end.isoformat()})
        self.assertNotIn(updated, self.api("GET", "/duty/shifts"))
        self.assertEqual(self.api("GET", "/duty/current")["employee_id"], lead_id)
        self.api("DELETE", "/duty/default", 204)
        self.api("DELETE", "/duty/default", 404)
        self.api("GET", "/duty/current", 503)
        self.api("DELETE", lead_path, 204)
        self.api("DELETE", f"/employees/{specialist_id}", 204)

    def test_incident_crud_and_creation_event(self):
        data = self.incident_data("Сбой базы данных")
        self.api("POST", "/incidents", 422, payload={**data, "severity": "UNKNOWN"})
        created = self.api("POST", "/incidents", 201, payload=data)
        path = f"/incidents/{created['id']}"
        self.assertEqual(created["status"], "OPEN")
        self.assertEqual(self.api("GET", path), created)
        self.assertIn(created, self.api("GET", "/incidents"))
        event, = self.api("GET", f"{path}/events")
        self.assertEqual(event["event_type"], "IncidentCreatedEvent")
        self.assertEqual(event["incident_id"], created["id"])
        self.assertEqual(event["severity"], "WARNING")
        self.assertEqual(event["occurred_at"], created["created_at"])

        changes = {"status": "RESOLVED", "severity": "CRITICAL"}
        updated = self.api("PATCH", path, payload=changes)
        self.assertEqual(updated, {**created, **changes})
        self.assertEqual(self.api("GET", path), updated)
        self.assertEqual(self.api("GET", f"{path}/events"), [event])

        self.api("DELETE", path, 204)
        self.api("GET", path, 404)
        self.api("GET", f"{path}/events", 404)
        self.assertNotIn(updated, self.api("GET", "/incidents"))

    def test_web_pages(self):
        for path in ("/", "/ui/employees", "/ui/duty", "/ui/incidents", "/admin/", "/docs"):
            with self.subTest(path=path):
                _, headers = self.request("GET", path)
                self.assertEqual(headers.get_content_type(), "text/html")
        self.request("GET", "/ui/unknown", 404)
        _, headers = self.request("GET", "/static/style.css")
        self.assertEqual(headers.get_content_type(), "text/css")

    def test_web_forms_and_incident_detail(self):
        self.request("POST", "/ui/unknown", 404, form={})
        body, headers = self.request("POST", "/ui/employees", 422, form={"email": "invalid"})
        self.assertEqual(headers.get_content_type(), "text/html")
        self.assertIn('role="alert"', body)

        employee_data = self.employee_data(5, "SHIFT_LEAD")
        _, headers = self.request("POST", "/ui/employees", 303, form=employee_data)
        self.assertEqual(headers["Location"], "/ui/employees?saved=1")
        employee, = [
            row for row in self.api("GET", "/employees")
            if row["email"] == employee_data["email"].lower()
        ]
        employee_id = employee["id"]

        _, headers = self.request("POST", "/ui/default", 303, form={"employee_id": employee_id})
        self.assertEqual(headers["Location"], "/ui/duty?saved=1")
        self.assertEqual(self.api("GET", "/duty/current")["employee_id"], employee_id)
        _, headers = self.request("POST", "/ui/shifts", 303, form={
            "employee_id": employee_id,
            "start_time": "2000-01-01T09:00",
            "end_time": "2000-01-01T10:00",
        })
        self.assertEqual(headers["Location"], "/ui/duty?saved=1")
        shift, = [row for row in self.api("GET", "/duty/shifts") if row["employee_id"] == employee_id]

        incident_data = self.incident_data("Инцидент из веб-формы")
        _, headers = self.request("POST", "/ui/incidents", 303, form=incident_data)
        self.assertEqual(headers["Location"], "/ui/incidents?saved=1")
        incident, = [row for row in self.api("GET", "/incidents") if row["title"] == incident_data["title"]]
        path = f"/ui/incidents/{incident['id']}"
        body, _ = self.request("GET", path)
        self.assertIn(incident_data["title"], body)
        self.assertIn("IncidentCreatedEvent", body)
        self.api("DELETE", f"/incidents/{incident['id']}", 204)
        self.request("GET", path, 404)
        self.api("DELETE", f"/duty/shifts/{shift['id']}", 204)
        self.api("DELETE", "/duty/default", 204)
        self.api("DELETE", f"/employees/{employee_id}", 204)


if __name__ == "__main__":
    report_path = Path(os.environ["REPORT_PATH"])
    runner = unittest.TextTestRunner(verbosity=2, resultclass=EndpointTestResult)
    result = unittest.main(testRunner=runner, exit=False).result
    report_path.write_text(json.dumps(result.requests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
