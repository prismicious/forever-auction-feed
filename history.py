"""Exact arithmetic means of observed market prices in trailing UTC-second windows.

Keep compact, timestamped scan records for thirty days. Never infer a missing
observation or treat an unlisted item as a zero-priced listing.
"""
from collections import defaultdict

DAY = 86400
WINDOWS = (3, 7, 30)


def empty():
    return dict(format=1, region="eu", house=113, started=None, scans=[])


def validate(history):
    if (history.get("format") != 1 or history.get("region") != "eu"
            or history.get("house") != 113 or not isinstance(history.get("scans"), list)):
        raise ValueError("Invalid history header")
    previous = 0
    for stamp, packed in history["scans"]:
        if type(stamp) is not int or stamp <= previous or not isinstance(packed, str):
            raise ValueError("Invalid history scan")
        previous = stamp
        seen = set()
        for item, price in unpack(packed):
            if item in seen or item <= 0 or price <= 0:
                raise ValueError("Invalid history item")
            seen.add(item)
    started = history.get("started")
    if history["scans"] and (type(started) is not int or not 0 < started <= history["scans"][0][0]):
        raise ValueError("Invalid history start")
    return history


def unpack(packed):
    for row in packed.split(";"):
        if row:
            item, price = row.split(":")
            yield int(item), int(price)


def add(history, house, now):
    stamp = house["updated"]
    if type(stamp) is not int or stamp > now or stamp <= now - 30 * DAY:
        raise ValueError("History scan is stale or future")
    scans = history["scans"]
    if scans and stamp < scans[-1][0]:
        raise ValueError("History source timestamp regressed")
    packed = ";".join(f"{int(item)}:{row[1]}" for item, row in sorted(house["items"].items())
                      if row[2] > 0 and row[1] > 0 and row[4] == stamp)
    if scans and stamp == scans[-1][0]:
        # Retrying the same Blizzard snapshot never counts it twice.
        scans[-1] = [stamp, packed]
    else:
        scans.append([stamp, packed])
    if history["started"] is None:
        history["started"] = stamp
    history["scans"] = [row for row in scans if row[0] > now - 30 * DAY]


def summarize(history, house, now):
    totals = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    scans = [0, 0, 0]
    for stamp, packed in history["scans"]:
        windows = [i for i, days in enumerate(WINDOWS) if now - days * DAY < stamp <= now]
        for i in windows:
            scans[i] += 1
        for item, price in unpack(packed):
            total = totals[str(item)]
            for i in windows:
                total[2*i] += price
                total[2*i+1] += 1
    averages = {}
    for item, total in totals.items():
        averages[item] = [value for i in range(3) for value in
                          (round(total[2*i] / total[2*i+1]) if total[2*i+1] else 0, total[2*i+1])]
    # Preserve the original five-field row contract for existing consumers.
    # Field 3 becomes the measured 3-day mean, never the old smoothed value.
    for item, row in house["items"].items():
        row[3] = averages.get(item, [0])[0]
    house["averages"] = averages
    house["history"] = dict(method="scan_mean", started=history["started"],
                            windows={str(days): dict(scans=scans[i],
                                complete=history["started"] <= now - days * DAY)
                                for i, days in enumerate(WINDOWS)})


def update(history, snapshot, now):
    validate(history)
    house = snapshot["houses"]["113"]
    add(history, house, now)
    summarize(history, house, now)
    return history
