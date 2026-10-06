#!/usr/bin/env python3
"""Request an authenticated HTTPS deployment and require the exact healthy SHA."""

import json
import os
import re
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Deployment endpoint redirects are forbidden")


def main():
    app = os.environ["DEPLOY_APP"]
    revision = os.environ["DEPLOY_SHA"]
    base = os.environ["EC2_DEPLOY_URL"]
    token = os.environ["EC2_DEPLOY_TOKEN"]
    if not re.fullmatch(r"https://[a-zA-Z0-9.-]+", base):
        raise ValueError("Configure the exact HTTPS deployment origin")
    if (
        app not in {"roadtrips", "mentro", "umami"}
        or not re.fullmatch(r"[0-9a-f]{40}", revision)
        or not token
    ):
        raise ValueError("Missing or invalid deployment configuration")
    request = urllib.request.Request(
        f"{base}/deploy/{app}/{revision}",
        data=json.dumps({"github_token": os.environ["GH_TOKEN"]}).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.build_opener(NoRedirect).open(
        request, timeout=3300
    ) as response:
        result = json.load(response)
    if result != {"status": "healthy", "app": app, "revision": revision}:
        raise RuntimeError("Host did not verify the requested release")
    print(f"PASS: {app} is healthy at {revision}")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write(
            f"Deployed `{app}` at `{revision}`; container health and readiness passed.\n"
        )


if __name__ == "__main__":
    main()
