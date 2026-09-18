import { SERVICES } from '../lib/meta';

export default function DispatchPanel({ scenario, selected, onToggle, disabled }) {
  const available = scenario.call?.available_services ?? Object.keys(SERVICES);

  return (
    <div className="panel dispatch-panel">
      <div className="panel-head">
        <span>Передача вызова</span>
        <span className="progress-mini">
          {selected.length}{available.length ? `/${available.length}` : ''}
        </span>
      </div>
      <p className="panel-note">Отметьте экстренные службы для направления на вызов.</p>
      <div className="dispatch-list">
        {available.map((id) => (
          <label key={id} className={`dispatch-item ${selected.includes(id) ? 'checked' : ''}`}>
            <input
              type="checkbox"
              checked={selected.includes(id)}
              onChange={() => onToggle(id)}
              disabled={disabled}
            />
            <span>{SERVICES[id] ?? id}</span>
          </label>
        ))}
      </div>
    </div>
  );
}