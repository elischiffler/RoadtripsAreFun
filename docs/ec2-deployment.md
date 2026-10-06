# EC2 deployment workflow

After all required CI passes on the exact current main commit, Deploy EC2 replaces
this backend API container on the existing shared EC2 host and verifies health.
A manual dispatch on main can retry a release. The host also checks CI and main,
serializes deployments, rejects stale SHAs, and rolls back a failed release.

The production environment holds EC2_DEPLOY_URL=https://ops.elischiffler.dev and
an app-specific EC2_DEPLOY_TOKEN secret. EC2_DEPLOY_ENABLED=true is a repository
variable. The environment permits main only. Automatic runs activate when the
owner merges this workflow PR; production dispatch is not available before merge.
Runtime secrets remain on the host. No SSH/AWS key is stored in Actions.

Only the API is deployed. Existing Compose project identities, external databases,
volumes, frontends, and other applications are preserved. Database migrations
remain a separate reviewed operation. See the shared deployment and recovery
[runbook](https://github.com/elischiffler/hosting-ops/blob/main/docs/ec2-deployments.md).
