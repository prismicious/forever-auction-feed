"""Publish the EU feed when Vercel Schedules invokes this endpoint."""
import hmac
import gzip
import json
import os
import time
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from publish import previous, scan
from history import empty, update, validate

BLOB_PATH = "eu.json"
HISTORY_PATH = "history-eu.json.gz"
# Use the same conditional PUT headers as @vercel/blob. The Python SDK's put
# method does not expose ifMatch in version 0.6.2.
BLOB_UPLOAD = "https://vercel.com/api/blob?pathname=eu.json"


def read_snapshot(url):
    request = Request(f"{url}?run={time.time_ns()}", headers={"Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=10) as response:
            snapshot = json.load(response)
            etag = response.headers.get("ETag")
    except HTTPError as error:
        if error.code == 404:
            return None, None
        raise
    if snapshot["format"] != 1 or snapshot["region"] != "eu" or not etag:
        raise ValueError("Invalid previous Vercel snapshot")
    return snapshot, etag


def put_snapshot(snapshot, etag, token, *, history=False):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/gzip" if history else "application/json",
        "x-api-version": "13",
        "x-vercel-blob-access": "public",
        "x-cache-control-max-age": "60",
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1" if etag else "0",
    }
    if etag:
        headers["x-if-match"] = etag
    body = json.dumps(snapshot, separators=(",", ":")).encode()
    url = BLOB_UPLOAD
    if history:
        body = gzip.compress(body, mtime=0)
        url = BLOB_UPLOAD.replace(BLOB_PATH, HISTORY_PATH)
    request = Request(url, data=body, headers=headers, method="PUT")
    with urlopen(request, timeout=15) as response:
        return json.load(response)["url"]


def read_history(url):
    request = Request(f"{url}?run={time.time_ns()}", headers={"Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=30) as response:
            etag = response.headers.get("ETag")
            with gzip.GzipFile(fileobj=response) as stream:
                payload = stream.read(128 * 1024 * 1024 + 1)
    except HTTPError as error:
        if error.code == 404:
            return empty(), None
        raise
    if not etag or len(payload) > 128 * 1024 * 1024:
        raise ValueError("Invalid or oversized price history")
    return validate(json.loads(payload)), etag


def refresh():
    token = os.environ["BLOB_READ_WRITE_TOKEN"]
    url = f'{os.environ["AUCTION_BLOB_BASE"].rstrip("/")}/{BLOB_PATH}'
    old, etag = read_snapshot(url)
    history, history_etag = read_history(url.replace(BLOB_PATH, HISTORY_PATH))
    now = int(time.time())
    if (not history["scans"] and old is not None
            and now - 30 * 86400 < old["houses"]["113"]["updated"] <= now):
        # This single actual snapshot is valid evidence; its old EMA is not.
        update(history, old, now)
    houses = previous("eu") if old is None else old["houses"]
    snapshot = scan("eu", previous_houses=houses)
    now = snapshot["generated"]
    update(history, snapshot, now)
    # Commit history before advertising its means. Both objects use conditional
    # writes: a concurrent invocation cannot overwrite a newer observation.
    put_snapshot(history, history_etag, token, history=True)
    published = put_snapshot(snapshot, etag, token)
    return {
        "url": published,
        "generated": snapshot["generated"],
        "updated": snapshot["houses"]["113"]["updated"],
    }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        secret = os.environ.get("CRON_SECRET")
        header = self.headers.get("Authorization", "")
        if not secret or not hmac.compare_digest(header.encode(), f"Bearer {secret}".encode()):
            self.send_error(401)
            return
        try:
            result = refresh()
        except Exception as error:
            # Keep token values and provider response bodies out of logs.
            print(f"auction refresh failed: {type(error).__name__} {getattr(error, 'code', '')}")
            self.send_error(502, "Auction publication failed")
            return
        body = json.dumps(result).encode()
        print(f"auction refresh succeeded: {body.decode()}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)
