# Guided planner / retirement integration

The isolated integration branch starts at PR55 head 96b232cb57b30f7c3aec5fed1a53e5abca3879a9 and merges PR56 head 8e9cba550f86be0d1b79045e66d76aea459aad3d. It does not merge develop/main or edit the removal owner's branch.

Eight textual conflicts were resolved explicitly:

| Path | Resolution |
| --- | --- |
| frontend/src/components/GlobalHeader.jsx | Keep removal's account/saved-trip navigation; retain Plan a trip / AI Studio and keyboard account button; no chat progress. |
| frontend/src/pages/ChatPage/ChatPage.jsx | Keep deleted. |
| frontend/src/pages/ChatPage/useTripWorkflow.js | Keep deleted. |
| frontend/src/pages/HomePage/HomePage.jsx | Keep reworked home; route setup to /plan and saved trips to /trips; remove chat copy. |
| frontend/src/services/session.js | Allow /plan and /trips; default safe login return to /plan; keep removal's storage/session behavior. |
| frontend/src/tests/HomePage.test.jsx | Assert setup, Studio and saved-trip destinations. |
| frontend/src/tests/session.test.js | Retain removal cases with the new planner default. |
| frontend/src/tests/useTripWorkflow.chat.test.jsx | Keep deleted; replace with tripPlanner and TripSetupPage behavior tests. |

Semantic conflicts were also handled: Router keeps /chat as a redirect and mounts standalone /plan; UserDataContext keeps account-scoped setup-draft cleanup without restoring composer drafts/progress. The setup container, model and browser test no longer import deleted modules or serialize answers as a conversation. The saved-trip list links to the working planner.

Parent merge order: review/integrate PR56 first, then PR55. PR55 contains PR56 as an ancestor; once PR56 is in develop its removal inventory drops out of PR55's review diff. PR51 remains separately owned; no duration/scheduler files were rewritten in this integration. Static merge preview and exact-head checks are recorded in the handoff.

See [verification and compatibility gates](ui-rework-verification.md), especially origin-local upcoming departures. No live Mentro calls, source-data edits, production deployment or user-PC preview restart were performed. The PC preview's local task01a142f0 changes require a later supervised sync; do not reset them.
