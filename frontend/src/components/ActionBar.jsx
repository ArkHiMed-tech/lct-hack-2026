export default function ActionBar({ status, dispatched, onAnswer, onDispatch, onEnd, onRestart, servicesSelected }) {
  return (
    <div className="action-bar">
      {status === 'ringing' ? (
        <button type="button" className="btn btn-primary btn-answer" onClick={onAnswer}>
          Ответить на вызов
        </button>
      ) : (
        <>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onDispatch}
            disabled={dispatched}
            title={dispatched ? 'Вызов уже передан' : servicesSelected ? '' : 'Сначала выберите службы'}
          >
            {dispatched ? 'Вызов передан' : 'Передать в службы'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={onEnd}>
            Завершить вызов
          </button>
        </>
      )}
      <button type="button" className="btn btn-ghost btn-sm" onClick={onRestart}>
        Начать заново
      </button>
    </div>
  );
}