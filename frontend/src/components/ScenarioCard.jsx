import { CATEGORIES, DIFFICULTY, SEVERITY, STATUS, formatScore } from '../lib/meta';

export default function ScenarioCard({ scenario, onStart }) {
  const cat = CATEGORIES[scenario.category] ?? { label: scenario.category, tone: 'tone-neutral' };
  const diff = DIFFICULTY[scenario.difficulty] ?? { label: scenario.difficulty, tone: 'diff-medium' };
  const sev = SEVERITY[scenario.severity] ?? { label: scenario.severity };
  const status = STATUS[scenario.status] ?? { label: scenario.status, btn: 'Начать' };

  return (
    <article className={`scenario-card ${scenario.status === 'new' ? 'is-new' : ''}`}>
      <div className="scenario-card-head">
        <span className={`badge badge-cat ${cat.tone}`}>{cat.label}</span>
        <span className={`badge ${diff.tone}`}>{diff.label}</span>
        <span className="tag-severity">Уровень: {sev.label}</span>
        <span className="scenario-status">{status.label}</span>
      </div>

      <h3 className="scenario-title">{scenario.title}</h3>
      <p className="scenario-summary">{scenario.summary}</p>

      <div className="scenario-card-meta">
        <span>≈ {Math.round(scenario.estimate_sec / 60)} мин</span>
        <span>
          Лучший результат:{' '}
          <strong>{formatScore(scenario.best_score)}</strong>
        </span>
      </div>

      <button type="button" className="btn btn-primary btn-block" onClick={() => onStart(scenario)}>
        {status.btn}
      </button>
    </article>
  );
}