# EC2 deployment workflow

The proposed `Deploy EC2` workflow redeploys this repository’s backend services
once CI passes on the exact current main commit. A manual dispatch on main can
retry the same release. PR, fork, stale, and failed-check runs cannot deploy.

Activation is pending verified host access and installation of the shared
`/usr/local/sbin/deploy-ec2` command. The job stays disabled until the repository
variable `EC2_DEPLOY_ENABLED` is `true`; this change alone does not update EC2.

The `production` environment needs `EC2_HOST` and `EC2_USER` variables, plus
`EC2_SSH_KEY` and `EC2_KNOWN_HOSTS` secrets. Use a restricted deployment identity
and a host fingerprint obtained through an already trusted connection. Runtime
application secrets stay on the host and are never copied from developer machines.

The host serializes deployments, verifies main again after the image build,
preserves the existing Compose project and data volumes, checks service health,
and restarts the recorded previous release if the new release fails. Databases,
DNS, and unrelated services are not replaced. Frontend hosting remains unchanged.

Host installation, configuration, rollback, and activation are described in the
[shared deployment runbook](https://github.com/elischiffler/hosting-ops/blob/codex/ec2-deployment/docs/ec2-deployments.md).
