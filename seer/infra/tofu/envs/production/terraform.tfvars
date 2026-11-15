# Non-secret values. Fill in the account id after running bootstrap/ in the production account.
aws_account_id = "000000000000"
name_prefix    = "seer-production"
editions       = ["mk", "fr"]

schedule_expression = "cron(0 8-22 * * ? *)"
schedule_enabled    = true

domain          = "" # for example "example.com"; needs route53_zone_id
route53_zone_id = ""
alarm_email     = ""
