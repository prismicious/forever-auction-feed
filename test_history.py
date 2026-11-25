import copy
import unittest
from unittest.mock import patch

import history
from api import refresh as publisher


def snapshot(at, price=100, listed=True):
    row = [price if listed else 0, price if listed else 0, 1 if listed else 0, 999999, at]
    return dict(format=1, region="eu", generated=at,
                houses={"113": dict(updated=at, name="Horde", items={"2589": row})})


class HistoryTests(unittest.TestCase):
    def test_exact_trailing_windows_and_boundaries(self):
        day = history.DAY
        now = 100 * day
        state = history.empty()
        for at, price in ((now-30*day, 1), (now-8*day, 100), (now-4*day, 200),
                          (now-3*day, 300), (now-day, 500), (now, 700)):
            doc = snapshot(at, price)
            history.update(state, doc, at)
        house = doc["houses"]["113"]
        self.assertEqual(house["averages"]["2589"], [600, 2, 425, 4, 360, 5])
        self.assertEqual(house["items"]["2589"][3], 600)
        self.assertEqual(len(house["items"]["2589"]), 5)
        self.assertEqual(len(state["scans"]), 5)
        self.assertTrue(house["history"]["windows"]["30"]["complete"])

    def test_duplicate_retries_and_corrected_same_timestamp_count_once(self):
        state = history.empty()
        for price in (100, 100, 200):
            doc = snapshot(10000, price)
            history.update(state, doc, 10000)
        self.assertEqual(doc["houses"]["113"]["averages"]["2589"], [200, 1, 200, 1, 200, 1])
        self.assertEqual(len(state["scans"]), 1)

    def test_unlisted_is_missing_observation_not_zero_price(self):
        state = history.empty()
        history.update(state, snapshot(10000, 100), 10000)
        doc = snapshot(11000, listed=False)
        history.update(state, doc, 11000)
        self.assertEqual(doc["houses"]["113"]["averages"]["2589"], [100, 1, 100, 1, 100, 1])
        self.assertEqual(doc["houses"]["113"]["items"]["2589"][3], 100)
        self.assertFalse(doc["houses"]["113"]["history"]["windows"]["3"]["complete"])

    def test_old_ema_never_seeds_a_measured_mean(self):
        doc = snapshot(10000, 123)
        history.update(history.empty(), doc, 10000)
        self.assertEqual(doc["houses"]["113"]["items"]["2589"][3], 123)
        self.assertEqual(doc["houses"]["113"]["history"]["method"], "scan_mean")

    def test_regression_corruption_and_future_scan_fail_closed(self):
        state = history.empty(); history.update(state, snapshot(10000), 10000)
        for at in (9999, 11000):
            with self.assertRaises(ValueError): history.update(copy.deepcopy(state), snapshot(at), 10000)
        for scans in ([[10000, "1:0"]], [[10000, "1:1;1:2"]], [[10000, "bad"]], [[10000, "1:2"], [9999, "1:2"]]):
            bad = copy.deepcopy(state); bad["scans"] = scans
            with self.assertRaises(ValueError): history.validate(bad)

    def test_publication_commits_history_before_summary_with_both_etags(self):
        old = snapshot(10000, 100)
        new = snapshot(11000, 200)
        with patch.dict(publisher.os.environ, {"BLOB_READ_WRITE_TOKEN": "test", "AUCTION_BLOB_BASE": "https://example.invalid"}), \
                patch.object(publisher, "read_snapshot", return_value=(old, "price-etag")), \
                patch.object(publisher, "read_history", return_value=(history.empty(), None)), \
                patch.object(publisher, "scan", return_value=new), \
                patch.object(publisher.time, "time", return_value=11000), \
                patch.object(publisher, "put_snapshot", return_value="published") as put:
            publisher.refresh()
        self.assertEqual(put.call_count, 2)
        self.assertEqual(put.call_args_list[0].kwargs, {"history": True})
        self.assertEqual(put.call_args_list[0].args[1], None)
        self.assertEqual(put.call_args_list[1].args[1], "price-etag")
        self.assertEqual(put.call_args_list[1].args[0]["houses"]["113"]["averages"]["2589"], [150, 2, 150, 2, 150, 2])


if __name__ == "__main__":
    unittest.main()
