"""Auction collection and price calculations adapted from Miaphys/ForeverPrices (MIT; see LICENSE)."""
import base64
import gzip
import json
import os
import time
import urllib.request

MARKET_SHARE = 0.25
OUTLIER_FACTOR = 1.5
AVG_ALPHA = 2 / 73
FORGET_AFTER = 14 * 86400

class Blizzard:
    def __init__(self, region: str):
        self.region = region
        self._token = None
        self._token_expires = 0.0

    def token(self) -> str:
        if self._token and time.time() < self._token_expires - 300:
            return self._token
        cid, secret = (os.environ["BNET_ID"], os.environ["BNET_SECRET"])
        basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        req = urllib.request.Request(
            "https://oauth.battle.net/token",
            data=b"grant_type=client_credentials",
            headers={"Authorization": f"Basic {basic}"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.load(r)
        self._token = tok["access_token"]
        self._token_expires = time.time() + tok.get("expires_in", 3600)
        return self._token

    def get(self, path: str):
        """Returns (json, Last-Modified header).

        Blizzard marks auction responses cacheable for a day, and conditional
        requests (If-Modified-Since) were answered "unchanged" from a stale copy
        after new data was out. So: plain requests, no-cache, compare timestamps ourselves.
        """
        url = f"https://{self.region}.api.blizzard.com{path}?namespace=dynamic-forever-{self.region}"
        headers = {
            "Authorization": f"Bearer {self.token()}",
            "Accept-Encoding": "gzip",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as r:
            lm = r.headers.get("Last-Modified")
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return json.loads(body), lm


def summarize(auctions: list, commodities: list) -> dict[int, tuple[int, int, int]]:
    """item id -> (min unit price, market value, quantity available), in copper."""
    units: dict[int, list[tuple[int, int]]] = {}
    for a in auctions:
        buyout = a.get("buyout")
        if not buyout:
            continue  # bid-only auctions don't tell us a price
        q = max(1, a.get("quantity", 1))
        units.setdefault(a["item"]["id"], []).append((buyout // q, q))
    for c in commodities:
        units.setdefault(c["item"]["id"], []).append((c["unit_price"], c.get("quantity", 1)))

    out = {}
    for item, lst in units.items():
        lst.sort()
        total = sum(q for _, q in lst)
        want = max(1, int(total * MARKET_SHARE))
        picked, n = [], 0
        for price, q in lst:
            take = min(q, want - n)
            picked.append((price, take))
            n += take
            if n >= want:
                break
        est = sum(p * q for p, q in picked) / n
        kept = [(p, q) for p, q in picked if p <= est * OUTLIER_FACTOR] or picked
        market = round(sum(p * q for p, q in kept) / sum(q for _, q in kept))
        out[item] = (lst[0][0], market, total)
    return out


def update_house(hstate: dict, snapshot: dict, updated: int) -> None:
    """Merge a new snapshot into a house's stored items (keeps the 3-day average)."""
    items = hstate.setdefault("items", {})
    for item, (mn, mkt, qty) in snapshot.items():
        key = str(item)
        old = items.get(key)
        avg = mkt if not old or not old[3] else round(old[3] + AVG_ALPHA * (mkt - old[3]))
        items[key] = [mn, mkt, qty, avg, updated]
    for key, row in list(items.items()):
        if int(key) not in snapshot:
            if updated - row[4] > FORGET_AFTER:
                del items[key]
            else:
                row[0] = row[1] = row[2] = 0  # not listed right now; keep the average
    hstate["updated"] = updated
