export default function ErrorBanner({ message, onRetry }) {
  return (
    <div className="error-banner" role="alert">
      <div>
        <strong>Ошибка загрузки данных</strong>
        {message && <p>{message}</p>}
      </div>
      {onRetry && (
        <button type="button" className="btn btn-ghost" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}