"""Collect public EU and US auction summaries, preserving each house's rolling average."""
import json
import os
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from pricing import Blizzard, summarize, update_house

BASE = "https://prismicious.github.io/forever-auction-feed"


def previous(region):
    try:
        with urlopen(f"{BASE}/{region}.json?run={time.time_ns()}", timeout=45) as reply:
            data = json.load(reply)
    except HTTPError as error:
        if error.code == 404:
            return {}
        raise
    if data["region"] != region or data["format"] != 1:
        raise ValueError("Incompatible previous feed")
    return data["houses"]


def scan(region):
    api = Blizzard(region)
    houses = previous(region)
    base = "/data/wow/ruleset/1/auctions/"
    index, _ = api.get(base)
    ids = set()
    for entry in index["auctions"]:
        house_id = str(entry["id"])
        ids.add(house_id)
        house = houses.setdefault(house_id, {})
        house["name"] = entry["name"]["en_US"]
        items, gear_header = api.get(base + house_id)
        goods, goods_header = api.get(base + house_id + "/commodities")
        stamps = [int(parsedate_to_datetime(h).timestamp()) for h in (gear_header, goods_header)]
        if items["id"] != entry["id"] or not all(
            doc["_links"]["self"]["href"] and isinstance(doc.get("auctions", []), list)
            for doc in (items, goods)
        ):
            raise ValueError("Invalid listing data")
        if stamps == house.get("timestamps"):
            continue
        if house.get("timestamps") and any(s < old for s, old in zip(stamps, house["timestamps"])):
            raise ValueError("Upstream timestamps regressed")
        update_house(house, summarize(items.get("auctions", []), goods.get("auctions", [])), min(stamps))
        house["timestamps"] = stamps
    if not {"110", "113", "116"}.issubset(ids):
        raise ValueError("Incomplete PvP house index")
    return {"format": 1, "region": region, "generated": int(time.time()),
            "houses": {key: houses[key] for key in sorted(ids, key=int)}}


if __name__ == "__main__":
    out = Path("site")
    out.mkdir(exist_ok=True)
    for region in ("eu", "us"):
        feed = scan(region)
        (out / f"{region}.json").write_text(json.dumps(feed, separators=(",", ":")), encoding="utf-8")
        print(region, len(feed["houses"]), "houses collected")
    (out / "build.json").write_text(json.dumps({"sha": os.environ["GITHUB_SHA"], "run": os.environ["GITHUB_RUN_ID"]}))
    (out / "index.html").write_text('<title>WoW Forever auction prices</title><h1>WoW Forever auction prices</h1><p><a href="eu.json">Europe</a> &middot; <a href="us.json">United States</a></p><p>Auction listings from Blizzard. Collector and pricing calculations adapted from <a href="https://github.com/Miaphys/ForeverPrices">ForeverPrices by Miaphys</a> (MIT). Published by prismicious.</p>')
