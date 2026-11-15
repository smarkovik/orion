# AWS definitions

No Step Functions and no database: a schedule invokes scrape, and the manifest scrape writes to S3 invokes build. Build also fetches story thumbnails, so it needs internet egress (no VPC, or a VPC with a NAT).

| File | What | Apply |
| --- | --- | --- |
| `scheduler.md` | EventBridge Scheduler: one hourly schedule per edition (08:00-22:00 `Europe/Skopje`) invoking scrape; build's reserved concurrency of 1 | see the file |
| `s3-raw-notification.json` | S3 event notification: invoke build on `s3:ObjectCreated:*` under `runs/` ending in `.json`. Replace `${BuildFunctionArn}` first (for example with `envsubst`). | `aws s3api put-bucket-notification-configuration --bucket <raw-bucket> --notification-configuration file://s3-raw-notification.json` |
| `s3-raw-lifecycle.json` | Expires `raw/`, `runs/` and `builds/` after 730 days and `archive/` after 1095; aborts incomplete multipart uploads after 1 day | `aws s3api put-bucket-lifecycle-configuration --bucket <raw-bucket> --lifecycle-configuration file://s3-raw-lifecycle.json` |
| `s3-raw-intelligent-tiering.json` | Intelligent-Tiering archive tiers for `raw/`: Archive Access after 90 days, Deep Archive Access after 180 | `aws s3api put-bucket-intelligent-tiering-configuration --bucket <raw-bucket> --id raw-archive --intelligent-tiering-configuration file://s3-raw-intelligent-tiering.json` |
| `s3-site-lifecycle.json` | Site bucket: expires `{e}/story/`, day and month pages (`{e}/20*`) and `thumbs/` after 1095 days and `admin/data/` after 400; aborts incomplete multipart uploads after 1 day. Add a rule per new edition. | `aws s3api put-bucket-lifecycle-configuration --bucket <site-bucket> --lifecycle-configuration file://s3-site-lifecycle.json` |
| `cloudfront-admin-auth.js` | CloudFront Function (viewer-request) that asks for HTTP Basic auth on `/admin/*` (the back-office page and its `admin/data/` JSON); other paths pass through. The file holds a placeholder: put the real `base64(user:password)` in at deploy time from a secret, never in git. | `aws cloudfront create-function --name admin-auth --function-config Comment=admin,Runtime=cloudfront-js-2.0 --function-code fileb://cloudfront-admin-auth.js`, publish it, then associate it as the viewer-request function of the distribution's default cache behaviour |

