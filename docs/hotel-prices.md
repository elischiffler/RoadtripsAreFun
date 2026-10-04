# Dated hotel prices

CP-SAT uses Google Hotels HTML as its sole hotel price source, supplying the
displayed **one-night total with taxes and fees, for two adults, in USD**.
The existing `OPENCAGE_KEY` verifies the overnight city and each hotel address;
no additional scraping subscription or browser process is required.

The lookup reverse-geocodes the stop to a city, requests an explicit stay, and
checks the returned check-in, check-out, occupancy and currency controls. It
reads at most 20 listing cards and visits at most six unique hotel detail pages.
Each accepted hotel's detail heading and stay must match the listing; its
geocoded address must be within 30 miles of the stop. Prices never come from
the language model. The model rates only names discovered by the provider.

The planner budgets the displayed total, not the pretax nightly rate. The
existing route and itinerary `url` fields carry the Google Hotels entity link
with the same stay and currency parameters. This opens a comparison page from
which the traveler can choose a booking provider. Displayed prices are a
snapshot, may be rounded, and can change before booking; availability and the
final charge are confirmed by the booking provider. Room type and cancellation
terms are not normalized. Other occupancy, currencies and multiple-night stays
require an explicit contract extension rather than relabeling these prices.

This is an undocumented HTML integration. Dates are encoded in Google's `ts`
protobuf parameter (see the original [SerpApi reverse-engineering
research](https://serpapi.com/blog/decoding-protobuf-messages-without-schema/));
returned controls remain authoritative if Google changes the parameter.
Layout changes, consent/challenge pages, redirects, rate limits, missing totals,
wrong dates or unverified locations fail closed. There is no challenge bypass,
JavaScript execution or automatic switch to undated estimates. Each HTTP request
has a five-second connect and twenty-second read timeout, each geocoding request
has a five-second timeout, the complete lookup has a sixty-second deadline, and
HTML responses are limited to five MiB. One lookup uses at most seven Google
requests and seven OpenCage requests; repeated overnight stops consume the
existing geocoding quota.

A required candidate-provider failure is marked nonretryable within the current
agent turn. The agent returns a clear chat error and keeps validated trip
details instead of asking the model to retry the same failing planning tool up
to five times. A subsequent user request can try again. The deadline applies to
hotel lookup, not to the entire model/route turn.

A rural overnight point may reverse-geocode only to a county. Google can then
return hotels elsewhere in that county, beyond the 30-mile limit. If every
checked detail listing confirms its dates, identity, address and geocoded
location but is outside the radius, the lookup returns an empty candidate list
and emits `hotels.no_nearby`. The scheduler can then try up to six overnight
points, moving backward in half-hour driving increments. It still fails if no
verified hotel can be found; it never expands the radius or accepts undated
prices. Invalid listings, geocoding failures and upstream errors remain provider
failures and stop the current turn. Each spatial retry has the existing lookup
request limits and deadline, so sparse areas can take longer to plan.

The older `find_hotel` scraper is outside the CP-SAT path and retains its Google
lookup behavior. Neither path switches to another hotel provider on failure.

Offline regression tests are in `backend/tests/routing/google_hotels_tests.py`,
with provider integration and agent failure tests in the existing candidate,
dispatcher and loop suites. Live acceptance on October 3, 2026 returned six
verified Denver hotels for November 20–21, 2026, including DoubleTree by Hilton
Hotel Denver at a displayed USD 90 total. This verifies fetching, date/guest/
currency checks, geocoding and dated links; it does not verify a completed
booking, every city, or a full live model-driven trip.
