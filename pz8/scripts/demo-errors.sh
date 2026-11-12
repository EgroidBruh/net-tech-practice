#!/usr/bin/env bash
# Набор 2: регистрация, вход и отрицательные сценарии.
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8080}"
email="demo-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')@example.com"
payload="{\"email\":\"$email\",\"password\":\"Study123!\"}"
response_file=$(mktemp)
trap 'rm -f "$response_file"' EXIT

expect() {
  local expected="$1" method="$2" path="$3" body="$4" code
  code=$(curl -sS -o "$response_file" -w '%{http_code}' -X "$method" \
    "$BASE_URL$path" -H 'Content-Type: application/json' -d "$body")
  printf '%s %s -> HTTP %s (expected %s)\n' "$method" "$path" "$code" "$expected"
  cat "$response_file"
  printf '\n'
  test "$code" = "$expected"
}

expect 200 POST /user/signup "$payload"
expect 409 POST /user/signup "$payload"
expect 200 POST /user/signin "$payload"
expect 403 POST /user/signin "{\"email\":\"$email\",\"password\":\"wrong\"}"
expect 404 POST /user/signin "{\"email\":\"missing-$email\",\"password\":\"wrong\"}"
expect 422 POST /user/signup '{"email":"invalid","password":"x"}'
expect 422 POST /event/new '{"title":"Нет обязательных полей"}'
expect 422 PUT /event/edit/1 '{"location":null}'
expect 422 PUT /event/edit/1 '{"id":123}'
expect 422 GET /event/not-an-id '{}'
