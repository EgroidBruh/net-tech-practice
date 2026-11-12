#!/usr/bin/env bash
# Набор 1: полный цикл CRUD. Нужны bash, curl, python3.
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8080}"

created=$(curl --fail-with-body -sS -X POST "$BASE_URL/event/new" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Семинар по SQLite","image":"sqlite.png","description":"Практика SQLModel","tags":["sqlite","python"],"location":"Аудитория 101"}')
printf 'CREATE: %s\n' "$created"
event_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "$created")

printf '\nREAD ALL:\n'
curl --fail-with-body -sS "$BASE_URL/event/"
printf '\nREAD ONE:\n'
curl --fail-with-body -sS "$BASE_URL/event/$event_id"
printf '\nUPDATE:\n'
curl --fail-with-body -sS -X PUT "$BASE_URL/event/edit/$event_id" \
  -H 'Content-Type: application/json' -d '{"location":"Hybrid","tags":["sqlite","sqlmodel"]}'
printf '\nDELETE:\n'
curl --fail-with-body -sS -X DELETE "$BASE_URL/event/delete/$event_id"
printf '\nREAD AFTER DELETE (expected 404):\n'
code=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/event/$event_id")
printf 'HTTP %s\n' "$code"
test "$code" = 404
