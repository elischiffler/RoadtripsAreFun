# Stage 2 UI review — November 7, 2026

The actual React screens pass 65 intercepted Chromium presentation checks:
46 onboarding/group/panel/profile screens, three ambiguous-location screens,
12 authentication screens and four Material control/dialog screens. Browser
errors and unexpected external requests were zero in every lane.

Ordinary 375×812, 390×844 and 1440×900 layouts enforce no document or nested
vertical scrolling and keep actions available. Short 320×568 and 200% text
cases intentionally retain an accessible vertical scrolling fallback. The final
layout report explicitly records `baseline: false` and enforced assertions.
Native comparison selection, focus return and saved preferences are checked;
ambiguous choices use the selected coordinates and preserve typed answers.

| Representative screenshot                            | View                                                   |
| ---------------------------------------------------- | ------------------------------------------------------ |
| [Phone trip questions](phone-route-questions.png)    | 390×844, prepared route summary and initial questions  |
| [Phone place comparison](phone-place-comparison.png) | 390×844, focused optional comparison                   |
| [Phone dark sign-in](phone-dark-sign-in.png)         | 390×844, trip entry in dark mode                       |
| [Desktop review](desktop-trip-review.png)            | 1440×900, centered review before checking trip options |

[Manifest](manifest.json) identifies the exact reviewed application revision,
194 identical frontend runtime/public/config/package files, their hashes and
the unchanged application content at the integration revision before this
evidence commit. The four JSON reports are copied without modification from
the final runs. Only these four representative screenshots are committed; the
complete screenshot sets remain in the local directories listed in the manifest.

All identity, geocoding, road and SDK replies are synthetic and intercepted.
Screenshots were visually inspected and reports checked for credentials and
authentication state before copying. No real account, provider call, database
write, migration, deployment or release occurred. These presentation checks
complement the separate signed backend/solver/PostgreSQL journey gate; they
do not establish live provider, physical-device, native iOS or manual
screen-reader acceptance. Release, merge and migration remain on user hold.

Reproduce with the [isolated UI runbook](../../../tests/ui-stage2/README.md).
