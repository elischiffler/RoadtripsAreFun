# Final arrival timing

`SchedulingPolicy.arrival_cutoff(final=True)` owns final destination timing for
both CP-SAT estimates and final Mapbox duration validation. Without late driving,
the default destination limit is **21:00 arrival-local time**, while hotels and
two-hour attraction visits retain **20:00**. This accepts the reported Boulder
arrival at **2026-10-19 20:30:38.484 -06:00** without enabling late driving. A
destination reached after the ordinary hotel cutoff carries a late-arrival
warning. Estimates can still differ from actual rerouted legs; actual validation
remains authoritative.

Optional `latest_destination_arrival` records an explicit final-arrival or
stop-driving deadline. It can narrow the default window; values later than 21:00
require explicit `late_driving` to take effect. Earlier hotel limits also
conservatively narrow the destination window. With explicit late driving, the
existing late cutoff (at most midnight) applies, bounded by any explicit
destination deadline. Preference extraction supports this field. Default `null` preserves existing saved late-driving policies.

Elapsed duration, IANA timezone/DST rules, booking nights and morning restart
are unchanged. A final route outside the bound explains the local deadline and
available replanning choices; the API retains that explanation. No migration, dependency, production
deployment or provider call is introduced.

