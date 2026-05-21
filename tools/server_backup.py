import json
import os
import pathlib
import socket
import sys
import time
import urllib.error
import urllib.request


def request_json(method, url, payload=None, token=None, timeout=30):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


def request_json_retry(method, url, payload=None, token=None, timeout=30, attempts=4, label="API istegi"):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            if attempt > 1:
                print(f"{label}: {attempt}. deneme")
            return request_json(method, url, payload=payload, token=token, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raise
            last_error = exc
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
            last_error = exc

        if attempt < attempts:
            wait_seconds = min(12, attempt * 3)
            print(f"{label}: hata/timeout, {wait_seconds} sn sonra tekrar denenecek: {last_error}", file=sys.stderr)
            time.sleep(wait_seconds)

    raise RuntimeError(f"{label}: {attempts} denemeden sonra basarisiz: {last_error}")


def main():
    api_url = os.environ.get("ALP_API_URL", "").rstrip("/")
    username = os.environ.get("ALP_BACKUP_USERNAME", "")
    password = os.environ.get("ALP_BACKUP_PASSWORD", "")
    output_dir = pathlib.Path(os.environ.get("ALP_BACKUP_DIR", "backups/server"))
    keep = int(os.environ.get("ALP_BACKUP_KEEP", "30"))
    attempts = int(os.environ.get("ALP_BACKUP_RETRIES", "5"))
    login_timeout = int(os.environ.get("ALP_BACKUP_LOGIN_TIMEOUT", "90"))
    download_timeout = int(os.environ.get("ALP_BACKUP_DOWNLOAD_TIMEOUT", "180"))

    if not api_url or not username or not password:
        print("ALP_API_URL, ALP_BACKUP_USERNAME ve ALP_BACKUP_PASSWORD zorunludur.", file=sys.stderr)
        return 2

    print(f"API uyandiriliyor: {api_url}/api/health")
    request_json_retry(
        "GET",
        f"{api_url}/api/health",
        timeout=login_timeout,
        attempts=attempts,
        label="API health",
    )

    login = request_json_retry(
        "POST",
        f"{api_url}/api/auth/login",
        {"kullanici_adi": username, "sifre": password},
        timeout=login_timeout,
        attempts=attempts,
        label="API login",
    )
    token = (login or {}).get("access_token")
    if not token:
        print("API token alinamadi.", file=sys.stderr)
        return 3

    backup = request_json_retry(
        "GET",
        f"{api_url}/api/yedek",
        token=token,
        timeout=download_timeout,
        attempts=attempts,
        label="API yedek indirme",
    )
    if not backup:
        print("API yedek cevabi bos geldi.", file=sys.stderr)
        return 4
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"alp_online_yedek_{stamp}.json"
    output_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")

    backups = sorted(output_dir.glob("alp_online_yedek_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        old.unlink(missing_ok=True)

    print(output_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
