# Scheduler

One EventBridge Scheduler schedule per edition invokes `scrape`. Scrape's manifest in `runs/` triggers `build` through the S3 notification (`s3-raw-notification.json`); there is nothing else to schedule.

| Schedule | Expression | Time zone | Target | Input |
| --- | --- | --- | --- | --- |
| `seer-scrape-mk` | `cron(0 8-22 * * ? *)` | `Europe/Skopje` | `${ScrapeFunctionArn}` | `{"edition": "mk"}` |
| `seer-scrape-fr` | `cron(0 8-22 * * ? *)` | `Europe/Skopje` | `${ScrapeFunctionArn}` | `{"edition": "fr"}` |

```bash
for ed in mk fr; do
  aws scheduler create-schedule --name "seer-scrape-$ed" \
    --schedule-expression "cron(0 8-22 * * ? *)" --schedule-expression-timezone Europe/Skopje \
    --flexible-time-window Mode=OFF \
    --target "{\"Arn\": \"$SCRAPE_ARN\", \"RoleArn\": \"$SCHEDULER_ROLE_ARN\", \"Input\": \"{\\\"edition\\\": \\\"$ed\\\"}\"}"
done
```

The role needs `lambda:InvokeFunction` on the scrape function. Set `RetryPolicy.MaximumRetryAttempts` to 2 (the default is 185 attempts over 24 hours).

## Build concurrency

Reserve concurrency 1 on `build` so two manifests never run at once (the window is also written with an S3 conditional write):

```bash
aws lambda put-function-concurrency --function-name seer-build --reserved-concurrent-executions 1
```

S3 invokes asynchronously and retries a throttled event for up to 6 hours, so manifests queue instead of being lost. Build skips a manifest that is not newer than the window.

## Wiring the S3 event

```bash
aws lambda add-permission --function-name seer-build --statement-id s3-raw --action lambda:InvokeFunction \
  --principal s3.amazonaws.com --source-arn arn:aws:s3:::<raw-bucket> --source-account <account-id>
aws s3api put-bucket-notification-configuration --bucket <raw-bucket> \
  --notification-configuration "$(BuildFunctionArn=<build-arn> envsubst < s3-raw-notification.json)"
```
