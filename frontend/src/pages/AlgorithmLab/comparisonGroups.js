export function comparisonGroups(rows) {
  const groups = new Map();
  for (const row of rows) {
    const metrics = row.metrics;
    if (
      row.mode !== 'live' ||
      !metrics?.cohort_key ||
      !metrics?.candidate_hash ||
      !metrics?.revision ||
      !metrics?.metric_version ||
      metrics.evidence_layer?.includes('synthetic')
    )
      continue;
    const key = JSON.stringify([
      metrics.cohort_key,
      metrics.candidate_hash,
      metrics.revision,
      metrics.metric_version,
    ]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return [...groups.values()];
}
