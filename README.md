# WoW Forever auction feed

Hourly public EU PvP Horde auction summaries (house 113) collected directly from Blizzard's Battle.net Game Data API. Read [EU PvP Horde prices](https://mgfzcwavbqb4eria.public.blob.vercel-storage.com/eu.json). Each house carries its source timestamp. A failed collection leaves the previous snapshot online.

The collector and pricing formulas are adapted from [ForeverPrices by Miaphys](https://github.com/Miaphys/ForeverPrices/tree/35a776002b15e8d769d6722805db0c51ebc9b188), under the included MIT license. Blizzard supplies the listings. This independent publication is operated by prismicious.

Each item row holds the lowest unit price, market price, quantity, three-day average and last-seen timestamp. Prices are in copper. The five-field row stays compatible with existing consumers. The feed contains aggregate prices only.

## Real price history

The Vercel publisher records each distinct Blizzard source scan in the existing Blob
store's `history-eu.json.gz`, separate from the small `eu.json` summary. It prunes
records older than thirty days on each run. This is the only historical file; PCs
and addons download only the current summary. It contains timestamped item market
prices, not account data, buyer identities or individual auction listings.

For each item, `houses["113"].averages[itemID]` holds
`[mean3, count3, mean7, count7, mean30, count30]`. Each mean is the exact arithmetic
mean (rounded to copper) of actual listed market-price observations inside the
trailing 3, 7 or 30 days. These are observed auction asking-price means, not sale
prices or volume-weighted transaction averages. Missing/unlisted observations do
not count as free items. Duplicate source timestamps count once. A retry can correct
that timestamp's observation without adding a sample. No EMA seeds these means.
The original row's fourth field also receives the real three-day mean.

`house.history` reports `method: "scan_mean"`, the first retained-collection timestamp
`started`, and each window's recorded scan count and elapsed-window `complete` flag.
The flag describes warm-up, not proof of gap-free hourly coverage. Counts expose
missed scans. During warm-up the means use only available real observations; they
are not invented historical values. The first current production snapshot may be
seeded as one genuine observation; its old smoothed average is discarded. The
legacy standalone Pages collector retains its old calculation; consumers requiring
measured averages use the production Blob summary and its `history.method` marker.

## Vercel publisher

Vercel Schedules invokes `/api/refresh` each hour from minute 30 UTC. That leaves time for Blizzard's observed updates around minute 23 and Vercel's normal scheduling delay before the overlay's minute 49 refresh. Set the sensitive Production environment variables `BNET_ID`, `BNET_SECRET`, and `CRON_SECRET`. Connect a public Blob store for `BLOB_READ_WRITE_TOKEN` and set `AUCTION_BLOB_BASE` to its public origin. The schedule supplies the bearer credential from `CRON_SECRET`.

The Vercel publisher starts with the Pages snapshot and then uses the last Blob
snapshot. Both the compressed history and public summary use conditional ETag
writes. History commits first; a failed or conflicting history write prevents
publication of new averages. A failed summary write leaves the old summary intact;
the next run reconciles the saved history without counting the scan twice. Invalid
or oversized history fails visibly rather than resetting collection. Verify that
scheduled runs succeed and `history.method` appears in `eu.json`. Check house
`113`'s `updated` timestamp for source age and `generated` for publication time.

Vercel deploys the publisher from this repository's `main` branch. The GitHub Pages workflow can still be dispatched manually for legacy consumers or rollback.
