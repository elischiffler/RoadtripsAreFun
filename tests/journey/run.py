"""Disposable signed-token HTTP journey with source/restore volume evidence."""

import http.client
import json
import os
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUN = os.getenv("JOURNEY_RUN_ID") or secrets.token_hex(5)
if not re.fullmatch(r"[a-z0-9]{1,20}", RUN):
    raise SystemExit("JOURNEY_RUN_ID must be lowercase alphanumeric")
PROJECT = f"roadtrips-journey-{RUN}"
ARTIFACTS = HERE / ".artifacts"
ARTIFACTS.mkdir(exist_ok=True)
for volume in (f"{PROJECT}_source-data", f"{PROJECT}_restore-data"):
    if (
        subprocess.run(
            ["docker", "volume", "inspect", volume], check=False, capture_output=True
        ).returncode
        == 0
    ):
        raise SystemExit(f"Refusing populated/reused journey volume: {volume}")
clean_checkout = not subprocess.check_output(
    ["git", "status", "--porcelain"], cwd=ROOT, text=True
).strip()
REVISION = (
    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if clean_checkout
    else "local-journey-uncommitted"
)
ENV = {**os.environ, "JOURNEY_RUN_ID": RUN, "ROADTRIPS_REVISION": REVISION}
COMPOSE = ["docker", "compose", "-f", str(HERE / "compose.yaml"), "-p", PROJECT]
SOURCE = "http://127.0.0.1:18002"
ISSUER = "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_LOCALJOURNEY"


def docker(*args, input_data=None, timeout=120):
    result = subprocess.run(
        COMPOSE + list(args),
        env=ENV,
        input=input_data,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"docker compose {' '.join(args)}: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def request(base, method, path, payload=None, token=None, timeout=15):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            return (
                response.status,
                json.loads(data) if data else None,
                time.monotonic() - start,
            )
    except urllib.error.HTTPError as error:
        data = error.read()
        return error.code, json.loads(data) if data else None, time.monotonic() - start


def wait_ready(base, deadline=60):
    until = time.monotonic() + deadline
    while time.monotonic() < until:
        try:
            code, data, _ = request(base, "GET", "/ready", timeout=5)
            if code == 200 and data == {"status": "ready"}:
                return
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected):
            pass
        time.sleep(1)
    raise AssertionError(f"{base} was not ready within {deadline}s")


def expect(base, method, path, code, payload=None, token=None):
    actual, data, elapsed = request(base, method, path, payload, token)
    assert actual == code, (method, path, actual, data)
    assert elapsed < 15, (method, path, elapsed)
    return data


private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
private_path = ARTIFACTS / f"{RUN}.private.pem"
public_path = ARTIFACTS / f"{RUN}.public.pem"
with private_path.open("xb") as file:
    file.write(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
with public_path.open("xb") as file:
    file.write(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )


def token(subject):
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": ISSUER,
            "client_id": "localjourneyclient",
            "sub": subject,
            "token_use": "access",
            "iat": now,
            "exp": now + timedelta(hours=2),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "local-journey-key"},
    )


owner = token(f"journey-{RUN}-owner")
other = token(f"journey-{RUN}-other")
chat_id = 741
chat_path = f"/chats/update/{chat_id}"


def record(base):
    rows = expect(base, "GET", "/chats", 200, token=owner)
    assert len(rows) == 1, rows
    data, log = rows[0]
    assert data["chatId"] == chat_id and data["budget"] == 400
    assert data["initial"]["geometry"]["coordinates"] == [
        [-120.6596, 35.2828],
        [-120.1789, 34.8518],
        [-119.6982, 34.4208],
    ]
    assert (
        data["route"]["geometry"]["coordinates"]
        == data["initial"]["geometry"]["coordinates"]
    )
    assert data["initial"]["legs"][0]["steps"][0]["geometry"]["coordinates"][0] == [
        -120.6596,
        35.2828,
    ]
    assert data["itinerary"][0]["stops"][-1]["name"] == "Arrive at your destination"
    assert [message["text"] for message in log["messages"]] == [
        "Plan the coast",
        "Fixture hello",
    ]
    assert expect(base, "GET", "/chats", 200, token=other) == []
    expect(base, "GET", "/chats", 401)
    return data


def recall(base):
    for auth_token, expected in [
        (owner, "Prefers quiet routes."),
        (other, "No saved preference."),
    ]:
        response = expect(
            base,
            "POST",
            "/agent/chat",
            200,
            {
                "partitionKey": auth_token,
                "chatId": str(chat_id),
                "message": "[fixture:recall]",
            },
        )
        assert response["reply"] == expected and response["toolsUsed"] == [
            "recall_facts"
        ]


objects_query = (
    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
    "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
    "AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f');"
)


def object_count():
    return int(
        docker(
            "exec",
            "-T",
            "restore",
            "psql",
            "-U",
            "postgres",
            "-d",
            "roadtrips",
            "-Atc",
            objects_query,
        )
    )


def restore(archive):
    count = object_count()
    if count:
        raise RuntimeError(f"Restore refused: target has {count} application objects")
    docker(
        "exec",
        "-T",
        "restore",
        "pg_restore",
        "-U",
        "postgres",
        "-d",
        "roadtrips",
        "--no-owner",
        "--no-privileges",
        "--single-transaction",
        "--exit-on-error",
        input_data=archive,
    )


started = False
mentro_stopped = False
try:
    print(f"run={RUN} commit={REVISION}", flush=True)
    docker(
        "up",
        "--build",
        "-d",
        "--wait",
        "--wait-timeout",
        "60",
        "postgres",
        "api",
        "web",
        "auth",
        timeout=600,
    )
    started = True
    wait_ready(SOURCE)
    first = expect(
        SOURCE,
        "POST",
        "/validate-location",
        200,
        {"is_coordinates": False, "location": {"address": "San Luis Obispo, CA"}},
    )
    second = expect(
        SOURCE,
        "POST",
        "/validate-location",
        200,
        {"is_coordinates": False, "location": {"address": "Santa Barbara, CA"}},
    )
    assert (first["latitude"], second["longitude"]) == (35.2828, -119.6982)
    params = urllib.parse.urlencode(
        {
            "start_lat": first["latitude"],
            "start_lon": first["longitude"],
            "end_lat": second["latitude"],
            "end_lon": second["longitude"],
        }
    )
    initial = expect(SOURCE, "GET", f"/get-initial-route?{params}", 200)
    assert initial["distance"] == 160000 and initial["legs"][0]["summary"] == "US-101 S"
    route = expect(
        SOURCE,
        "POST",
        "/generate-final-route",
        200,
        {
            "initial_route": initial,
            "num_stops": 0,
            "budget": 400,
            "start": "2026-10-01T09:00:00",
        },
    )
    assert route["cost"] == 0 and route["geometry"] == initial["geometry"]
    assert route["stops"][-1]["address"] == "Santa Barbara, CA"
    itinerary = expect(
        SOURCE,
        "POST",
        "/generate-itinerary",
        200,
        {"route": route, "start_time": "2026-10-01T09:00:00"},
    )
    assert itinerary[0]["stops"][0]["time"] == "09:00 AM"
    assert itinerary[0]["stops"][-1]["time"] == "11:00 AM"
    chat_data = {
        "chatId": chat_id,
        "locationType": "cities",
        "stops": 0,
        "budget": 400,
        "showInputBar": True,
        "showStopSlider": False,
        "showBudgetSlider": False,
        "showAddressInput": False,
        "workflowStarted": True,
        "loading": False,
        "carDetails": [],
        "startCoords": [35.2828, -120.6596],
        "endCoords": [34.4208, -119.6982],
        "startConfirmed": first,
        "endConfirmed": second,
    }
    chat_log = {
        "id": chat_id,
        "title": "Coastal trip",
        "messages": [{"sender": "user", "text": "Plan the coast"}],
    }
    body = {"PartitionKey": owner, "ChatData": chat_data, "ChatLog": chat_log}
    expect(SOURCE, "POST", f"/chats/create/{chat_id}", 200, body)
    body["ChatData"].update(
        {"initial": initial, "route": route, "itinerary": itinerary}
    )
    body["ChatLog"]["messages"].append({"sender": "bot", "text": "Fixture hello"})
    expect(SOURCE, "PUT", chat_path, 200, body)
    other_body = json.loads(json.dumps(body))
    other_body["PartitionKey"] = other
    expect(SOURCE, "PUT", chat_path, 404, other_body)
    expect(SOURCE, "DELETE", f"/chats/delete/{chat_id}", 404, token=other)
    expect(SOURCE, "DELETE", f"/chats/delete/{chat_id}", 401)
    throwaway = json.loads(json.dumps(body))
    throwaway["ChatData"]["chatId"] = chat_id + 1
    throwaway["ChatData"].pop("initial")
    throwaway["ChatData"].pop("route")
    throwaway["ChatData"].pop("itinerary")
    throwaway["ChatLog"]["id"] = chat_id + 1
    expect(SOURCE, "POST", f"/chats/create/{chat_id + 1}", 200, throwaway)
    expect(SOURCE, "DELETE", f"/chats/delete/{chat_id + 1}", 200, token=owner)
    record(SOURCE)
    print(
        "R1/R2 HTTP route, itinerary, geometry, save/update, reload and owner denial PASS",
        flush=True,
    )

    memory = expect(
        SOURCE,
        "POST",
        "/agent/chat",
        200,
        {
            "partitionKey": owner,
            "chatId": str(chat_id),
            "message": "[fixture:remember]",
        },
    )
    assert memory["reply"] == "Preference saved." and memory["toolsUsed"] == [
        "remember_fact"
    ]
    recall(SOURCE)
    print(
        "R2 signed API agent memory write/read and second-owner separation PASS",
        flush=True,
    )

    # Real API and real Mentro container. The first marker returns a controlled
    # prose reply; the second yields a streamed text tool request.
    plain = expect(
        SOURCE,
        "POST",
        "/agent/chat",
        200,
        {"partitionKey": owner, "chatId": str(chat_id), "message": "[fixture:tool]"},
    )
    assert plain["reply"] == "Hello world" and plain["provider"].startswith("mentro:")
    # Real API and real Mentro container. This fixture marker yields a controlled
    # streamed tool request; the application dispatches validate_location.
    agent = expect(
        SOURCE,
        "POST",
        "/agent/chat",
        200,
        {
            "partitionKey": owner,
            "chatId": str(chat_id),
            "message": "[fixture:text-tool]",
        },
    )
    assert "validate_location" in agent["toolsUsed"] and agent["provider"].startswith(
        "mentro:"
    )
    print(
        f"R3 real Mentro streamed tool: {agent['toolsUsed']}, provider={agent['provider']}",
        flush=True,
    )

    mentro_container = "mentro-server-local-mentro-server-1"
    subprocess.run(
        ["docker", "stop", "--time", "15", mentro_container],
        check=True,
        capture_output=True,
        timeout=25,
    )
    mentro_stopped = True
    unavailable = expect(
        SOURCE,
        "POST",
        "/agent/chat",
        503,
        {"partitionKey": owner, "chatId": str(chat_id), "message": "[fixture:tool]"},
    )
    assert unavailable["detail"] == "No language model provider is available right now."
    subprocess.run(
        ["docker", "start", mentro_container],
        check=True,
        capture_output=True,
        timeout=30,
    )
    mentro_stopped = False
    deadline = time.monotonic() + 60
    while True:
        try:
            reply = expect(
                SOURCE,
                "POST",
                "/agent/chat",
                200,
                {
                    "partitionKey": owner,
                    "chatId": str(chat_id),
                    "message": "[fixture:tool]",
                },
            )
            if reply["reply"] == "Hello world":
                break
        except AssertionError:
            if time.monotonic() >= deadline:
                raise AssertionError("Mentro did not recover in 60s") from None
            time.sleep(2)
    print("R3 Mentro interruption 503 and recovery within 60s PASS", flush=True)

    docker("stop", "postgres")
    down = expect(SOURCE, "GET", "/chats", 503, token=owner)
    assert down["detail"] == "Chat storage is temporarily unavailable"
    docker("up", "-d", "--wait", "--wait-timeout", "60", "postgres")
    wait_ready(SOURCE)
    record(SOURCE)
    print("R6 PostgreSQL interruption 503 and recovery within 60s PASS", flush=True)

    docker("stop", "api", "postgres")
    docker("up", "-d", "--wait", "--wait-timeout", "60", "postgres")
    docker(
        "up",
        "-d",
        "--wait",
        "--wait-timeout",
        "60",
        "--force-recreate",
        "--no-deps",
        "api",
    )
    wait_ready(SOURCE)
    record(SOURCE)
    recall(SOURCE)
    print("R2 recreated source database and API read persisted trip PASS", flush=True)

    archive = docker(
        "exec", "-T", "postgres", "pg_dump", "-U", "postgres", "-d", "roadtrips", "-Fc"
    )
    assert archive.startswith(b"PGDMP")
    backup = ARTIFACTS / f"{PROJECT}.dump"
    with backup.open("xb") as file:
        file.write(archive)
    docker(
        "--profile", "restore", "up", "-d", "--wait", "--wait-timeout", "60", "restore"
    )
    restore(archive)
    restored_name = f"{PROJECT}-restore-api"
    docker(
        "run",
        "-d",
        "--no-deps",
        "--name",
        restored_name,
        "-p",
        "127.0.0.1::8000",
        "-e",
        "DATABASE_URL=postgresql://postgres:disposable-local-only@restore/roadtrips",
        "api",
    )
    restored_port = (
        subprocess.check_output(
            ["docker", "port", restored_name, "8000/tcp"], text=True
        )
        .strip()
        .rsplit(":", 1)[-1]
    )
    restored_url = f"http://127.0.0.1:{restored_port}"
    wait_ready(restored_url)
    record(restored_url)
    recall(restored_url)
    try:
        restore(archive)
        raise AssertionError("Populated restore was accepted")
    except RuntimeError as error:
        assert str(error).startswith("Restore refused: target has "), error
        print(str(error), flush=True)
    record(SOURCE)
    recall(SOURCE)
    print(
        f"R5 source={PROJECT}_source-data restore={PROJECT}_restore-data backup={backup} PASS",
        flush=True,
    )
finally:
    if mentro_stopped:
        subprocess.run(
            ["docker", "start", "mentro-server-local-mentro-server-1"],
            check=False,
            capture_output=True,
            timeout=30,
        )
    if started and os.getenv("JOURNEY_KEEP_RUNNING") != "1":
        subprocess.run(
            ["docker", "stop", f"{PROJECT}-restore-api"],
            env=ENV,
            capture_output=True,
            timeout=60,
            check=False,
        )
        subprocess.run(
            COMPOSE
            + [
                "--profile",
                "restore",
                "stop",
                "api",
                "postgres",
                "restore",
                "web",
                "auth",
            ],
            env=ENV,
            capture_output=True,
            timeout=60,
            check=False,
        )
