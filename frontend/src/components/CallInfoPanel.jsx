import { CATEGORIES, SEVERITY } from '../lib/meta';

export default function CallInfoPanel({ scenario, status, callerKnown }) {
  const cat = CATEGORIES[scenario.category] ?? { label: scenario.category };
  const sev = SEVERITY[scenario.severity] ?? { label: scenario.severity };
  const call = scenario.call ?? {};

  return (
    <div className="panel call-info">
      <div className="panel-head">
        <span className={`badge badge-cat ${CATEGORIES[scenario.category]?.tone ?? 'tone-neutral'}`}>
          {cat.label}
        </span>
        <span className="severity-tag">Уровень: {sev.label}</span>
      </div>
      <dl className="call-info-list">
        <div>
          <dt>Номер АОН</dt>
          <dd>{call.phone ?? '—'}</dd>
        </div>
        <div>
          <dt>Звонящий</dt>
          <dd>{callerKnown ? 'Определён автоматически' : 'Не определён'}</dd>
        </div>
        <div>
          <dt>Автопозиционирование</dt>
          <dd>{call.address_auto?.known ? 'Есть' : 'Нет'}</dd>
        </div>
        <div>
          <dt>Линия</dt>
          <dd className={status === 'connected' ? 'line-ok' : 'line-ring'}>{status === 'ringing' ? 'Входящий вызов' : 'Обрабатывается'}</dd>
        </div>
      </dl>
    </div>
  );
}