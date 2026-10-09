# Deploying Snake Arena to AWS

This deploys the app to AWS using CloudFormation: an ECS Fargate service
running the same Docker image the Dockerfile already builds, a managed
RDS Postgres database, and an Application Load Balancer in front of it.

**This is not something Claude runs for you.** Neither the cloud sandbox
nor the bridge to your computer has AWS credentials or network access to
AWS's API — the same restriction that's kept Claude from running `docker
build`/`docker compose up` directly all session. `deploy.sh` and
`teardown.sh` are meant to be run by you, from your own terminal, with
your own AWS credentials.

## Architecture

```
                         Internet
                            |
                    [Application Load Balancer]  (public subnets, port 80)
                            |
                    [ECS Fargate task]  (backend + built frontend, port 8000)
                            |    + ADOT collector sidecar --> X-Ray (traces),
                            |                                 CloudWatch (metrics)
                    [RDS Postgres]  (not publicly reachable -- only the
                                      ECS task's security group can reach it)
```

- **`01-ecr.yaml`** — an ECR repository to hold the built image.
- **`02-app.yaml`** — everything else: a VPC with two public subnets (no
  NAT gateway, to avoid its ~$30+/month fixed cost -- security groups do
  the actual access control, not subnet placement), RDS Postgres, an ECS
  cluster/task/service on Fargate, and the load balancer.
- Deployed in two stacks because the ECS task definition needs to
  reference an image that has to already exist in ECR -- `build.sh`
  creates the ECR stack and pushes the image, then `deploy.sh` deploys
  the app stack pointing at it.

The RDS master password is generated and owned by AWS Secrets Manager
(via RDS's `ManageMasterUserPassword` feature) -- it never appears in the
CloudFormation templates, parameters, or console in plaintext. The ECS
task pulls it directly from Secrets Manager at container startup. See
`backend/app/database.py` for how the app builds its connection string
from the split `DB_HOST`/`DB_USER`/`DB_PASSWORD`/etc. environment
variables the task definition sets, instead of a single `DATABASE_URL`
(which isn't knowable until the RDS instance exists) -- this is on top
of, not instead of, the existing `DATABASE_URL` support used locally and
by `docker-compose.yml`.

### Observability: a shared stack plus a collector per app

**`01-observability.yaml`** (stack `snake-arena-observability`) is shared
by dev and prod, and deployed separately from them, once, before either
(`./deploy-observability.sh`; `deploy.sh` checks it exists):

| Resource | What it's for |
|---|---|
| Log group `/snake-arena/metrics` (7 days) | Both collectors' metric records, one stream per environment (`snake-arena`, `snake-arena-prod`). CloudWatch extracts the `SnakeArena` metrics from them and keeps those 15 months. |
| SNS topic `snake-arena-alarms` | Every dev and prod alarm notifies here. Emails: `ALARM_EMAIL=you@example.com ./deploy-observability.sh`, then click AWS's confirmation link; `ALARM_EMAIL= ./deploy-observability.sh` turns them off. |
| Dashboard `snake-arena` | Game metrics with **Environment** and **Version** dropdowns, plus both environments' alarms. The URL is printed by `deploy-observability.sh`. |
| X-Ray groups `snake-arena`, `snake-arena-prod` | Each environment's traces, one click away (X-Ray → Traces → group). |

The app stacks *import* these (they never create their own), so the
dependency runs only app → observability: dev can still be torn down
and redeployed freely. The observability stack can only be deleted after
both app stacks are gone.

Inside each app's ECS task, an AWS Distro for OpenTelemetry (ADOT)
collector sidecar receives the app's traces and game metrics on
`localhost:4318` and forwards them — traces to X-Ray, metrics to the
shared log group — using the task role `<project>-ecs-task-role`, which
can only write traces and write to that log group.

- **Metrics:** CloudWatch → Metrics → `SnakeArena` namespace, one series
  per environment (`deployment.environment.name`) and deployed version
  (`service.version`), plus `reason` on `scores.rejected`. Each deploy
  starts new series and the old version's stop, so the billed count stays
  about flat; totals across versions are summed at query time (both
  dashboards do this). They arrive about once a minute. For
  `scores.value`, the `p50` statistic is the median score. Only the five
  declared metrics, with only the declared dimensions, are published —
  see `awsemf` in `02-app.yaml` before adding labels, since each label
  combination is billed.
- **Alarms** (in each app stack, since they watch that app's load
  balancer and ECS service): `<project>-5xx-errors` (5+ server errors from
  the app or load balancer in 5 minutes) and `<project>-memory-high` (task
  memory above 80% for 15 minutes).
- **Traces:** X-Ray → Traces in `us-east-2`, or pick an environment's
  group. Filter one release with `annotation.service_version = "<image
  tag>"`. (Environment and version are searchable because the app copies
  them onto every span — X-Ray only indexes span attributes, and this
  ADOT build has no processor that could do it in the collector.)
- **Safety:** the collector listens on `127.0.0.1` only (nothing outside
  the task can send it spans), is non-essential (if it fails the game
  keeps serving, and ECS restarts it), and is capped at 128 MB of the
  task's 512 MB. Measured locally: ~30 MB under load.
- **Logs:** the collector's own logs are in the app's log group, under
  the `otel/` stream prefix.
- **Turning it off:** remove the `otel-collector` container and the
  app's `OTEL_EXPORTER_OTLP_ENDPOINT` from `02-app.yaml`; the app then
  creates spans but exports none.

## Prerequisites

- An AWS account, with the [AWS CLI](https://aws.amazon.com/cli/)
  installed and configured (`aws configure`) -- you'll need credentials
  with permission to create VPCs, RDS instances, ECS/Fargate resources,
  an ALB, IAM roles, and ECR repositories.
- Docker running locally (same as for `docker compose up`).

## Build and deploy

Two separate stages:

```bash
cd infra/aws
./deploy-observability.sh   # Once: the shared observability stack (see above)
./build.sh                  # Build: build the image, push it to ECR
./deploy.sh                 # Deploy: serve an image from ECR (the newest, by default)
```

- **Build (`build.sh`)** makes sure the ECR repository stack exists,
  builds the image from the repo's `Dockerfile` (for `linux/amd64`, what
  Fargate runs), and pushes it to ECR tagged
  **`YYYYMMDD-HHMMSS-shortsha`** -- UTC build time plus the commit it was
  built from, e.g. `20260818-163457-83242da`. It refuses to build with
  uncommitted changes to tracked files, since the tag would name a commit
  the image doesn't match (`ALLOW_DIRTY=1 ./build.sh` overrides that for
  a throwaway experiment). Needs Docker.
- **Deploy (`deploy.sh`)** builds nothing and doesn't need Docker. It
  checks the image tag exists in ECR, then deploys the app stack (VPC,
  RDS, ECS, ALB) pointing at it; ECS pulls the image from ECR. The first
  deploy takes the longest -- RDS alone typically takes 5-10 minutes --
  later ones only roll the ECS service over to the new image.

Arguments, if you want something other than the defaults:

```bash
./build.sh  <project-name> <aws-region>                     # defaults: snake-arena, us-east-2
./deploy.sh <project-name> <aws-region> <db-deletion-protection> <image-tag>
            # defaults: snake-arena, us-east-2, false, newest image in ECR
```

(us-east-2 because that's this project's assigned Region if you're on
the "new AWS experience" account type -- see `~/.claude/CLAUDE.md`'s AWS
Agent Toolkit rules, or AWS Settings > View all projects > Overview, to
confirm yours. Pass a different Region explicitly if it doesn't match.)

When it finishes, it prints the app's URL (the load balancer's DNS
name). It can take a minute or two after the stack finishes for the
target group's health checks to pass -- if the URL doesn't load
immediately, wait a bit and retry.

To deploy again after a code change, commit it, then run `./build.sh`
and `./deploy.sh` -- the ECS service rolls over to the new image without
you needing to do anything else. To roll back, run `./deploy.sh` with an
older tag from ECR as the fourth argument.

## Cost

This creates real, billable AWS resources that keep costing money for as
long as the stack exists, whether or not anyone's playing the game.
Rough estimate based on `us-east-1` rates, running continuously for a
full month (~730 hours), at the template's default sizes. `us-east-2`
(this project's actual deploy Region, see "Deploy" above) is usually
close to `us-east-1` pricing but wasn't separately re-verified here --
check the Pricing Calculator link below for exact `us-east-2` numbers:

| Resource | Rate | ~Monthly |
|---|---|---|
| RDS `db.t4g.micro` (single-AZ) | ~$0.016/hr | ~$12 |
| RDS storage (20GB gp3) | ~$0.115/GB-month | ~$2 |
| Application Load Balancer (base) | ~$0.0225/hr | ~$16 |
| Fargate (0.25 vCPU / 0.5GB) | ~$0.045/hr combined | ~$9 |
| X-Ray traces | first 100,000/month free, then $5/million | ~$0 |
| CloudWatch dashboard (shared) | first 3 dashboards free, then $3/month | ~$0 |
| CloudWatch custom metrics (7 series per running version) | ~$0.30/metric-month, prorated hourly | ~$2 |
| CloudWatch alarms (3 metrics watched) | ~$0.10/metric-month | ~$0.30 |
| **Total** | | **~$38-40/month** |

The ADOT collector sidecar fits in the existing task size, so it adds no
Fargate cost; at this game's traffic X-Ray stays inside its free monthly
allowance. The metrics row counts one series per metric plus one per
rejection reason (`scores.rejected` has three), per environment — prod
doubles it. Metric logs and alarm emails are pennies. That excludes ALB data-processing charges and data transfer, which are
usually small for a class exercise but not exactly zero. Two things can
reduce this a lot:

- A newer AWS account may have free-tier allowances that cover some of
  this (RDS: 750 hrs/month of a `db.*.micro` instance + 20GB storage for
  12 months; ALB: 750 hrs/month + 15 LCUs for 12 months) -- check your
  account's Billing Console for what applies to you.
- **You don't need this running continuously.** A class exercise is
  realistically a few hours of actual use, which costs pennies -- the
  ~$40/month figure only happens if you leave it up for a full month.
  Tear it down between sessions (see below) and redeploy with
  `./build.sh && ./deploy.sh` when you need it again.

Prices change and vary by region -- check the [AWS Pricing
Calculator](https://calculator.aws) or your account's Cost Explorer for
current, exact numbers before relying on this estimate.

## Tear down

```bash
./teardown.sh
```

Deletes everything `deploy.sh` created: the ALB, the ECS service, the
RDS database (**this permanently deletes the leaderboard data** -- there
is no separate backup kept), the VPC, and finally the ECR repository and
every image in it. It asks for a typed confirmation first. This is the
same two-argument form as `deploy.sh` if you used a non-default project
name or region:

```bash
./teardown.sh <project-name> <aws-region>   # defaults: snake-arena, us-east-2
```

`teardown.sh` leaves the shared observability stack alone (the other
environment still uses it). To remove it too, once **both** app stacks
are gone:

```bash
aws cloudformation delete-stack --stack-name snake-arena-observability --region us-east-2
```

## Environments: dev and prod

There are two independent copies of this infrastructure in the same
AWS project and Region, told apart only by the project name passed to
`deploy.sh`:

| | Dev | Prod |
|---|---|---|
| Project name | `snake-arena` | `snake-arena-prod` |
| Stacks | `snake-arena-ecr`, `snake-arena-app` | `snake-arena-prod-ecr`, `snake-arena-prod-app` |
| RDS deletion protection | off (tear down freely) | **on** |
| CI deploy role stack | `snake-arena-github-oidc` | `snake-arena-prod-github-oidc` |
| GitHub variable | repo variable `AWS_DEPLOY_ROLE_ARN` | `production` environment variable `AWS_PROD_DEPLOY_ROLE_ARN` |

Each has its own VPC, database (and leaderboard data), ECR repository,
load balancer URL, and ECS execution role -- nothing is shared, so a dev
deploy or teardown never touches prod. Prod doubles the running cost in
the "Cost" section below while it's up.

### Promoting dev to prod

Prod is never built from source. It only ever runs an image that has
already run in dev ("build once, promote"):

1. Build and deploy dev, then test it: `./build.sh && ./deploy.sh`
2. Promote exactly what dev is running: `./promote.sh` (or the
   **"Promote dev to prod"** GitHub Actions workflow, see below)
3. Tear dev back down when you're done: `./teardown.sh`

`promote.sh` reads the image dev's stack runs, refuses to continue
unless dev's `/api/health` passes, copies that image into prod's ECR
repository under the same `YYYYMMDD-HHMMSS-shortsha` tag (no rebuild),
updates the prod stack to
run it, and polls prod's `/api/health`. Dev has to be up while you
promote -- `teardown.sh` deletes dev's ECR repository, so there's
nothing to promote while dev is down. Note that the prod stack is
updated with this checkout's `02-app.yaml`, so any template changes are
promoted along with the image.

The only time prod is built from source is its very first creation:

```bash
./build.sh snake-arena-prod && ./deploy.sh snake-arena-prod us-east-2 true
```

The `true` turns on RDS deletion protection (`promote.sh` always keeps
it on).
`./teardown.sh snake-arena-prod us-east-2` refuses to run while
protection is on -- see its message for how to deliberately turn it off.

**Same-account trade-off:** both environments live in one AWS account,
so dev and prod share billing and the spend limit, and the dev deploy
role's broad VPC/RDS/ECS/ALB permissions (see "What the deploy role can
and can't do" below) technically reach prod resources too. Deletion
protection guards the prod database against that. For full isolation,
prod could move to its own project in AWS Settings later; the
templates work unchanged there.

## CI/CD (GitHub Actions)

`.github/workflows/ci-cd.yaml` runs backend tests and frontend/e2e
(Playwright) tests in parallel on every push and pull request against
`master`, then -- if both pass -- builds and runs the Docker Compose
integration/e2e suite (`tests/integration/`) for real. None of that
needs AWS access.

Two more jobs deploy dev, as separate stages, only on a manual **"Run
workflow"** click in the Actions tab (not on every push) -- see the
workflow file's comment for why:

- **build** runs `build.sh`: builds the image and pushes it to ECR
  tagged `YYYYMMDD-HHMMSS-shortsha`, and passes that tag on.
- **deploy** runs `deploy.sh` with exactly that tag (ECS pulls it from
  ECR -- no Docker build), then polls `/api/health` to confirm it came
  up healthy.

Both jobs authenticate
with a short-lived, keyless AWS session via GitHub's OIDC identity
provider, not a stored access key.

### One-time setup (you do this, not the pipeline)

> **Blocked on this AWS project as it stands.** The managed paid-plan
> service control policy for the "new AWS experience" denies every
> `iam:*Provider*` action, so `00-github-oidc.yaml` can't create the
> GitHub OIDC provider (`AccessDenied ... explicit deny in a service
> control policy`) -- this is why `snake-arena-github-oidc` rolled back
> on 2026-09-24. Per AWS's docs that policy is lifted by **activating
> advanced features** in AWS Settings. Until then, build, deploy and
> promote by running `build.sh`/`deploy.sh`/`promote.sh` locally; the CI test jobs are unaffected.
>
> Once advanced features are on: a stack in `ROLLBACK_COMPLETE` can't be
> updated, so first delete it (`aws cloudformation delete-stack
> --stack-name snake-arena-github-oidc --region us-east-2`), then follow
> the steps below from the start. The template already includes
> everything later changes need (e.g. the X-Ray task role), so there's no
> separate "update the deploy role" step to catch up on.

1. **Deploy the OIDC role** — this has to exist before the pipeline can
   authenticate at all, so it's a separate template you deploy yourself,
   the same way as `01-ecr.yaml`/`02-app.yaml`:

   ```bash
   aws cloudformation deploy \
     --stack-name snake-arena-github-oidc \
     --template-file 00-github-oidc.yaml \
     --parameter-overrides GitHubOrg=Crooked-Cat-Tail-Software GitHubRepo=snake-arena GitHubBranch=master \
     --capabilities CAPABILITY_NAMED_IAM \
     --region us-east-2
   ```

   If your AWS account already has a GitHub OIDC provider set up (for
   example, if you used the AWS Agent Toolkit's own GitHub integration,
   or another project's pipeline), this fails with "Provider already
   exists" — pass that existing provider's ARN as
   `ExistingOIDCProviderArn=<arn>` instead of letting this stack create
   a second one (AWS allows only one per account for this URL). Find it
   with:

   ```bash
   aws iam list-open-id-connect-providers
   ```

2. **Copy the role ARN into GitHub.** After the stack finishes:

   ```bash
   aws cloudformation describe-stacks \
     --stack-name snake-arena-github-oidc \
     --region us-east-2 \
     --query "Stacks[0].Outputs[?OutputKey=='DeployRoleArn'].OutputValue" \
     --output text
   ```

   Then in the GitHub repo: **Settings → Secrets and variables → Actions
   → Variables tab → New repository variable**, name it
   `AWS_DEPLOY_ROLE_ARN`, and paste the ARN. It's a variable, not a
   secret — a role ARN isn't sensitive on its own; nothing usable comes
   from it without also presenting a valid GitHub Actions OIDC token for
   this exact repo and branch.

3. **Trigger a deploy.** Actions tab → "CI/CD" workflow → "Run workflow"
   → pick the `master` branch → Run (this deploys dev only). Watch the `deploy`
   job's logs for the app URL and the health-check result.

### One-time setup for promoting to prod

`.github/workflows/promote.yaml` ("Promote dev to prod") runs
`promote.sh` with its own deploy role, scoped to the `snake-arena-prod-*`
resources plus read-only access to dev's image and stack, in a GitHub
Environment named `production` that requires approval.

1. **Deploy the prod OIDC role.** Reuse the GitHub OIDC provider the dev
   stack already created (AWS allows only one per account):

   ```bash
   OIDC_ARN=$(aws cloudformation describe-stacks \
     --stack-name snake-arena-github-oidc --region us-east-2 \
     --query "Stacks[0].Outputs[?OutputKey=='OIDCProviderArn'].OutputValue" \
     --output text)
   aws cloudformation deploy \
     --stack-name snake-arena-prod-github-oidc \
     --template-file 00-github-oidc.yaml \
     --parameter-overrides GitHubOrg=Crooked-Cat-Tail-Software GitHubRepo=snake-arena \
       ProjectName=snake-arena-prod GitHubEnvironment=production \
       PromoteFromProjectName=snake-arena \
       ExistingOIDCProviderArn="$OIDC_ARN" \
     --capabilities CAPABILITY_NAMED_IAM \
     --region us-east-2
   ```

   With `GitHubEnvironment=production`, the role trusts only jobs that
   run in the `production` environment, not branch runs in general.
   `PromoteFromProjectName=snake-arena` adds read-only access to dev's
   ECR repository and app stack, so it can find and pull dev's image.

2. **Create the `production` environment in GitHub.** Settings →
   Environments → New environment → `production`. Then:
   - **Required reviewers:** add yourself (or whoever approves prod
     releases). Every prod deploy then pauses until one of them approves.
   - **Deployment branches and tags:** "Selected branches" → `master`, so
     only `master` can ever be deployed to prod.
   - **Environment variables:** add `AWS_PROD_DEPLOY_ROLE_ARN` with the
     `DeployRoleArn` output of `snake-arena-prod-github-oidc`.

3. **Promote.** With dev deployed and tested: Actions tab → "Promote
   dev to prod" → "Run workflow" → branch `master` → Run, then approve
   it when GitHub asks.

### What the deploy role can and can't do

`00-github-oidc.yaml`'s IAM policy is scoped to exactly what
`deploy.sh` needs: push images to this project's ECR repo, create/update
the two `snake-arena-ecr`/`snake-arena-app` CloudFormation stacks, and
manage the two IAM roles (`snake-arena-ecs-execution-role` and
`snake-arena-ecs-task-role`, the role the telemetry collector uses to
write traces and metrics) those stacks create, plus this project's
`snake-arena-*` alarms and alarm-email SNS topic — it cannot touch any other IAM role, user, or resource outside
those two stacks. The VPC/RDS/ECS/ALB permissions are necessarily
broader than a single resource ARN, since AWS doesn't support
resource-level restrictions for most of those services' *create*
actions (the resource doesn't exist yet to have an ARN) — this is the
same shape of access you already need yourself to run `deploy.sh` by
hand, not anything wider. The trust policy on top of that only accepts
a token whose `sub` claim is `repo:<org>/<repo>:ref:refs/heads/master` --
a workflow run on any other branch, or a pull request from a fork, is
refused by AWS before anything in the workflow even executes.

## Troubleshooting

- **ECS tasks keep stopping / target group shows unhealthy** — check the
  container logs: CloudWatch Logs, log group `/ecs/snake-arena` (or
  `/ecs/<project-name>` if you used a custom name). The most likely
  cause is the task failing to reach Secrets Manager or RDS -- double
  check the stack actually finished creating (`aws cloudformation
  describe-stacks --stack-name snake-arena-app`) before assuming the app
  itself is broken.
- **`AccessDeniedException` reading the secret** — the ECS execution
  role is granted `secretsmanager:GetSecretValue` on the RDS-managed
  secret specifically; if AWS changes how that default key's permissions
  work between when this was written and when you deploy, you may need
  to also grant the execution role `kms:Decrypt` on the
  `aws/secretsmanager` key.
- **`CREATE_FAILED` on the RDS instance, engine version** — `EngineVersion`
  in `02-app.yaml` is pinned to a specific Postgres minor version, which
  AWS deprecates over time. If deploy fails here, check the current
  supported list and bump the version in `02-app.yaml` -- any 16.x works,
  the app doesn't depend on a specific minor version.
- **`docker: command not found` or `aws: command not found`** — both
  scripts check for these upfront and tell you which one's missing.

## What wasn't verified

I (Claude) have no way to actually run `deploy.sh` or otherwise test
these templates against a real AWS account from this session -- no AWS
credentials, and no network access to AWS's API from either the cloud
sandbox or the bridge to your computer. What I *did* verify: all three
CloudFormation templates (including `00-github-oidc.yaml`) pass
`cfn-lint` with zero errors or warnings, both shell scripts pass
`shellcheck` cleanly and have valid bash syntax, and the
`backend/app/database.py` split-variable connection logic (used only by
the ECS task, not by local dev or `docker-compose.yml`) is tested
against real cases -- default URL, `DATABASE_URL` override, and
`DB_HOST`-based construction with special characters in the password,
including a round-trip through SQLAlchemy's own URL parser to confirm
nothing gets mangled. I also re-ran the existing backend test suite
against real Postgres after the `database.py` change -- still 9/9
passing, confirming it didn't break local/Docker Compose behavior. None
of that proves the actual AWS deployment will succeed end-to-end --
please run `./deploy.sh` yourself and treat the first run as the real
test.

The GitHub Actions workflow (`.github/workflows/ci-cd.yaml`) similarly
passes `actionlint` (which validates its YAML/expression syntax, the
`uses:` action references, and shellchecks every embedded `run:` block)
with zero findings -- but I have no way to actually execute a GitHub
Actions run from this session either, so whether the real pipeline goes
green (the Postgres service container comes up in time, the Playwright
browser install works on the runner, the OIDC token exchange succeeds,
the deploy job's health-check polling behaves as expected against a
real ALB) is untested. The OIDC thumbprint in `00-github-oidc.yaml` was
looked up fresh via web search against GitHub's and AWS's own current
documentation rather than recalled, since this is exactly the kind of
value that silently goes stale. Please push this to GitHub, do the
one-time OIDC role setup in the CI/CD section above, and treat the
first "Run workflow" click as the real test of the deploy job.
