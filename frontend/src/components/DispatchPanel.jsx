import { useEffect, useRef, useState } from 'react';
import { SERVICES } from '../lib/meta';

// Полный состав дока как в АРМ ДДС: 101 / 104 / 102 / Деп. ЖКХ / ЦЭМП / Служба 103 / ЦОДД / Мос.Без. / Мослифт
// 103 и ЦЭМП — разные ячейки (раньше делили одну ambulance с подписью ЦЭМП).
const DDS_ORDER = [
  { id: 'fire', dds: 'Служба 101' },
  { id: 'gas', dds: 'Служба 104' },
  { id: 'police', dds: 'Служба 102' },
  { id: 'utility', dds: 'Деп. ЖКХ' },
  { id: 'ambulance', dds: 'ЦЭМП' },
  { id: 'smp103', dds: 'Служба 103' },
  { id: 'codd', dds: 'ЦОДД' },
  { id: 'mosbez', dds: 'Мос.Без.' },
  { id: 'moslift', dds: 'Мослифт' },
];

// Вложенные исполнители (как всплывашки ОАТИ / Поселение Ти… / Поселение Во… над Службой 102).
// На оценку не влияют — только учёт статусов, как в ДДС.
const DDS_CHILDREN = {
  police: [
    { id: 'oati', dds: 'ОАТИ' },
    { id: 'pos_ti', dds: 'Поселение Ти…' },
    { id: 'pos_vo', dds: 'Поселение Во…' },
  ],
  utility: [
    { id: 'dep_vo', dds: 'Поселение Вороновское' },
  ],
};

const CHILD_LABELS = {
  oati: 'ОАТИ',
  pos_ti: 'Поселение Ти…',
  pos_vo: 'Поселение Во…',
  dep_vo: 'Поселение Вороновское',
};

const STATUS_OPTIONS = [
  'Принята',
  'Не принята',
  'Начало реагирования',
  'Прибытие',
  'Проведение работ',
  'Работы завершены',
  'Отказ от выполнения работ',
];

function stamp() {
  const n = new Date();
  const p = (v) => String(v).padStart(2, '0');
  return `17.09.2026 ${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;
}

function seedHist() {
  return [
    { t: stamp(), s: 'Добавлена', c: '' },
    { t: stamp(), s: 'Получена службой', c: '' },
  ];
}

function HistPop({ title, rows, id, editing, draft, setDraft, onEdit, onSave, onCancel, onClose, pos = '' }) {
  return (
    <div className={`dds-pop ${pos}`}>
      <div className="dds-pop-head">
        <span>{title}</span>
        <span style={{ display: 'flex', gap: 6 }}>
          <button type="button" onClick={() => onEdit(id)} title="Проставить статус" style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>✎</button>
          {onClose && (
            <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>×</button>
          )}
        </span>
      </div>
      {rows.map((row, i) => (
        <div key={i} className="dds-pop-row">
          <span>оп. 0</span>
          <span>› {row.t} {row.s}</span>
          <span>› {row.c}</span>
        </div>
      ))}
      {editing === id && (
        <div className="dds-status-edit" onClick={(e) => e.stopPropagation()}>
          <select value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })}>
            {STATUS_OPTIONS.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
          <input placeholder="Номер наряда" value={draft.order} onChange={(e) => setDraft({ ...draft, order: e.target.value })} style={{ width: 90 }} />
          <input placeholder="Комментарий" value={draft.comment} onChange={(e) => setDraft({ ...draft, comment: e.target.value })} style={{ width: 170 }} />
          <button type="button" className="ok" onClick={() => onSave(id)}>✓</button>
          <button type="button" className="cancel" onClick={onCancel}>×</button>
        </div>
      )}
    </div>
  );
}

export default function DispatchPanel({ scenario, selected, onToggle, disabled, visibleIds = null, locked = false, extraLabels = [] }) {
  void disabled;
  // Карточный режим: показываем только службы из карточки.
  const ordered = visibleIds ? DDS_ORDER.filter((s) => visibleIds.includes(s.id)) : DDS_ORDER;
  const [open, setOpen] = useState(null);
  const [editing, setEditing] = useState(null);
  const [hist, setHist] = useState({});
  const [draft, setDraft] = useState({ status: 'Принята', order: '', comment: '' });
  // Вторая строка ячеек (после первых 8) — по кнопке правее.
  const [dockExpanded, setDockExpanded] = useState(false);
  const scenarioId = scenario?.id ?? null;
  useEffect(() => { setDockExpanded(false); }, [scenarioId]);
  const dockRef = useRef(null);
  // Клик вне дока — скрыть всплывающие окна служб.
  useEffect(() => {
    const onDown = (e) => {
      if (dockRef.current && !dockRef.current.contains(e.target)) { setOpen(null); setEditing(null); }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  const rowsOf = (id) => hist[id] ?? [{ t: stamp(), s: 'Добавлена', c: '' }];

  const pushHist = (id, status, comment) => {
    setHist((prev) => ({
      ...prev,
      [id]: [...(prev[id] ?? seedHist()), { t: stamp(), s: status, c: comment }],
    }));
  };

  const handleCell = (sid) => {
    if (locked) return; // карточный режим: службы заданы карточкой, менять нельзя
    if (!selected.includes(sid)) onToggle(sid);
    setOpen(open === sid ? null : sid);
    setEditing(null);
  };

  const saveEdit = (id) => {
    pushHist(id, draft.status, draft.comment || (draft.order ? `Наряд ${draft.order}` : ''));
    setEditing(null);
  };

  const popProps = { editing, draft, setDraft, onEdit: (id) => { setEditing(id); setDraft({ status: 'Принята', order: '', comment: '' }); }, onSave: saveEdit, onCancel: () => setEditing(null) };

  const renderCell = (s) => {
    const last = rowsOf(s.id).slice(-1)[0];
    const children = DDS_CHILDREN[s.id] ?? [];
    return (
      <div
        key={s.id}
        className={`dds-service ${open === s.id ? 'active' : ''} ${selected.includes(s.id) ? 'chosen' : ''}`}
        onClick={() => handleCell(s.id)}
        title={SERVICES[s.id] ?? s.dds}
      >
        <span className="arm-svctel">📞</span>
        <b>{s.dds}</b>
        <small>11:14 {last.s}</small>
        {open === s.id && children.length === 0 && (
          <div onClick={(e) => e.stopPropagation()}>
            <HistPop title={s.dds} rows={rowsOf(s.id)} id={s.id} onClose={() => setOpen(null)} {...popProps} />
          </div>
        )}
        {open === s.id && children.length > 0 && (
          <div className="dds-children" onClick={(e) => e.stopPropagation()}>
            {children.map((ch) => (
              <HistPop
                key={ch.id}
                pos="static"
                title={CHILD_LABELS[ch.id] ?? ch.dds}
                rows={rowsOf(ch.id)}
                id={ch.id}
                {...popProps}
              />
            ))}
          </div>
        )}
      </div>
    );
  };

  // Все видимые элементы дока одним списком: ячейки + заглушка + доп. службы.
  // Первая линия — максимум 8, остальные уходят во вторую строку по кнопке.
  const DOCK_PAGE = 8;
  const dockItems = [
    ...ordered.map((s) => ({ key: s.id, node: renderCell(s) })),
    ...(locked && ordered.length === 0 && extraLabels.length === 0
      ? [{
        key: '__none__',
        node: (
          <div className="dds-service" title="Службы не назначались">
            <span className="arm-svctel">📞</span>
            <b>—</b>
            <small>службы не назначались</small>
          </div>
        ),
      }]
      : []),
    ...extraLabels.map((label) => ({
      key: label,
      node: (
        <div key={label} className="dds-service chosen" title={`${label} (из карточки)`}>
          <span className="arm-svctel">📞</span>
          <b>{label}</b>
          <small>из карточки</small>
        </div>
      ),
    })),
  ];
  const dockHidden = Math.max(0, dockItems.length - DOCK_PAGE);

  return (
    <div className="dds-dock" ref={dockRef}>
      <div className="dds-dock-label">Службы:</div>
      <div className="dds-dockrows">
        <div className="dds-dockrow">
          {dockItems.slice(0, DOCK_PAGE).map((i) => i.node)}
          {dockHidden > 0 && (
            <button
              type="button"
              className="dds-dockmore"
              onClick={() => setDockExpanded((v) => !v)}
              title={dockExpanded ? 'свернуть вторую строку' : `показать ещё ${dockHidden}`}
            >
              {dockExpanded ? '△' : `+${dockHidden} ▽`}
            </button>
          )}
        </div>
        {dockExpanded && dockHidden > 0 && (
          <div className="dds-dockrow">
            {dockItems.slice(DOCK_PAGE).map((i) => i.node)}
          </div>
        )}
      </div>
    </div>
  );
}
