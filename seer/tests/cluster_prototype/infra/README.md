# AWS definitions

| File | What | Apply |
| --- | --- | --- |
| `state_machine.asl.json` | Step Functions (Standard) definition of the hourly pipeline. Replace `${ScrapeFunctionArn}`, `${IngestFunctionArn}`, `${StoriesFunctionArn}`, `${ExportFunctionArn}` first (for example with `envsubst`). Start it with `{"editions": ["mk", "fr"]}`. | `aws stepfunctions create-state-machine --name seer-hourly --type STANDARD --role-arn <role> --definition file://state_machine.asl.json` |
| `s3-raw-lifecycle.json` | Expires `raw/` and `runs/` after 730 days; aborts incomplete multipart uploads after 1 day | `aws s3api put-bucket-lifecycle-configuration --bucket <raw-bucket> --lifecycle-configuration file://s3-raw-lifecycle.json` |
| `s3-raw-intelligent-tiering.json` | Intelligent-Tiering archive tiers for `raw/`: Archive Access after 90 days, Deep Archive Access after 180 | `aws s3api put-bucket-intelligent-tiering-configuration --bucket <raw-bucket> --id raw-archive --intelligent-tiering-configuration file://s3-raw-intelligent-tiering.json` |
