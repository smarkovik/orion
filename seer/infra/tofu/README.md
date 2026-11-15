# Seer infrastructure (OpenTofu)

Two AWS accounts, staging and production, each with its own state. Both call the same module (`modules/seer`) with the same settings; only names and account values differ.

| Path | Holds |
| --- | --- |
| `modules/seer/` | The stack in `eu-central-1` (CloudFront certificate and log delivery in `us-east-1`): buckets, ECR, Lambdas, S3 event, schedules, CloudFront, alarms |
| `envs/staging/`, `envs/production/` | Thin roots: S3 backend, provider with `allowed_account_ids`, `terraform.tfvars` |
| `bootstrap/` | Run once per account with local state: state bucket, GitHub OIDC provider, deploy role |

The rules encoded here are the ones in `tests/cluster_prototype/infra/` (lifecycle, Intelligent-Tiering, notification, scheduler).

## One-time setup (per account)

1. Pick `name_prefix` (`seer-staging` / `seer-production`) and use the same value in the matching `envs/<env>/terraform.tfvars`.
2. With admin credentials for that account:
   ```bash
   cd seer/infra/tofu/bootstrap
   cp terraform.tfvars.example terraform.tfvars   # set environment and name_prefix
   tofu init && tofu apply
   ```
   If the account already has the GitHub OIDC provider, `tofu import aws_iam_openid_connect_provider.github arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com` first. Keep `bootstrap/terraform.tfstate` safe (it is local and git-ignored).
3. Copy the outputs into the env root:
   - `account_id` into `aws_account_id` in `envs/<env>/terraform.tfvars`;
   - `backend_bucket` into the `bucket` of `envs/<env>/backend.tf` (the bucket name is `<name_prefix>-tfstate-<account id>`).
4. In GitHub, create the environments `staging` and `production` (Settings, Environments). On each, add the variable `AWS_ROLE_ARN` = the `deploy_role_arn` output of that account. On `production`, add required reviewers.
5. Commit the filled tfvars and backend. Optional: set `domain` and `route53_zone_id` (the hosted zone must already exist), and `alarm_email` (confirm the SNS email once).

The deploy role trusts only `repo:smarkovik/orion:environment:<env>`, so a job must run in that GitHub environment to assume it.

## Deploying

- **Staging:** every push to `main` that touches `seer/**` (or the deploy workflow files or the composite action) runs `seer-deploy-staging.yml`; it can also be started manually.
- **Production:** run `seer-deploy-production.yml` manually with `ref` = `main` (default), a commit SHA or a tag. Refs not reachable from `origin/main` and not tags are refused.
- Both use `.github/actions/seer-deploy` (OpenTofu 1.11.6 in CI; `>= 1.10` required): create the ECR repositories (targeted apply, so the first run works), build and push both images tagged with the full commit SHA, then `tofu plan -out` and `tofu apply`. The summary shows the `site_url` output.
- Schedule: `cron(0 8-22 * * ? *)` in `Europe/Skopje` (staging has `schedule_enabled = false`: scrape by invoking the function, see `seer/README.md`), one schedule per edition. Staging can be slowed to every 3 hours with `schedule_expression = "cron(0 8-22/3 * * ? *)"` in its tfvars, cutting runs from 15 to 5 a day.

## Notes

- State uses native S3 locking (`use_lockfile`, OpenTofu >= 1.10): no DynamoDB table.
- Adding an edition: add its code to `editions` (one schedule and the site lifecycle rules are generated).
- `reserved_concurrent_executions = 1` on build needs an account Lambda concurrency quota above 10 (AWS keeps 10 unreserved). New accounts may need a quota increase first.
- New accounts (concurrency quota 10) also cap Lambda memory at 3008 MB, and the first build of an edition (about 900 articles) can exceed the 900 s timeout at that size. Until the quota is raised, set `build_reserved_concurrency = -1` and `build_memory_mb = 3008` in the env's tfvars (as staging does), and backfill a large first batch in chunks.
- `block_indexing = true` adds `X-Robots-Tag: noindex, nofollow` to every CloudFront response (used for staging).
- CloudFront logs go to `logs/cloudfront/` of the raw bucket (standard logging v2, W3C, no `c-ip`); the build Lambda reads and deletes them.
- Rolling back: run the production workflow with the previous tag or SHA.

## Turning deploys on

Both workflows skip until the repository variable `SEER_DEPLOY_ENABLED` is `true` (Settings → Secrets and variables → Actions → Variables). Set it after the bootstrap and GitHub environment steps above, so `main` doesn't collect failed runs before AWS is ready.
