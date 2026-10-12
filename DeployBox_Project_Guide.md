# DeployBox — project guide

Build a small deployment tool that takes a Docker image, runs it on a Linux server, checks its health, and restores the previous version when a release fails. Use a tiny demo web app to prove that the tool works. By the end, a push to your GitHub repository will test and build the app, publish an image, and deploy it to AWS.

This is a portfolio project you build yourself. Work through the milestones in order and keep each one working before adding the next.

## What the finished project does

1. A developer pushes a change to GitHub.
2. GitHub Actions runs tests and builds a Docker image tagged with the commit SHA.
3. The workflow pushes that image to Amazon Elastic Container Registry (ECR).
4. The workflow asks AWS Systems Manager to run DeployBox on an EC2 instance.
5. DeployBox starts the new image as a candidate and checks its `/health` endpoint.
6. If healthy, DeployBox makes the new image active. If it fails, the previous working version stays available or is restored.
7. You can inspect the current version, recent deployments, and container logs, and request a rollback.

The flow is `GitHub → Actions → ECR → Systems Manager → EC2 → DeployBox → Docker app`.

### What you will demonstrate

- Linux server administration, Docker images and containers, and HTTP health checks.
- AWS EC2, ECR, IAM roles, security groups, and Systems Manager.
- A test/build/deploy pipeline using GitHub Actions.
- Infrastructure as code with Terraform.
- Failure handling: a deliberately broken release is rejected or rolled back.

## Recommended stack and scope

| Part | Choice | Why |
| --- | --- | --- |
| Demo application | Python + FastAPI | Small enough that you can focus on deployment. |
| Deployment tool | Python CLI calling Docker | Lets you implement and test the release logic yourself. |
| Container registry | Amazon ECR | Stores images used by the EC2 server. |
| Server | One EC2 Linux instance | Keeps the first version manageable. |
| Automation | GitHub Actions + AWS Systems Manager Run Command | Builds on pushes and deploys without opening SSH to the workflow runner. |
| Infrastructure | Terraform | Recreates the AWS resources from version-controlled files. |

**MVP boundary:** one application on one server, one active container, a short interruption when switching versions, and command-line administration. A web dashboard, multiple servers, and zero-downtime switching are later improvements.

## Suggested repository layout

```text
deploybox/
├── demo-app/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
├── deploybox/
│   ├── cli.py
│   ├── docker_runtime.py
│   └── state.py
├── tests/
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── .github/workflows/
│   └── deploy.yml
├── docs/
│   ├── architecture.md
│   └── recovery.md
└── README.md
```

You can change the internal Python file names as you learn. Keep the demo app, deployment tool, infrastructure, and workflow clearly separated.

## Milestone 0 — prepare your workspace

- [ ] Create a new Git repository named `deploybox` and add a README describing the goal.
- [ ] Confirm that Python, Git, Docker, and `curl` work locally. Install Terraform and the AWS CLI when you reach the AWS milestone.
- [ ] Check your AWS trial's remaining credits, expiration, and EC2 Free Tier eligibility in Billing. Set a budget alert before launching resources.
- [ ] Choose one AWS Region and use it consistently for EC2, ECR, and the workflow.

**Done when:** the repository exists and you can build and run a basic Docker image locally. No AWS resources are needed yet.

## Milestone 1 — write the demo app

Build a deliberately small service. The deployment behavior is the interesting part of this project.

- [ ] `GET /` returns the service name and deployed version. Read the version from an `APP_VERSION` environment variable.
- [ ] `GET /health` returns HTTP 200 when the app is ready.
- [ ] Add a way to simulate a bad release: when `FAIL_HEALTH=1`, `/health` returns HTTP 503.
- [ ] Write a Dockerfile that starts the app on port 8000.
- [ ] Add tests for the healthy and unhealthy responses.
- [ ] Build the image and run it locally with port 8080 published.

**Done when:** `curl http://localhost:8080/` shows the version, and `curl -i http://localhost:8080/health` shows either 200 or 503 depending on the failure switch.

## Milestone 2 — build DeployBox locally

Create a CLI with these commands:

| Command | Required behavior |
| --- | --- |
| `deploybox deploy IMAGE` | Pull or use an image, test it, and switch the active release if healthy. |
| `deploybox status` | Show the active image, previous image, and health. |
| `deploybox logs` | Show recent logs from the active container. |
| `deploybox rollback` | Deploy the previous successful image after checking it. |

Use immutable version tags such as a Git commit SHA. Save the active and previous image references in a small state file. Make the state directory configurable so local development and EC2 can use different paths.

Implement `deploy` in this order:

1. Verify that Docker is available and the image reference is valid. Pull the image when it comes from a registry.
2. Start a candidate container on a port bound to `127.0.0.1`, separate from the live app.
3. Poll its `/health` endpoint for a short, fixed timeout. If it fails, remove the candidate and leave the active app running.
4. If it passes, stop the old active container and start the new version on the live port. Check health again.
5. If the live check fails, restart the previous image. Save the new active/previous state only after a successful release.

A brief interruption during the switch is acceptable for this MVP. Validate command arguments, avoid passing untrusted text through a shell, and make failed commands return nonzero exit codes.

**Done when:** version `v1` is active; a deliberately unhealthy `v2` is rejected while `v1` stays healthy; a healthy `v2` deploys; and `rollback` returns to `v1`. Test `status` and `logs` as well.

## Milestone 3 — provision AWS and deploy manually

Use Terraform to create the project's AWS resources:

- [ ] One ECR repository for the demo app.
- [ ] One Free Tier-eligible EC2 instance, chosen according to your account's current eligibility.
- [ ] A security group allowing the demo app's public port. If you use SSH during setup, limit it to your own IP address. Systems Manager can handle later remote commands.
- [ ] An EC2 IAM role that allows Systems Manager management and pulling the required ECR image. Give it only the permissions it needs.
- [ ] Any instance setup needed to install Docker, start DeployBox, and make the instance available to Systems Manager.
- [ ] Terraform outputs for the ECR repository URL and instance identifier.

Push a tagged image to ECR, then run `deploybox deploy IMAGE` on EC2 manually. Verify the app through the instance's public address. Reboot the instance and confirm you can bring the app back using the documented procedure.

**Done when:** Terraform creates the resources, the instance can pull your ECR image without a stored AWS access key, and the app runs on EC2.

## Milestone 4 — automate releases

Create a GitHub Actions workflow that runs only after a push to your chosen deployment branch:

1. Install dependencies and run the demo app and DeployBox tests.
2. Build a Docker image tagged with the full commit SHA.
3. Authenticate to AWS using GitHub OpenID Connect (OIDC), with an IAM trust policy restricted to your repository and branch.
4. Push the image to ECR.
5. Send a Systems Manager Run Command to the specific EC2 instance to run `deploybox deploy IMAGE`.
6. Wait for the remote command's result. Mark the workflow failed if deployment or its health check fails.

Keep AWS credentials and private keys out of the repository. Use separate IAM permissions for the GitHub workflow and EC2 instance. Do not put secrets in Run Command parameters or workflow logs.

**Done when:** a good commit automatically reaches EC2, while a bad release makes the workflow fail and leaves the previous version serving requests.

## Milestone 5 — document and prove the result

- [ ] Write a README with setup, local run, deployment, rollback, and cleanup instructions.
- [ ] Draw a small architecture diagram showing the release path and AWS resources.
- [ ] Add a screenshot or short recording of a successful pipeline and a failed deployment being rejected.
- [ ] Record one incident: what you broke, how you detected it, and how you recovered.
- [ ] Document what remains on AWS when you stop working, and use `terraform destroy` when you no longer need the practice environment. Preserve any evidence you want for your portfolio first.

**Final demonstration:** push a healthy `v1`, show it running, push an unhealthy `v2`, show the failed workflow and still-working `v1`, then deploy a fixed `v3` and perform a manual rollback.

Once this works, your résumé can accurately describe a container deployment tool with automated releases, health checks, rollback, and AWS infrastructure as code. Do not claim zero downtime or production scale for this first version.

## Optional improvements after the MVP

- Add blue/green containers behind a reverse proxy for switching without a brief interruption.
- Add a read-only deployment history page.
- Add CloudWatch log collection and an alarm for repeated deployment failures.
- Add integration tests that start a real container and intentionally fail its health check.
- Support a second demo app to show that DeployBox is reusable.

## Reference documentation

- [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [GitHub Actions: build and test Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [GitHub Actions: configure OIDC for AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [AWS: get started with EC2 and check Free Tier conditions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html)
- [AWS: push a Docker image to ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html)
- [AWS Systems Manager Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html)
- [Terraform AWS getting-started tutorials](https://developer.hashicorp.com/terraform/tutorials/aws-get-started)

Start with Milestone 1. Build and test the tiny app before writing the deployment tool or spending AWS credits.
