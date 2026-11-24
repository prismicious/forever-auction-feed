# WoW Forever auction feed

Hourly public EU PvP Horde auction summaries (house 113) collected directly from Blizzard's Battle.net Game Data API by this repository's GitHub Actions runner. Read [EU PvP Horde prices](https://prismicious.github.io/forever-auction-feed/eu.json). Each house carries its source timestamp. An hourly schedule can run late. A failed collection leaves the previous deployment online.

The collector and pricing formulas are adapted from [ForeverPrices by Miaphys](https://github.com/Miaphys/ForeverPrices/tree/35a776002b15e8d769d6722805db0c51ebc9b188), under the included MIT license. Blizzard supplies the listings. This independent publication is operated by prismicious.

Each item row holds the lowest unit price, market price, quantity, rolling three-day average and last-seen timestamp. Prices are in copper. Previous state comes from this publication. The initial average starts with the first observation. The feed contains aggregate prices only. Set the Actions secrets BNET_ID and BNET_SECRET, select GitHub Actions for Pages, and dispatch Publish auction prices to initialize a deployment.

## Vercel publisher

Vercel Schedules invokes `/api/refresh` at minute 17 UTC each hour. Set the sensitive Production environment variables `BNET_ID`, `BNET_SECRET`, and `CRON_SECRET`. Connect a public Blob store for `BLOB_READ_WRITE_TOKEN` and set `AUCTION_BLOB_BASE` to its public origin. The schedule supplies the bearer credential from `CRON_SECRET`.

The Vercel publisher starts with the Pages snapshot and uses the last Blob snapshot for subsequent rolling averages. The Blob write is conditional on the previous snapshot's ETag. Verify that scheduled runs succeed and the public `eu.json` advances before switching clients. Check house `113`'s `updated` timestamp for the source age and `generated` for publication time.
