# WoW Forever auction feed

Hourly public EU PvP Horde auction summaries (house 113) collected directly from Blizzard's Battle.net Game Data API. Read [EU PvP Horde prices](https://mgfzcwavbqb4eria.public.blob.vercel-storage.com/eu.json). Each house carries its source timestamp. A failed collection leaves the previous snapshot online.

The collector and pricing formulas are adapted from [ForeverPrices by Miaphys](https://github.com/Miaphys/ForeverPrices/tree/35a776002b15e8d769d6722805db0c51ebc9b188), under the included MIT license. Blizzard supplies the listings. This independent publication is operated by prismicious.

Each item row holds the lowest unit price, market price, quantity, rolling three-day average and last-seen timestamp. Prices are in copper. Previous state comes from this publication. The initial average starts with the first observation. The feed contains aggregate prices only.

## Vercel publisher

Vercel Schedules invokes `/api/refresh` each hour from minute 30 UTC. That leaves time for Blizzard's observed updates around minute 23 and Vercel's normal scheduling delay before the overlay's minute 49 refresh. Set the sensitive Production environment variables `BNET_ID`, `BNET_SECRET`, and `CRON_SECRET`. Connect a public Blob store for `BLOB_READ_WRITE_TOKEN` and set `AUCTION_BLOB_BASE` to its public origin. The schedule supplies the bearer credential from `CRON_SECRET`.

The Vercel publisher starts with the Pages snapshot and uses the last Blob snapshot for subsequent rolling averages. The Blob write is conditional on the previous snapshot's ETag. Verify that scheduled runs succeed and the public `eu.json` advances before switching clients. Check house `113`'s `updated` timestamp for the source age and `generated` for publication time.

Vercel deploys the publisher from this repository's `main` branch. The GitHub Pages workflow can still be dispatched manually for legacy consumers or rollback.
