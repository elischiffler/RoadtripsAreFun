# Backend-first frontend release

The mobile workflow release keeps the existing frontend live while the matching
API revision passes its checks and deploys. `frontend/vercel.json` disables
Vercel's automatic Git deployment trigger for `main` only. Other branches retain
their default preview behavior. GitHub validation and the EC2 deployment gate
continue unchanged; deployment protection and global Vercel settings are unchanged.

[Vercel's Git configuration documentation](https://vercel.com/docs/project-configuration/git-configuration#gitdeploymentenabled)
defines this option in terms of commit-triggered deployments. The
[official configuration schema](https://openapi.vercel.sh/vercel.json) likewise
describes automatic deployments. An explicit deployment API request remains the
release operation; this setting is not an access-control restriction.

## Coordinated release

1. Run required checks on the reconciled candidate and follow the repository's
   [release PR process](branch-workflow.md). Record the final `main` SHA.
2. Confirm all four required GitHub workflows succeeded on that exact SHA and
   the [EC2 deployment contract](ec2-deployment.md) reports the matching API
   revision healthy. A successful preview build alone does not authorize release.
3. Create a production frontend deployment of that same SHA using the existing
   Vercel Git connection and inherited project settings. Replace
   `FINAL_MAIN_SHA` below with the checked, healthy full commit SHA:

   ```json
   {
     "teamId": "team_OyFbNlASEaHfjOi6B6O5nCFu",
     "requestBody": {
       "name": "roadtripsarefun",
       "project": "prj_Zy5SFTRTOqY4BHWwwD9oX8oXrxYf",
       "target": "production",
       "gitSource": {
         "type": "github",
         "org": "elischiffler",
         "repo": "RoadtripsAreFun",
         "ref": "main",
         "sha": "FINAL_MAIN_SHA"
       }
     }
   }
   ```

   Use the Vercel `create_deployment` tool or equivalent
   [deployment API](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment).
   The [official OpenAPI schema](https://openapi.vercel.sh) supports both GitHub
   `ref` and `sha`. Omit `withLatestCommit` and `projectSettings` to retain the
   exact source revision and existing build/environment configuration.

4. Verify the deployment is `READY`, its recorded SHA matches, the production
   domains point to it, and public frontend routes/assets load. Confirm the
   public bundle still targets `https://api.roadtrips.elischiffler.dev/` and use
   only authorized, non-mutating health checks. Do not trigger a live AI trip
   as an incidental deployment check.
5. Keep the Git trigger hold until release verification completes. Removing
   `git.deploymentEnabled.main` through a later checked PR restores automatic
   main deployments; coordinate that change with the backend release owner.

If the backend fails its gate, leave the frontend on its previous deployment.
If the frontend build fails, retain the hold and investigate its logs rather
than changing protections or skipping checks.

## Preflight evidence, November 6, 2026

Production deployment `dpl_GCsRi9jee1wj81F5DREMFSeeFYfE` was `READY` at main
`b3fc73e4c511e4c1bd1b230f72ed28fc99b5f134`. Build events
`bld_6jesm7c8n` explicitly report that `engines.node: 24.x` overrides the project
setting `20.x`; effective build Node is already 24. Logs show `npm run build`,
Vite 5.3.5 and `dist` output. No Node project-setting change is needed.

The live public bundle targets `https://api.roadtrips.elischiffler.dev/`.
Production environment metadata contains `VITE_BACKEND_SERVER`, `VITE_CLIENT_ID`,
`VITE_USERPOOL_ID` and `VITE_MAPBOX_TOKEN`; values were not decrypted. Connector
metadata does not expose all stored build settings or the original ignored-build
command, so this source-controlled hold avoids overwriting unknown settings.
