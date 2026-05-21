import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(base_url, method, path, payload=None, token=None, expected=None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            if expected is not None and resp.status != expected:
                raise AssertionError(f"{method} {path} returned {resp.status}: {body}")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"{method} {path} returned {exc.code}: {body}") from exc


def expect_http_error(base_url, method, path, status_code, payload=None, token=None):
    try:
        request(base_url, method, path, payload=payload, token=token)
    except AssertionError as exc:
        if f"returned {status_code}" in str(exc):
            return
        raise
    raise AssertionError(f"{method} {path} should have returned {status_code}")


def wait_for_health(proc, base_url):
    last_error = None
    for _ in range(60):
        if proc.poll() is not None:
            out, err = proc.communicate(timeout=1)
            raise RuntimeError(f"API exited early\nSTDOUT:\n{out}\nSTDERR:\n{err}")
        try:
            status, _ = request(base_url, "GET", "/api/health")
            if status == 200:
                return
        except Exception as exc:
            last_error = exc
            time.sleep(0.4)
    raise RuntimeError(f"API health timeout: {last_error}")


def main():
    tmp = tempfile.mkdtemp(prefix="alp_api_smoke_")
    db_path = Path(tmp) / "api_smoke.db"
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["APPDATA"] = tmp
    env["DATABASE_URL"] = "sqlite:///" + str(db_path).replace("\\", "/")
    env["ALP_BOOTSTRAP_ADMIN_USERNAME"] = "admin"
    env["ALP_BOOTSTRAP_ADMIN_PASSWORD"] = "admin1234"

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )

    try:
        wait_for_health(proc, base_url)

        _, login = request(
            base_url,
            "POST",
            "/api/auth/login",
            {"kullanici_adi": "admin", "sifre": "admin1234"},
            expected=200,
        )
        admin_token = login["access_token"]

        _, device_token = request(base_url, "POST", "/api/auth/device-token", {}, token=admin_token, expected=200)
        _, device_login = request(
            base_url,
            "POST",
            "/api/auth/device-login",
            {"device_token": device_token["device_token"]},
            expected=200,
        )
        admin_token = device_login["access_token"]

        _, farm = request(
            base_url,
            "POST",
            "/api/ciftlikler",
            {"id": "smoke-farm", "ad": "Smoke Farm", "aktif": True},
            token=admin_token,
            expected=201,
        )
        farm_id = farm["id"]

        _, user = request(
            base_url,
            "POST",
            "/api/kullanicilar",
            {
                "kullanici_adi": "smoke_user",
                "sifre": "smoke1234",
                "rol": "ciftlik",
                "ciftlik_id": farm_id,
                "aktif": True,
            },
            token=admin_token,
            expected=201,
        )
        assert user["ciftlik_id"] == farm_id

        _, removable_user = request(
            base_url,
            "POST",
            "/api/kullanicilar",
            {
                "kullanici_adi": "smoke_delete_user",
                "sifre": "smoke1234",
                "rol": "ciftlik",
                "ciftlik_id": farm_id,
                "aktif": True,
            },
            token=admin_token,
            expected=201,
        )
        request(base_url, "DELETE", f"/api/kullanicilar/{removable_user['id']}", token=admin_token, expected=200)
        expect_http_error(
            base_url,
            "POST",
            "/api/auth/login",
            401,
            {"kullanici_adi": "smoke_delete_user", "sifre": "smoke1234"},
        )

        _, farm_login = request(
            base_url,
            "POST",
            "/api/auth/login",
            {"kullanici_adi": "smoke_user", "sifre": "smoke1234"},
            expected=200,
        )
        farm_token = farm_login["access_token"]

        _, scoped_farms = request(base_url, "GET", "/api/ciftlikler", token=farm_token, expected=200)
        assert len(scoped_farms) == 1 and scoped_farms[0]["id"] == farm_id, scoped_farms

        animal_payload = {
            "id": "api-smoke-h1",
            "ciftlik_id": farm_id,
            "resmi_kupe_no": "TRAPI001",
            "ciftlik_kupe_no": "CAPI001",
            "dogum_tarihi": "01/01/2024",
            "cins": "D\u00fcve",
            "foto_data": "data:image/jpeg;base64,abc",
            "son_guncelleme": "21/05/2026 01:10:00",
        }
        _, animal = request(base_url, "POST", "/api/hayvanlar", animal_payload, token=farm_token, expected=201)
        assert animal["foto_data"] == animal_payload["foto_data"]

        request(
            base_url,
            "PATCH",
            "/api/hayvanlar/api-smoke-h1",
            {
                "cins": "Sa\u011fmal \u0130nek",
                "gebe_mi": True,
                "gebelik_tarihi": "01/02/2026",
                "aktif_tohumlama_id": "smoke",
                "son_guncelleme": "21/05/2026 01:11:00",
            },
            token=farm_token,
            expected=200,
        )

        _, birth = request(
            base_url,
            "POST",
            "/api/hayvanlar/api-smoke-h1/dogumlar",
            {
                "tarih": "01/05/2026",
                "yavrular": [
                    {
                        "cins": "Di\u015fi Buza\u011f\u0131",
                        "resmi_kupe_no": "TRCALF001",
                        "ciftlik_kupe_no": "CCALF001",
                    }
                ],
            },
            token=farm_token,
            expected=201,
        )
        assert birth["yavrular"][0]["ciftlik_kupe_no"] == "CCALF001", birth

        _, calf = request(base_url, "GET", "/api/hayvanlar/CCALF001", token=farm_token, expected=200)
        assert calf["resmi_kupe_no"] == "TRCALF001", calf

        _, history = request(base_url, "GET", "/api/islem-gecmisi", token=farm_token, expected=200)
        assert any(item.get("hedef_id") == "api-smoke-h1" for item in history), history

        request(base_url, "DELETE", f"/api/ciftlikler/{farm_id}", token=admin_token, expected=200)
        expect_http_error(
            base_url,
            "POST",
            "/api/auth/login",
            401,
            {"kullanici_adi": "smoke_user", "sifre": "smoke1234"},
        )
        expect_http_error(base_url, "GET", "/api/hayvanlar/api-smoke-h1", 404, token=admin_token)
        expect_http_error(base_url, "GET", "/api/hayvanlar/CCALF001", 404, token=admin_token)
        _, remaining_users = request(base_url, "GET", "/api/kullanicilar", token=admin_token, expected=200)
        assert all(k.get("ciftlik_id") != farm_id for k in remaining_users), remaining_users
        _, remaining_animals = request(
            base_url,
            "GET",
            f"/api/hayvanlar?skip=0&limit=1000&arsiv_dahil=true&ciftlik_id={farm_id}",
            token=admin_token,
            expected=200,
        )
        assert remaining_animals == [], remaining_animals

        print(f"API smoke OK: {base_url}")
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
