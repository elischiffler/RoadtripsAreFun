import PropTypes from 'prop-types';
import { placeSourceLines } from './placeSource.js';

export default function PlaceSource({ place }) {
  const lines = placeSourceLines(place);
  if (!lines.length) return null;
  return (
    <div className="place-source" aria-label="Place sources">
      <small>
        <a href="/catalog-attribution.html">Sources</a>
      </small>
    </div>
  );
}
PlaceSource.propTypes = { place: PropTypes.object };
