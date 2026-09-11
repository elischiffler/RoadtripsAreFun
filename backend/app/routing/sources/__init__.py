"""Candidate-sourcing infrastructure shared by all planners.

These modules own every external API call the routing layer makes:

* ``mapbox`` — driving route geometry (:func:`call_route`).
* ``attractions`` — TripAdvisor attraction search (:func:`find_stop`) plus a
  batch corridor gather (:func:`gather_candidates`) for optimizer planners.
* ``hotels`` — Google Hotels scraping + Google Places + Amadeus fallback
  (:func:`find_hotel`).

Planners receive these through :class:`~app.routing.services.RoutingServices`
and never import them directly, keeping algorithm code free of I/O concerns.
"""
