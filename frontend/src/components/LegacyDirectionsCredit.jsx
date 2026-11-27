import mapboxCredit from '../assets/mapbox-directions-credit.svg';

// Original in-app logo from Mapbox GL JS 3.5.2, retained for its saved directions.
export default function LegacyDirectionsCredit() {
  return (
    <a
      className="map-route-credit"
      href="https://www.mapbox.com/about/maps/"
      target="_blank"
      rel="noreferrer"
    >
      <img src={mapboxCredit} alt="" width="60" height="15" />
      Directions © Mapbox
    </a>
  );
}
