"""Collect EU PvP Horde auction summaries, preserving each house's rolling average."""
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


def scan(region, *, previous_houses=None):
    api = Blizzard(region)
    if previous_houses is None:
        previous_houses = previous(region)
    base = "/data/wow/ruleset/1/auctions/"
    house_id = "113"
    house = previous_houses.get(house_id, {})
    house["name"] = "Horde Auction House"
    items, gear_header = api.get(base + house_id)
    goods, goods_header = api.get(base + house_id + "/commodities")
    stamps = [int(parsedate_to_datetime(h).timestamp()) for h in (gear_header, goods_header)]
    if items["id"] != int(house_id) or not all(
        doc["_links"]["self"]["href"] and isinstance(doc.get("auctions", []), list)
        for doc in (items, goods)
    ):
        raise ValueError("Invalid listing data")
    if house.get("timestamps") and any(s < old for s, old in zip(stamps, house["timestamps"])):
        raise ValueError("Upstream timestamps regressed")
    if stamps != house.get("timestamps"):
        update_house(house, summarize(items.get("auctions", []), goods.get("auctions", [])), min(stamps))
    house["timestamps"] = stamps
    return {"format": 1, "region": region, "generated": int(time.time()),
            "houses": {house_id: house}}


if __name__ == "__main__":
    out = Path("site")
    out.mkdir(exist_ok=True)
    feed = scan("eu")
    (out / "eu.json").write_text(json.dumps(feed, separators=(",", ":")), encoding="utf-8")
    (out / "build.json").write_text(json.dumps({"sha": os.environ["GITHUB_SHA"], "run": os.environ["GITHUB_RUN_ID"]}))
    (out / "index.html").write_text('<title>WoW Forever auction prices</title><h1>WoW Forever auction prices</h1><p><a href="eu.json">EU PvP Horde</a></p><p>Auction listings from Blizzard. Collector and pricing calculations adapted from <a href="https://github.com/Miaphys/ForeverPrices">ForeverPrices by Miaphys</a> (MIT). Published by prismicious.</p>')
