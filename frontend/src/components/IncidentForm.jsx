import { getFormFields } from '../lib/meta';

function FieldControl({ field, value, onChange }) {
  if (field.kind === 'select') {
    return (
      <select value={value ?? ''} onChange={(e) => onChange(field.id, e.target.value)}>
        <option value="">— выберите —</option>
        {field.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }
  if (field.kind === 'multi') {
    const values = value ?? [];
    return (
      <div className="chips-inline">
        {field.options.map((o) => {
          const checked = values.includes(o);
          return (
            <button
              key={o}
              type="button"
              className={`chip-mini ${checked ? 'checked' : ''}`}
              onClick={() => onChange(field.id, checked ? values.filter((v) => v !== o) : [...values, o])}
            >
              {checked ? '✓ ' : ''}
              {o}
            </button>
          );
        })}
      </div>
    );
  }
  return (
    <input
      type="text"
      value={value ?? ''}
      onChange={(e) => onChange(field.id, e.target.value)}
      placeholder={field.label}
    />
  );
}

export default function IncidentForm({ scenario, values, onChange, disabled, pick, omit }) {
  const all = getFormFields(scenario);
  let fields = pick ? all.filter((f) => pick.includes(f.id)) : all;
  if (omit) fields = fields.filter((f) => !omit.includes(f.id));
  if (!fields.length) return null;

  const filled = fields.filter((f) => {
    const v = values[f.id];
    if (Array.isArray(v)) return v.length > 0;
    return String(v ?? '').trim() !== '';
  }).length;

  return (
    <div className="panel incident-form">
      <div className="panel-head">
        <span>Карточка вызова</span>
        <span className="progress-mini">
          {filled}/{fields.length}
        </span>
      </div>
      {fields.map((f) => (
        <label key={f.id} className="field field-compact">
          <span>
            {f.label}
            {f.required && <span className="req-flag"> · обяз.</span>}
          </span>
          <FieldControl field={f} value={values[f.id]} onChange={onChange} disabled={disabled} />
        </label>
      ))}
    </div>
  );
}