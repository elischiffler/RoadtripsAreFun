import { useState } from 'react';
import PropTypes from 'prop-types';
import './PlaceContext.css';

const localImage = /^\/place-images\/[a-z0-9-]+\.(jpg|jpeg|png|webp)$/;

function reviewedImage(image) {
  if (
    !image ||
    !localImage.test(image.src) ||
    typeof image.alt !== 'string' ||
    !image.alt.trim() ||
    typeof image.credit !== 'string' ||
    !image.credit.trim() ||
    image.license !== 'CC BY-SA 4.0' ||
    image.license_url !== 'https://creativecommons.org/licenses/by-sa/4.0/' ||
    !Number.isInteger(image.width) ||
    !Number.isInteger(image.height) ||
    image.width <= 0 ||
    image.height <= 0
  )
    return null;
  try {
    const url = new URL(image.source_url);
    if (
      url.protocol !== 'https:' ||
      url.host !== 'commons.wikimedia.org' ||
      url.username ||
      url.password ||
      !(url.pathname.startsWith('/wiki/File:') || url.pathname === '/w/index.php')
    )
      return null;
  } catch {
    return null;
  }
  return image;
}

export default function PlaceContext({ context }) {
  const [failedImage, setFailedImage] = useState(null);
  if (typeof context?.summary !== 'string' || !context.summary.trim()) return null;
  const photo = reviewedImage(context.image);
  return (
    <div className="place-context">
      <p className="place-context-summary">{context.summary}</p>
      {photo && failedImage !== photo.src && (
        <figure className="place-context-photo">
          <img
            src={photo.src}
            alt={photo.alt}
            width={photo.width}
            height={photo.height}
            loading="lazy"
            onError={() => setFailedImage(photo.src)}
          />
          <figcaption>
            {photo.caption && <span>{photo.caption} </span>}
            <a href={photo.source_url} target="_blank" rel="noopener noreferrer">
              Photo: {photo.credit}
            </a>
            {' · '}
            <a href={photo.license_url} target="_blank" rel="noopener noreferrer">
              {photo.license}
            </a>
          </figcaption>
        </figure>
      )}
    </div>
  );
}

PlaceContext.propTypes = { context: PropTypes.object };
