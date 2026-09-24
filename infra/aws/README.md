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
                            |
                    [RDS Postgres]  (not publicly reachable -- only the
                                      ECS task's security group can reach it)
```

- **`01-ecr.yaml`** — an ECR repository to hold the built image.
- **`02-app.yaml`** — everything else: a VPC with two public subnets (no
  NAT gateway, to avoid its ~$30+/month fixed cost -- security groups do
  the actual access control, not subnet placement), RDS Postgres, an ECS
  cluster/task/service on Fargate, and the load balancer.
- Deployed in two stacks because the ECS task definition needs to
  reference an image that has to already exist in ECR -- `deploy.sh`
  handles the ordering (ECR stack, then build+push, then app stack).

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

## Prerequisites

- An AWS account, with the [AWS CLI](https://aws.amazon.com/cli/)
  installed and configured (`aws configure`) -- you'll need credentials
  with permission to create VPCs, RDS instances, ECS/Fargate resources,
  an ALB, IAM roles, and ECR repositories.
- Docker running locally (same as for `docker compose up`).

## Deploy

```bash
cd infra/aws
./deploy.sh
```

This runs the whole sequence: deploys the ECR repository stack, builds
the image from the repo's `Dockerfile`, pushes it to ECR, then deploys
the app stack (VPC, RDS, ECS, ALB) with that image. The first run takes
the longest -- RDS alone typically takes 5-10 minutes to become
available -- later runs (after a code change) are faster since only the
image and the ECS service need to update.

Optional arguments if you want something other than the defaults:

```bash
./deploy.sh <project-name> <aws-region>   # defaults: snake-arena, us-east-2
```

(us-east-2 because that's this project's assigned Region if you're on
the "new AWS experience" account type -- see `~/.claude/CLAUDE.md`'s AWS
Agent Toolkit rules, or AWS Settings > View all projects > Overview, to
confirm yours. Pass a different Region explicitly if it doesn't match.)

When it finishes, it prints the app's URL (the load balancer's DNS
name). It can take a minute or two after the stack finishes for the
target group's health checks to pass -- if the URL doesn't load
immediately, wait a bit and retry.

To deploy again after a code change, just re-run `./deploy.sh` -- it
builds a fresh image, pushes it under a new tag, and updates the app
stack in place (the ECS service rolls over to the new task without you
needing to do anything else).

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
| **Total** | | **~$38-40/month** |

That excludes ALB data-processing charges and data transfer, which are
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
  `./deploy.sh` when you need it again.

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

## CI/CD (GitHub Actions)

`.github/workflows/ci-cd.yaml` runs backend tests and frontend/e2e
(Playwright) tests in parallel on every push and pull request against
`main`, then -- if both pass -- builds and runs the Docker Compose
integration/e2e suite (`tests/integration/`) for real. None of that
needs AWS access.

A fourth job, **deploy**, actually runs `deploy.sh` against AWS and then
polls `/api/health` on the result to confirm it came up healthy. It only
runs on a manual **"Run workflow"** click in the Actions tab (not on
every push) -- see the workflow file's comment for why. It authenticates
with a short-lived, keyless AWS session via GitHub's OIDC identity
provider, not a stored access key.

### One-time setup (you do this, not the pipeline)

1. **Deploy the OIDC role** — this has to exist before the pipeline can
   authenticate at all, so it's a separate template you deploy yourself,
   the same way as `01-ecr.yaml`/`02-app.yaml`:

   ```bash
   aws cloudformation deploy \
     --stack-name snake-arena-github-oidc \
     --template-file 00-github-oidc.yaml \
     --parameter-overrides GitHubOrg=Crooked-Cat-Tail-Software GitHubRepo=snake-arena GitHubBranch=main \
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
   → pick the `main` branch → Run. Watch the `deploy` job's logs for the
   app URL and the health-check result.

### What the deploy role can and can't do

`00-github-oidc.yaml`'s IAM policy is scoped to exactly what
`deploy.sh` needs: push images to this project's ECR repo, create/update
the two `snake-arena-ecr`/`snake-arena-app` CloudFormation stacks, and
manage the one IAM role (`snake-arena-ecs-execution-role`) those stacks
create — it cannot touch any other IAM role, user, or resource outside
those two stacks. The VPC/RDS/ECS/ALB permissions are necessarily
broader than a single resource ARN, since AWS doesn't support
resource-level restrictions for most of those services' *create*
actions (the resource doesn't exist yet to have an ARN) — this is the
same shape of access you already need yourself to run `deploy.sh` by
hand, not anything wider. The trust policy on top of that only accepts
a token whose `sub` claim is `repo:<org>/<repo>:ref:refs/heads/main` --
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
