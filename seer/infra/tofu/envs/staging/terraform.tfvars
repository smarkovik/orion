# Non-secret values. Fill in the account id after running bootstrap/ in the staging account.
aws_account_id = "160224865114"
name_prefix    = "seer-staging"
editions       = ["mk", "fr"]

# Same as production. To halve the load on publishers, staging can be slowed to every 3 hours
# with "cron(0 8-22/3 * * ? *)".
schedule_expression = "cron(0 8-22 * * ? *)"
schedule_enabled    = false # manual fetches only; see seer/README.md

domain          = "" # for example "staging.example.com"; needs route53_zone_id
route53_zone_id = ""
alarm_email     = ""

# Sandbox: keep search engines out.
block_indexing = true

# The account's Lambda concurrency quota is 10, which AWS needs fully unreserved. Set back to 1 after a quota increase.
build_reserved_concurrency = -1

# New-account Lambda memory cap. Remove after the limit is raised.
build_memory_mb = 3008

# Sync button and Lambda cost in the admin. The token itself is in seer/README.md (temporary, see there to rotate it).
control_token_sha256     = "7c7606393d8eeaf4bd88599d51f9ab095877770817565ebd2b5142386633c6bc"
control_cooldown_seconds = 900

# arm64 is 20% cheaper per GB-second; the staging workflow builds the images on an arm runner.
lambda_architecture = "arm64"
