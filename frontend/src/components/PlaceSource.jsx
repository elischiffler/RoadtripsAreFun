import PropTypes from 'prop-types';
import { placeSourceLines } from './placeSource.js';

export default function PlaceSource({ place }) {
  const lines = placeSourceLines(place);
  if (!lines.length) return null;
  return (
    <div className="place-source" aria-label="Place source and freshness">
      {lines.map((line) => (
        <small key={line} style={{ display: 'block' }}>
          {line}
        </small>
      ))}
      <small>
        <a href="/catalog-attribution.html">Data licenses and attribution</a>
      </small>
    </div>
  );
}
PlaceSource.propTypes = { place: PropTypes.object };
