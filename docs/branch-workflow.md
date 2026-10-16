# Development and production branches

`develop` is the shared integration branch. Create feature/task branches from
current develop and open PRs targeting develop. Preserve commits and other
writers' work; do not force-push shared integration or feature branches.

`main` remains the production release branch. Release with a reviewed develop to
main PR after the sole production/catalog owner clears the release window and
required checks and independent reviews pass. A green CI check is not review
approval or a dataset/source-access review. Coordinate source-calendar corrections
with that owner; do not race an urgent correction or active release. Do not merge
unrelated feature work into a release solely to empty the PR queue.

## Continuous integration and deployment

The four application workflows run for every PR, and for pushes to main and
develop. They retain the same jobs, dependency locks, coverage thresholds and
read-only permissions. Existing workflow files on the target branch govern when
push CI starts; this workflow transition is delivered through a develop PR.
Feature PR CI already supports develop because its `pull_request` trigger has no
base-branch filter.

Develop must not deploy production. `deploy-ec2.yml` listens only to completed
main workflows or a manual main dispatch. Its job additionally requires a
same-repository main-push event. `scripts/check_deployment.py` independently
rejects develop workflow completions and manual develop requests, requires the
exact current main SHA, and counts only successful main-push checks. The host
performs its own current-main/CI checks. Neither the deployment workflow nor its
scripts, credentials, environment settings or permissions change in this transition.
The frontend's existing preview integration is separate from the production API.

## Initial branch mapping and releases

Develop starts at verified main
`e9129a7551ef8c07405a9bf7552f6303765365af`. PR #41 (evaluation/shared limits)
and PR #39 (repository guidance) move from main to develop only after their
base-to-head diffs are checked to be identical. PR #44 is closed: its exact
head `5f17b994f719b9e9d342bd0d17f1bde9e339ffa6` is already an ancestor of
main through #46, including its portable filenames. Existing source and catalog
release branches remain owned by their current release worker.

The separately assigned AI visit-duration/UI feature also targets develop.
After features merge, delete only their inactive merged branches using GitHub's
recoverable branch cleanup. Keep PR history, catalog source artifacts, saved user
trips and production data. Do not delete active expansion/release branches.

If an authorized urgent correction lands on main first, merge the reviewed main
change back into develop, then retest affected PRs. A release PR must include all
main corrections and show its actual diff before review. This document does not
claim that any pending feature, source review, correction or release is cleared.
