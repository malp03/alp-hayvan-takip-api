import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image


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


def multipart_request(base_url, path, files, fields=None, token=None, expected=None):
    boundary = "----alp-smoke-boundary"
    body = bytearray()
    fields = fields or {}
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    for field_name, filename, content_type, data in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base_url + path, data=bytes(body), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
            if expected is not None and resp.status != expected:
                raise AssertionError(f"POST {path} returned {resp.status}: {payload}")
            return resp.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"POST {path} returned {exc.code}: {payload}") from exc


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
    for key in ("ALP_API_URL", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ALP_PHOTO_BUCKET"):
        env.pop(key, None)
    env["APPDATA"] = tmp
    env["DATABASE_URL"] = "sqlite:///" + str(db_path).replace("\\", "/")
    env["ALP_AUTH_SECRET"] = "smoke-test-auth-secret-at-least-32-characters"
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
        _, health = request(base_url, "GET", "/api/health", expected=200)
        assert health["database"] == "connected", health
        assert health["auth_secret_configured"] is True, health

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

        _, admin_users = request(
            base_url, "GET", "/api/kullanicilar", token=admin_token, expected=200
        )
        bootstrap_admin = next(item for item in admin_users if item["rol"] == "admin")
        expect_http_error(
            base_url,
            "PATCH",
            f"/api/kullanicilar/{bootstrap_admin['id']}",
            400,
            {"aktif": False},
            token=admin_token,
        )
        expect_http_error(
            base_url,
            "DELETE",
            f"/api/kullanicilar/{bootstrap_admin['id']}",
            400,
            token=admin_token,
        )

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
        expect_http_error(
            base_url,
            "POST",
            "/api/kullanicilar",
            400,
            {
                "kullanici_adi": "SMOKE_USER",
                "sifre": "smoke1234",
                "rol": "ciftlik",
                "ciftlik_id": farm_id,
                "aktif": True,
            },
            token=admin_token,
        )
        expect_http_error(
            base_url,
            "PATCH",
            f"/api/kullanicilar/{user['id']}",
            404,
            {"ciftlik_id": "missing-farm"},
            token=admin_token,
        )

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
            "resmi_kupe_no": "TR987654321",
            "ciftlik_kupe_no": "CAPI123456",
            "dogum_tarihi": "01/01/2024",
            "cins": "D\u00fcve",
            "irk": "Simental",
            "foto_path": "smoke/api-smoke-h1/original.jpg",
            "son_guncelleme": "21/05/2026 01:10:00",
        }
        _, animal = request(base_url, "POST", "/api/hayvanlar", animal_payload, token=farm_token, expected=201)
        assert animal["foto_path"] == animal_payload["foto_path"]
        assert animal["irk"] == "Simental", animal
        initial_version = animal["son_guncelleme"]
        def png_bytes(color):
            buffer = BytesIO()
            Image.new("RGB", (12, 12), color).save(buffer, format="PNG")
            return buffer.getvalue()

        tiny_png = png_bytes((255, 0, 0))
        tiny_png_2 = png_bytes((0, 80, 255))
        _, photo_upload = multipart_request(
            base_url,
            "/api/hayvanlar/api-smoke-h1/fotograflar",
            [
                ("fotograflar", "smoke-1.png", "image/png", tiny_png),
                ("fotograflar", "smoke-2.png", "image/png", tiny_png_2),
            ],
            token=farm_token,
            expected=200,
        )
        assert (
            len(photo_upload.get("foto_paths") or [])
            + len(photo_upload.get("foto_urls") or [])
            + len(photo_upload.get("foto_datas") or [])
        ) == 3, photo_upload
        _, photo_delete = request(
            base_url,
            "DELETE",
            "/api/hayvanlar/api-smoke-h1/fotograflar?foto_path="
            + urllib.parse.quote(animal_payload["foto_path"], safe=""),
            token=farm_token,
            expected=200,
        )
        assert (
            len(photo_delete.get("foto_paths") or [])
            + len(photo_delete.get("foto_urls") or [])
            + len(photo_delete.get("foto_datas") or [])
        ) == 2, photo_delete

        _, normal_search = request(base_url, "GET", "/api/hayvanlar?q=TR%209876", token=farm_token, expected=200)
        assert any(item["id"] == "api-smoke-h1" for item in normal_search), normal_search
        _, last6_search = request(base_url, "GET", "/api/hayvanlar?q=123456", token=farm_token, expected=200)
        assert any(item["id"] == "api-smoke-h1" for item in last6_search), last6_search
        _, camera_search = request(base_url, "GET", "/api/hayvanlar/bul?ref=OCR-000123456&kaynak=kamera", token=farm_token, expected=200)
        assert camera_search["tekil"] and camera_search["hayvanlar"][0]["id"] == "api-smoke-h1", camera_search
        _, official_camera = request(base_url, "GET", "/api/hayvanlar/bul?ref=TR987654321&kaynak=kamera", token=farm_token, expected=200)
        assert official_camera["tekil"] and official_camera["hayvanlar"][0]["id"] == "api-smoke-h1", official_camera
        _, camera_abbr = request(base_url, "GET", "/api/hayvanlar/bul?ref=TR%209876&kaynak=kamera", token=farm_token, expected=200)
        assert camera_abbr["eslesme_sayisi"] == 0, camera_abbr

        _, young_female = request(
            base_url,
            "POST",
            "/api/hayvanlar",
            {
                "id": "api-smoke-young-female",
                "ciftlik_id": farm_id,
                "resmi_kupe_no": "TR-YOUNG-FEMALE",
                "dogum_tarihi": "01/01/2025",
                "cins": "Düve",
            },
            token=farm_token,
            expected=201,
        )
        expect_http_error(
            base_url,
            "POST",
            "/api/hayvanlar",
            400,
            {
                "id": "api-smoke-invalid-embedded-insemination",
                "ciftlik_id": farm_id,
                "dogum_tarihi": "01/01/2025",
                "cins": "D\u00fcve",
                "tohumlamalar": [{"tarih": "01/07/2025", "sekil": "Bo\u011fa"}],
            },
            token=farm_token,
        )
        _, valid_insemination = request(
            base_url,
            "POST",
            "/api/hayvanlar/api-smoke-young-female/tohumlamalar",
            {"tarih": "02/01/2026", "sekil": "Boğa"},
            token=farm_token,
            expected=201,
        )
        expect_http_error(
            base_url,
            "PATCH",
            f"/api/hayvanlar/api-smoke-young-female/tohumlamalar/{valid_insemination['id']}",
            400,
            {"tarih": "01/07/2025"},
            token=farm_token,
        )

        request(
            base_url,
            "POST",
            "/api/hayvanlar",
            {
                "id": "api-smoke-male",
                "ciftlik_id": farm_id,
                "resmi_kupe_no": "TR-SMOKE-MALE",
                "dogum_tarihi": "01/01/2024",
                "cins": "Dana",
                "cinsiyet": "Erkek",
            },
            token=farm_token,
            expected=201,
        )
        expect_http_error(
            base_url,
            "POST",
            "/api/hayvanlar",
            400,
            {
                "id": "api-smoke-invalid-embedded-birth",
                "ciftlik_id": farm_id,
                "dogum_tarihi": "01/01/2024",
                "cins": "Dana",
                "cinsiyet": "Erkek",
                "dogumlar": [{"tarih": "01/05/2026", "yavrular": []}],
            },
            token=farm_token,
        )
        expect_http_error(
            base_url,
            "POST",
            "/api/hayvanlar/api-smoke-male/dogumlar",
            400,
            {"tarih": "01/05/2026", "yavrular": []},
            token=farm_token,
        )

        expect_http_error(
            base_url,
            "POST",
            "/api/hayvanlar/api-smoke-young-female/asi-prosedurler",
            400,
            {
                "ad": "Tarih sırası testi",
                "tarih": "10/01/2026",
                "sonraki_tarih": "01/01/2026",
            },
            token=farm_token,
        )
        _, valid_procedure = request(
            base_url,
            "POST",
            "/api/hayvanlar/api-smoke-young-female/asi-prosedurler",
            {
                "ad": "Geçerli prosedür",
                "tarih": "10/01/2026",
                "sonraki_tarih": "10/02/2026",
            },
            token=farm_token,
            expected=201,
        )
        expect_http_error(
            base_url,
            "PATCH",
            f"/api/hayvanlar/api-smoke-young-female/asi-prosedurler/{valid_procedure['id']}",
            400,
            {"sonraki_tarih": "01/01/2026"},
            token=farm_token,
        )

        _, patched_animal = request(
            base_url,
            "PATCH",
            "/api/hayvanlar/api-smoke-h1?" + urllib.parse.urlencode(
                {"beklenen_son_guncelleme": photo_delete["son_guncelleme"]}
            ),
            {
                "cins": "Sa\u011fmal \u0130nek",
                "irk": "Holstein",
                "gebe_mi": True,
                "gebelik_tarihi": "01/02/2026",
                "aktif_tohumlama_id": "smoke",
                "son_guncelleme": (datetime.now() + timedelta(minutes=1)).strftime("%d/%m/%Y %H:%M:%S"),
            },
            token=farm_token,
            expected=200,
        )
        assert patched_animal["irk"] == "Holstein", patched_animal
        expect_http_error(
            base_url,
            "PATCH",
            "/api/hayvanlar/api-smoke-h1?" + urllib.parse.urlencode(
                {"beklenen_son_guncelleme": initial_version}
            ),
            409,
            {"irk": "Simental"},
            token=farm_token,
        )

        _, birth = request(
            base_url,
            "POST",
            "/api/hayvanlar/api-smoke-h1/dogumlar",
            {
                "tarih": "01/05/2026",
                "yavrular": [
                    {
                        "hayvan_id": "offline_yavru_smoke_1",
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
        assert birth["yavrular"][0]["hayvan_id"] == "offline_yavru_smoke_1", birth

        _, calf = request(base_url, "GET", "/api/hayvanlar/offline_yavru_smoke_1", token=farm_token, expected=200)
        assert calf["resmi_kupe_no"] == "TRCALF001", calf

        _, history = request(base_url, "GET", "/api/islem-gecmisi", token=farm_token, expected=200)
        assert any(item.get("hedef_id") == "api-smoke-h1" for item in history), history

        _, system_status = request(base_url, "GET", "/api/sistem-durumu", token=admin_token, expected=200)
        assert system_status["kayit_sayilari"]["hayvan"] >= 2, system_status
        assert system_status["storage"]["aktif"] is False, system_status
        assert system_status["fotograflar"]["database_base64_adet"] >= 1, system_status
        _, data_health = request(base_url, "GET", "/api/admin/veri-sagligi", token=admin_token, expected=200)
        assert data_health["genel_durum"] in {"saglikli", "uyari", "kritik"}, data_health
        assert isinstance(data_health.get("kontroller"), list), data_health

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
        _, reset = request(base_url, "POST", "/api/admin/test-verilerini-sifirla", token=admin_token, expected=200)
        assert reset["status"] == "ok", reset
        _, final_users = request(base_url, "GET", "/api/kullanicilar", token=admin_token, expected=200)
        assert final_users and all(k["rol"] == "admin" for k in final_users), final_users
        _, final_animals = request(base_url, "GET", "/api/hayvanlar?arsiv_dahil=true", token=admin_token, expected=200)
        assert final_animals == [], final_animals

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
