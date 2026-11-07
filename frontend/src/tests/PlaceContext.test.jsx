import { expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import PlaceContext from '../components/PlaceContext';
import ItineraryDays from '../components/ItineraryDays';

const image = {
  src: '/place-images/chautauqua-trail-2026.jpg',
  alt: 'Chautauqua trail in October 2026',
  credit: 'Dough4872',
  license: 'CC BY-SA 4.0',
  license_url: 'https://creativecommons.org/licenses/by-sa/4.0/',
  source_url: 'https://commons.wikimedia.org/wiki/File:Reviewed.jpeg',
  caption: 'Historical photo; source-provided resized preview.',
  width: 960,
  height: 720,
};

it('renders reviewed factual context, local image and mandatory rights credit', () => {
  const context = { summary: 'A trailhead with picnic facilities.', image };
  const original = structuredClone(context);
  render(<PlaceContext context={context} />);
  expect(screen.getByText(context.summary)).toBeInTheDocument();
  expect(screen.getByRole('img')).toHaveAttribute('src', image.src);
  expect(screen.getByRole('img')).toHaveAttribute('loading', 'lazy');
  expect(screen.getByRole('link', { name: 'Photo: Dough4872' })).toHaveAttribute(
    'href',
    image.source_url
  );
  expect(screen.getByRole('link', { name: image.license })).toHaveAttribute(
    'href',
    image.license_url
  );
  expect(screen.queryByText(/^Source:/)).not.toBeInTheDocument();
  expect(context).toEqual(original);
});

it.each([
  { ...image, src: 'https://unreviewed.test/photo.jpg' },
  { ...image, src: '/place-images/../secret.jpg' },
  { ...image, src: '/place-images/executable.svg' },
  { ...image, source_url: 'javascript:alert(1)' },
  { ...image, source_url: 'https://commons.wikimedia.org.evil.test/wiki/File:X' },
  { ...image, source_url: 'https://evil@commons.wikimedia.org/wiki/File:X' },
  { ...image, license: 'Unknown rights' },
  { ...image, credit: '' },
])('keeps summary but suppresses unsafe or unlicensed image %#', (badImage) => {
  render(<PlaceContext context={{ summary: 'Known facts remain useful.', image: badImage }} />);
  expect(screen.getByText('Known facts remain useful.')).toBeInTheDocument();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

it('has no fabricated placeholder when context or image is unavailable', () => {
  const { container, rerender } = render(<PlaceContext />);
  expect(container).toBeEmptyDOMElement();
  rerender(<PlaceContext context={{ summary: 'A reviewed summary.', image }} />);
  fireEvent.error(screen.getByRole('img'));
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.getByText('A reviewed summary.')).toBeInTheDocument();
});

it('treats facts as text and renders context on itinerary arrivals only when supplied', () => {
  const summary = '<img src=x onerror=alert(1)> A literal source string.';
  render(
    <ItineraryDays
      itinerary={[
        {
          date: '2030-06-01',
          stops: [
            { name: 'Trailhead', type: 'stop', place_context: { summary } },
            { name: 'Legacy stop', type: 'stop' },
          ],
        },
      ]}
    />
  );
  expect(screen.getByText(summary)).toBeInTheDocument();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.getByText('Legacy stop')).toBeInTheDocument();
});
