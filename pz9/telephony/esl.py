"""Small inbound ESL client using the documented TCP wire protocol."""
import json
import re
import socket
import time
from collections import deque
from contextlib import suppress
from datetime import datetime, timezone
from urllib.parse import unquote

from telephony.store import timestamp


class ESLError(Exception):
    pass


class ESLConnection:
    def __init__(self, settings):
        self.settings = settings
        self.socket = None
        self.buffer = b""
        self.events = deque()

    def __enter__(self):
        try:
            self.socket = socket.create_connection((self.settings.esl_host, self.settings.esl_port), timeout=5)
            headers, _ = self.read_frame(5)
            if headers.get("Content-Type") != "auth/request":
                raise ESLError("FreeSWITCH did not request authentication")
            self.command(f"auth {self.settings.esl_password}")
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.socket:
            self.socket.close()

    def read_frame(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            separator = re.search(b"\r?\n\r?\n", self.buffer)
            if separator:
                headers = {}
                for line in self.buffer[:separator.start()].decode("utf-8").splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        headers[key] = unquote(value.strip())
                length = int(headers.get("Content-Length", "0"))
                if length < 0 or length > 2_000_000:
                    raise ESLError("Invalid ESL frame length")
                end = separator.end() + length
                if len(self.buffer) >= end:
                    body = self.buffer[separator.end():end]
                    self.buffer = self.buffer[end:]
                    return headers, body
            elif len(self.buffer) > 65536:
                raise ESLError("ESL headers too large")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("ESL read timed out")
            self.socket.settimeout(remaining)
            chunk = self.socket.recv(65536)
            if not chunk:
                raise ESLError("FreeSWITCH closed the ESL connection")
            self.buffer += chunk

    def send(self, command):
        if "\n" in command or "\r" in command:
            raise ValueError("ESL command must be a single line")
        self.socket.sendall((command + "\n\n").encode("utf-8"))

    def command(self, command):
        self.send(command)
        deadline = time.monotonic() + 5
        while True:
            headers, body = self.read_frame(max(0.01, deadline - time.monotonic()))
            if headers.get("Content-Type") == "text/event-json":
                self.events.append(json.loads(body))
                continue
            if headers.get("Content-Type") == "command/reply":
                if not headers.get("Reply-Text", "").startswith("+OK"):
                    raise ESLError(headers.get("Reply-Text", "ESL command rejected"))
                return headers
            if headers.get("Content-Type") == "api/response":
                return body.decode("utf-8")
            raise ESLError("Unexpected ESL response")

    def next_event(self, timeout):
        if self.events:
            return self.events.popleft()
        headers, body = self.read_frame(timeout)
        if headers.get("Content-Type") != "text/event-json":
            raise ESLError("Unexpected ESL event frame")
        return json.loads(body)


def failure_status(cause):
    if cause in {"USER_BUSY", "CALL_REJECTED"}:
        return "BUSY"
    if cause in {"NO_ANSWER", "NO_USER_RESPONSE", "ALLOTTED_TIMEOUT", "ORIGINATOR_CANCEL", "RECOVERY_ON_TIMER_EXPIRE"}:
        return "NO_ANSWER"
    return "FAILED"


def dial(call, store, settings, stop):
    call_id = call["id"]
    sent = False
    answered_at = None
    confirmed_at = None
    dtmf_digit = None
    confirmation_deadline = None
    try:
        with ESLConnection(settings) as esl:
            esl.command("event json CHANNEL_PROGRESS CHANNEL_PROGRESS_MEDIA CHANNEL_ANSWER CHANNEL_HANGUP_COMPLETE BACKGROUND_JOB DTMF")
            # All interpolated values are UUIDs, validated numeric extensions or
            # administrator configuration. Incident text never enters commands.
            command = (
                f"bgapi originate {{origination_uuid={call_id},"
                f"originate_timeout={settings.originate_timeout},"
                f"origination_caller_id_name=Incident_Alert,"
                f"origination_caller_id_number={settings.caller_id_number},"
                f"execute_on_answer='sched_hangup +{settings.answered_call_duration + 1} NORMAL_CLEARING',"
                f"park_timeout={settings.answered_call_duration}}}"
                f"user/{call['sip_extension']}@{settings.sip_domain} 9900 XML notifications"
            )
            # Set before send: a broken connection may mean ambiguous delivery.
            sent = True
            reply = esl.command(command)
            job_id = reply.get("Job-UUID")
            if not job_id:
                raise ESLError("FreeSWITCH did not return a Job-UUID")
            deadline = time.monotonic() + settings.originate_timeout + settings.answered_call_duration + 15
            while not stop.is_set() and time.monotonic() < deadline:
                if confirmation_deadline and time.monotonic() >= confirmation_deadline:
                    esl.command(f"api uuid_kill {call_id} NORMAL_CLEARING")
                    confirmation_deadline = None
                try:
                    event = esl.next_event(0.5)
                except TimeoutError:
                    continue
                name = event.get("Event-Name")
                if name == "BACKGROUND_JOB" and event.get("Job-UUID") == job_id:
                    result = event.get("_body", "").strip()
                    if result.startswith("-ERR"):
                        cause = result.removeprefix("-ERR").strip()
                        store.update(call_id, status=failure_status(cause), hangup_cause=cause, finished_at=timestamp())
                        return
                if event.get("Unique-ID") != call_id:
                    continue
                if name in {"CHANNEL_PROGRESS", "CHANNEL_PROGRESS_MEDIA"} and not answered_at:
                    store.update(call_id, status="RINGING")
                elif name == "CHANNEL_ANSWER":
                    answered_at = timestamp()
                    confirmation_deadline = time.monotonic() + settings.answered_call_duration
                    store.update(call_id, status="ANSWERED", answered_at=answered_at)
                elif name == "DTMF" and answered_at and not confirmed_at and confirmation_deadline and time.monotonic() < confirmation_deadline:
                    digit = event.get("DTMF-Digit", "")
                    if digit in "0123456789*#ABCD" and len(digit) == 1:
                        confirmed_at, dtmf_digit = timestamp(), digit
                        store.update(call_id, status="CONFIRMED", confirmed_at=confirmed_at, dtmf_digit=digit)
                        esl.command(f"api uuid_kill {call_id} NORMAL_CLEARING")
                elif name == "CHANNEL_HANGUP_COMPLETE":
                    cause = event.get("Hangup-Cause", "UNKNOWN")
                    # The final event can establish answer even if a prior
                    # CHANNEL_ANSWER event was lost during event delivery.
                    answer_us = int(event.get("Caller-Channel-Answered-Time", "0"))
                    if not answered_at and answer_us > 0:
                        answered_at = datetime.fromtimestamp(answer_us / 1_000_000, timezone.utc).isoformat()
                    store.update(call_id, status="CONFIRMED" if confirmed_at else "UNCONFIRMED" if answered_at else failure_status(cause),
                                 answered_at=answered_at, confirmed_at=confirmed_at, dtmf_digit=dtmf_digit, hangup_cause=cause, finished_at=timestamp())
                    return
            with suppress(Exception):
                esl.command(f"api uuid_kill {call_id} NORMAL_CLEARING")
            raise ESLError("Call observation interrupted or timed out")
    except (OSError, ESLError, ValueError) as exc:
        if not sent:
            # No originate was sent. Retrying a connection is safe.
            store.update(call_id, status="QUEUED", last_error=str(exc))
        else:
            store.update(call_id, status="CONFIRMED" if confirmed_at else "UNKNOWN",
                         answered_at=answered_at, finished_at=timestamp(), last_error=str(exc))
