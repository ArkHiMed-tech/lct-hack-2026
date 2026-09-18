export default function QuickReplyPanel({ quickReplies, onInsert, disabled }) {
  if (!quickReplies?.length) return null;

  return (
    <div className="quick-reply-wrap">
      <span className="panel-label">Подсказки</span>
      <div className="quick-reply-list">
        {quickReplies.map((qr, i) => (
          <button
            key={i}
            type="button"
            className="btn btn-ghost btn-qr"
            onClick={() => onInsert(qr.text)}
            disabled={disabled}
          >
            {qr.label}
          </button>
        ))}
      </div>
    </div>
  );
}