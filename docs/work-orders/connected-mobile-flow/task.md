# Connected mobile trip flow

Coordinator: root. All agents share `/workspace/RoadtripsAreFun`, branch
`feat/mobile-design-system-20261106`, base design commit `c8e8b383` on current
develop `04a9ecee`. Use Apple design skill and the scoped `src/design` primitives.

Dispatch independent owners:

- preferences: setup model/migration and reviewed comparison assets.
- flow-ui: TripSetup, PreferenceProfile and page form styles/tests.
- backend: authenticated progress stream and bounded read-only nearby browsing.
- connection: TripSetupPage, RouteEstimate, progress and transport services/tests.
- experience: itinerary/map/visited state and saved presentation hydration/tests.

Dependencies: preferences publishes comparison API for flow-ui; backend publishes
stream and nearby schemas for connection and experience. Coordinator resolves cross
contracts and runs all full checks once stable. Separate workers must not edit each
other's files. No commits/pushes until coordinator review.

No live Mentro or provider requests, database access/mutations, production changes,
deployments, Mac access/approval bypass or denied Neon test retries. Mock all
provider/persistence boundaries in tests. Preserve auth ownership, backend required
field validation, legacy drafts and records, source holds and timing constraints.
