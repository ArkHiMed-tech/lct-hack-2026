export default function ChecklistProgress({ groups, total }) {
  return (
    <div className="panel checklist-progress">
      <div className="panel-head">
        <span>Протокол (черновик)</span>
        {total != null && (
          <span className="progress-total">{Math.round(total * 100)}%</span>
        )}
      </div>
      <div className="checklist-groups">
        {groups.map((g) => (
          <div key={g.id} className="checklist-group">
            <div className="checklist-group-head">
              <span>
                {g.id} · {g.title}
              </span>
              <span>{Math.round(g.score * 100)}%</span>
            </div>
            <div className="checklist-bar">
              <div
                className={`checklist-bar-fill ${g.score >= 1 ? 'done' : g.score >= 0.5 ? 'partial' : ''}`}
                style={{ width: `${g.score * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="panel-note">Мгновенная обратная связь. Итоговый балл считает бэкенд.</p>
    </div>
  );
}