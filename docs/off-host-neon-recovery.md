# Proposed off-host Neon recovery for the AWS API

Status: **PROPOSED**, not provisioned. Roadtrips still writes to Neon project
`misty-mouse-24917066`, production branch `br-noisy-forest-aqidrq92`, database
`neondb`. The host-local `pg_dump` and isolated PostgreSQL 18 restore passed on
2026-09-28 with matching counts for `chats`, `route_segments`, `steps`, and
`chat_memory`. That 3,893,073-byte dump is on the EC2 root disk. The Neon
snapshot list is empty. Neither protects against losing that disk or host.

## Single proposed destination and budget

- Private S3 Standard bucket in the host's `us-west-1` region:
  `s3://elischiffler-roadtrips-neon-backups-us-west-1/production/`. Confirm
  global bucket-name availability and the AWS account before creation.
- One custom-format `pg_dump` plus SHA-256 manifest each day at 03:00 UTC.
  Timestamped immutable object names; retain 30 daily points with a 30-day S3
  lifecycle expiry. Abort incomplete multipart uploads after one day. Keep the
  current same-host latest copy for quick restore, but S3 is the disaster copy.
- Block all public access; bucket-owner enforced; default SSE-S3 encryption;
  HTTPS-only bucket policy. Attach an EC2 instance role scoped to `PutObject`,
  `GetObject`, and `ListBucket` under this prefix. Do not grant `DeleteObject`
  to the backup job. Do not store access keys in the host env or repository.
- At the observed dump size, 30 copies are about 117 MB plus tiny manifests.
  Even at a planning allowance of $0.05 per GB-month, storage is under $0.01
  per month; daily PUT and weekly GET requests should keep the whole S3 bill
  below $0.05/month at current size. This is an estimate, not a provider quote;
  growth, requests, transfer, taxes, and any optional KMS service change it.
  Confirm the exact `us-west-1` price in the AWS calculator before creation and
  ask again if the projected recurring cost exceeds $1/month. S3 bills usage,
  not a hard cap.

## Backup and proof sequence after approval

1. Create/review the bucket, lifecycle, policy, and instance role in the
   approved AWS account. Keep Roadtrips Neon writes disabled while the first
   backup and restore are verified. Record resource IDs and policy without
   printing connection strings.
2. Run `pg_dump --format=custom --no-owner --no-acl --file <private-path>` from
   the reviewed Neon direct endpoint with `sslmode=verify-full`; use the
   protected host credential. Set file mode 0600, produce SHA-256, run
   `pg_restore --list`, and upload dump plus manifest to timestamped S3 keys.
   Verify both remote object sizes and hashes after downloading to a private
   temporary directory. Never put the credential or data in logs.
3. Restore the downloaded object into a fresh, isolated PostgreSQL 18 database.
   Refuse a populated target. Compare table schemas, sequences, constraints,
   and exact counts for all four application tables; run a two-user read journey
   against the restore. A same-host isolated restore verifies the artifact; a
   replacement-host rehearsal is additionally needed to prove recovery from
   whole-host loss. Keep source and restore isolated.
4. Schedule daily backup with failure alerting and weekly downloaded restore.
   Record last successful object key, SHA-256, source branch/commit, row counts,
   restore target, and duration. Alarm if no verified off-host copy is newer
   than 24 hours. Periodically restore to a replacement host.

## Release and rollback

Only after the first off-host copy and isolated restore pass, review production
schema compatibility and actual Cognito two-user ownership, route/map/chat
persistence, provider behavior, and recovery. Then enable
`ROADTRIPS_NEON_WRITES_ENABLED=true` in a controlled window and run an
authorized write journey. If it fails, turn writes off, revert the API image
and frontend target, and reconcile any committed writes. An image rollback does
not undo database writes or migrations. Restoring Neon from the backup replaces
newer data and requires a separate explicit data-loss decision.

The smallest owner approval for this proposal is: private S3 bucket and scoped
EC2 role in the existing AWS account, 30-day daily retention, and a recurring
budget review threshold of $1/month. No resource has been created by this PR.

Pricing and security references: [AWS S3 pricing](https://aws.amazon.com/s3/pricing/),
[S3 Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html),
[S3 security practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).
