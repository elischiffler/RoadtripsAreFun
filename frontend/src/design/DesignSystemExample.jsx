import { useState } from 'react';
import {
  ActionButton,
  ChoiceGroup,
  DesignFrame,
  Field,
  QuestionGroup,
  Sheet,
  StageProgress,
  TripTimeline,
  TripViewSwitch,
} from './index';

/** Local composition for integration/visual review; no planning or network calls. */
export default function DesignSystemExample() {
  const [start, setStart] = useState('Denver, Colorado');
  const [pace, setPace] = useState('relaxed');
  const [view, setView] = useState('itinerary');
  const [saved, setSaved] = useState(false);
  return (
    <DesignFrame>
      <header className="rt-stack">
        <p className="rt-caption">RoadtripsAreFun · Design foundations</p>
        <h1 className="rt-display">A little planning. A lot to look forward to.</h1>
        <p className="rt-copy">A local example of reusable trip components.</p>
      </header>
      <StageProgress
        stages={[
          { id: 'route', label: 'Route' },
          { id: 'people', label: 'Travelers' },
          { id: 'preferences', label: 'Your style' },
          { id: 'review', label: 'Review' },
        ]}
        currentId="people"
        completedIds={['route']}
      />
      <Sheet aria-label="Trip questions">
        <QuestionGroup
          legend="Where does your trip begin?"
          description="Keep related questions together, with room to breathe."
        >
          <Field
            label="Starting city"
            value={start}
            onChange={(event) => {
              setStart(event.target.value);
              setSaved(false);
            }}
            hint="Choose and confirm an exact location in the connected trip flow."
            autoComplete="address-level2"
          />
          <Field label="Departure date" type="date" defaultValue="2027-06-14" />
        </QuestionGroup>
        <ChoiceGroup
          legend="What pace feels right?"
          value={pace}
          onChange={setPace}
          options={[
            { value: 'relaxed', label: 'Take it slow', description: 'More time at each stop' },
            {
              value: 'active',
              label: 'See a little more',
              description: 'A fuller day on the road',
            },
          ]}
        />
        <ActionButton onClick={() => setSaved(true)}>Save example choices</ActionButton>
        <p className="rt-caption" role="status">
          {saved
            ? 'Example choices saved for this preview.'
            : 'Preview only. Your trip is unchanged.'}
        </p>
      </Sheet>
      <Sheet floating aria-label="Trip preview">
        <h2 className="rt-title">Monday, June 14</h2>
        <TripViewSwitch value={view} onChange={setView} />
        {view === 'itinerary' ? (
          <TripTimeline
            label="Monday itinerary example"
            items={[
              {
                id: 'start',
                title: 'Leave Denver',
                time: '9:00 AM',
                dateTime: '2027-06-14T09:00',
                status: 'complete',
              },
              {
                id: 'stop',
                title: 'A morning in the foothills',
                time: '10:30 AM',
                dateTime: '2027-06-14T10:30',
                description: 'Stretch your legs, find a coffee, and take in the view.',
                status: 'current',
              },
              {
                id: 'lunch',
                title: 'Lunch along the way',
                time: '12:30 PM',
                dateTime: '2027-06-14T12:30',
              },
            ]}
          />
        ) : (
          <div className="rt-stack">
            <p className="rt-title">Explore along your route</p>
            <p className="rt-copy">
              Place your existing map here. Keep route controls above the map and place details in a
              single rounded sheet.
            </p>
            <ActionButton variant="secondary" onClick={() => setView('itinerary')}>
              Back to itinerary
            </ActionButton>
          </div>
        )}
      </Sheet>
    </DesignFrame>
  );
}
