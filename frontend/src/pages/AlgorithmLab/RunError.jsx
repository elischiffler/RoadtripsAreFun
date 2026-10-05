import PropTypes from 'prop-types';

export default function RunError({ error, attempts = [] }) {
  const records = Array.isArray(attempts) ? attempts : [];
  if (!error && !records.length) return null;
  const cause = error?.causes?.findLast((item) => item.message);
  return (
    <div role={error ? 'alert' : undefined} className={error ? 'lab-error' : 'lab-note'}>
      {error && (
        <p>
          {error.stage && `${error.stage.replaceAll('_', ' ')}: `}
          {error.message} ({error.code})
        </p>
      )}
      {cause?.message && <p>{cause.message}</p>}
      {error?.http_status && <p>Provider HTTP status: {error.http_status}</p>}
      {records.length > 0 && (
        <p>
          {records.filter((item) => item.outcome === 'retrying').length} automatic retries recorded.
          Each retryable request gets up to 3 attempts; completed steps are kept.
        </p>
      )}
      <details>
        <summary>
          {error ? 'Saved error and attempt details' : 'Saved provider retry details'}
        </summary>
        <pre className="lab-stage-json" tabIndex={0} aria-label="Error diagnostic">
          <code>{JSON.stringify({ error, attempts: records }, null, 2)}</code>
        </pre>
      </details>
    </div>
  );
}
RunError.propTypes = { error: PropTypes.object, attempts: PropTypes.arrayOf(PropTypes.object) };
