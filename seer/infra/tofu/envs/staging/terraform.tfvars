# Non-secret values. Fill in the account id after running bootstrap/ in the staging account.
aws_account_id = "000000000000"
name_prefix    = "seer-staging"
editions       = ["mk", "fr"]

# Same as production. To halve the load on publishers, staging can be slowed to every 3 hours
# with "cron(0 8-22/3 * * ? *)".
schedule_expression = "cron(0 8-22 * * ? *)"
schedule_enabled    = true

domain          = "" # for example "staging.example.com"; needs route53_zone_id
route53_zone_id = ""
alarm_email     = ""
