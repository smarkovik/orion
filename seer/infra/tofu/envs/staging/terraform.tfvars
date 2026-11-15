# Non-secret values. Fill in the account id after running bootstrap/ in the staging account.
aws_account_id = "160224865114"
name_prefix    = "seer-staging"
editions       = ["mk", "fr"]

# Same as production. To halve the load on publishers, staging can be slowed to every 3 hours
# with "cron(0 8-22/3 * * ? *)".
schedule_expression = "cron(0 8-22 * * ? *)"
schedule_enabled    = true

domain          = "" # for example "staging.example.com"; needs route53_zone_id
route53_zone_id = ""
alarm_email     = ""

# Sandbox: keep search engines out.
block_indexing = true

# The account's Lambda concurrency quota is 10, which AWS needs fully unreserved. Set back to 1 after a quota increase.
build_reserved_concurrency = -1

# New-account Lambda memory cap. Remove after the limit is raised.
build_memory_mb = 3008
