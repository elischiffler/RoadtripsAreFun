import { lazy, Suspense } from 'react';

const StudioResearch = lazy(() => import('./StudioResearch'));

export default function ResearchRoute() {
  return (
    <Suspense fallback={<p role="status">Loading research…</p>}>
      <StudioResearch />
    </Suspense>
  );
}
