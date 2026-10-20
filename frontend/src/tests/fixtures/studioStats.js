const result = {
  mode: 'live',
  snapshot: { id: 'ui-sample', label: 'Sample trip', source: 'Synthetic UI check' },
  stages: [],
  input_snapshot: { num_stops: 4 },
  explanation: {
    solver: {
      status: 'OPTIMAL',
      objective_direction: 'minimize',
      selected_count: 3,
      eligible_count: 4,
      average_match: 0.8,
      best_average_match: 0.8,
      quality_loss: 0,
      wall_time_seconds: 0.004,
    },
    candidates: [
      { name: 'Museum', provider_id: 'museum', selected: true, utility: 0.9 },
      { name: 'Park', provider_id: 'park', selected: true, utility: 0.7 },
      { name: 'Gallery', provider_id: 'gallery', selected: true, utility: 0.8 },
      { name: 'Market', provider_id: 'market', selected: false, utility: 0.5 },
    ],
  },
  route: {
    distance: 177027.84,
    duration: 10800,
    cost: 245,
    stops: [
      { provider_id: 'museum', type: 'stop' },
      { provider_id: 'park', type: 'stop' },
    ],
  },
  run_record: {
    metrics: {
      latency_ms: {
        total: 150000,
        gathering: 100000,
        solving: 4,
        generation: 120000,
        validation: 20000,
      },
      external_calls: { catalog: 12, mapbox: 6, language_model: 3 },
      trip_evaluation: {
        stop_fulfillment: { delivered: 2, requested: 4, solver_selected: 3 },
        utility: {
          selected: { mean: 0.8, min: 0.7, max: 0.9, median: 0.8 },
          delivered: { mean: 0.8, min: 0.7, max: 0.9, median: 0.8 },
        },
        driving: {
          direct_duration_seconds: 7200,
          final_duration_seconds: 10800,
          extra_duration_seconds: 3600,
          extra_duration_percent: 50,
          direct_distance_meters: 160934.4,
          final_distance_meters: 177027.84,
          extra_distance_meters: 16093.44,
          extra_distance_percent: 10,
        },
        schedule: {
          final_arrival: '2026-10-22T13:55:57-06:00',
          final_timezone: 'America/Boise',
          itinerary_days: 3,
          overnights: 2,
          visit_seconds: 10800,
        },
        hotel_costs: {
          quoted_total_usd: 245,
          room_night_count: 2,
          over_target_room_nights: 0,
          budget_utilization: 0.6806,
        },
        schedule_compliance: { violation_count: 0, assessed_stops: 5 },
      },
    },
  },
};
export default result;
