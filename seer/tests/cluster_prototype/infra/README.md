# AWS definitions

No Step Functions and no database: a schedule invokes scrape, and the manifest scrape writes to S3 invokes build. Build also fetches story thumbnails, so it needs internet egress (no VPC, or a VPC with a NAT).

| File | What | Apply |
| --- | --- | --- |
| `scheduler.md` | EventBridge Scheduler: one hourly schedule per edition (08:00-22:00 `Europe/Skopje`) invoking scrape; build's reserved concurrency of 1 | see the file |
| `s3-raw-notification.json` | S3 event notification: invoke build on `s3:ObjectCreated:*` under `runs/` ending in `.json`. Replace `${BuildFunctionArn}` first (for example with `envsubst`). | `aws s3api put-bucket-notification-configuration --bucket <raw-bucket> --notification-configuration file://s3-raw-notification.json` |
| `s3-raw-lifecycle.json` | Expires `raw/`, `runs/` and `builds/` after 730 days, `archive/` after 1095 and `logs/` after 7 (safety net for the reader-statistics logs); aborts incomplete multipart uploads after 1 day | `aws s3api put-bucket-lifecycle-configuration --bucket <raw-bucket> --lifecycle-configuration file://s3-raw-lifecycle.json` |
| `s3-raw-intelligent-tiering.json` | Intelligent-Tiering archive tiers for `raw/`: Archive Access after 90 days, Deep Archive Access after 180 | `aws s3api put-bucket-intelligent-tiering-configuration --bucket <raw-bucket> --id raw-archive --intelligent-tiering-configuration file://s3-raw-intelligent-tiering.json` |
| `s3-site-lifecycle.json` | Site bucket: expires `{e}/story/`, day and month pages (`{e}/20*`) and `thumbs/` after 1095 days and `system/admin/data/` after 400; aborts incomplete multipart uploads after 1 day. Add a rule per new edition. | `aws s3api put-bucket-lifecycle-configuration --bucket <site-bucket> --lifecycle-configuration file://s3-site-lifecycle.json` |


**Reader statistics logs:** enable CloudFront standard logging to `s3://<raw-bucket>/logs/cloudfront/` (the build Lambda reads and deletes these files; see `lambdas/build/READERS.md`). Where the logging version allows field selection (v2), leave out `c-ip`; the Lambda never reads it either way. Give the build role `s3:ListBucket`, `GetObject` and `DeleteObject` on that prefix.
