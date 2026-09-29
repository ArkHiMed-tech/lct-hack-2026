/**
 * Верхняя плашка АРМ 112 — по эталону `верхняя плашка.png` / `Пример.png`.
 *
 * Полоса слева направо:
 *  [Отключение | записи звонков / список SMS]
 *  [АОН] [предоставленный] [телефон на место]
 *  [Происшествие NNNN · Сохр. · Опер. | просмотр / дополнение]
 *  [таймер мм:сс]
 *
 * mode="edit"  — страница /card: телефоны — input'ы.
 * mode="view"  — страница /scenario/:id: телефоны — только чтение.
 */
export default function TopStrip({
  mode = 'view',
  incidentNo = '—',
  savedAt = '',
  operInfo = '',
  phones = {},
  onPhoneChange = null,
  phoneRefs = {},
  phoneHints = {},
  onCall = null,
  onCopyAon = null,
  onSms = null,
  onRecords = null,
  onSmsList = null,
  timer = null,
  onView = null,
  onAdd = null,
  timerOver = false,
}) {
  const cell = (key, label, valueKey, hint) => (
    <div className="topstrip-cell" key={key}>
      <span className="topstrip-ico" aria-hidden>📞</span>
      <div className="topstrip-body">
        <small className="topstrip-label">
          {label}
          {hint && <span className="topstrip-hint"> ({hint})</span>}
        </small>
        {mode === 'edit' ? (
          <div className="topstrip-row">
            <input
              ref={phoneRefs[valueKey]}
              className="topstrip-num topstrip-input"
              value={phones[valueKey] ?? ''}
              onChange={(e) => onPhoneChange?.(valueKey, e.target.value)}
              placeholder="+7 (__) ___-__-__"
            />
            <div className="topstrip-actions">
              <button type="button" className="topstrip-mini" title="Исходящий звонок (мок)" onClick={() => onCall?.(valueKey)}>📞</button>
              {valueKey !== 'aon' && (
                <button type="button" className="topstrip-mini" title="Скопировать АОН" onClick={() => onCopyAon?.(valueKey)}>АОН</button>
              )}
              <button type="button" className="topstrip-mini" title="Отправить СМС" onClick={() => onSms?.(valueKey)}>💬</button>
            </div>
          </div>
        ) : (
          <div className="topstrip-row">
            <span className="topstrip-num">{phones[valueKey] || '+7 (__) ___-__-__'}</span>
            <div className="topstrip-actions">
              <button type="button" className="topstrip-mini" title="Исходящий звонок (мок)" onClick={() => onCall?.(valueKey)}>📞</button>
              <button type="button" className="topstrip-mini" title="СМС" onClick={() => onSms?.(valueKey)}>💬</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="topstrip" data-mode={mode}>
      {/* Отключение */}
      <div className="topstrip-cell topstrip-off">
        <span className="topstrip-ico" aria-hidden>📞</span>
        <div className="topstrip-body">
          <b className="topstrip-label">Отключение</b>
          <div className="topstrip-btns">
            <button type="button" className="topstrip-mini" onClick={() => onRecords?.()}>записи звонков</button>
            <button type="button" className="topstrip-mini" onClick={() => onSmsList?.()}>список SMS</button>
          </div>
        </div>
      </div>

      {cell('aon', 'АОН', 'aon', phoneHints.aon)}
      {cell('provided', 'предоставленный', 'provided', phoneHints.provided)}
      {cell('onsite', 'телефон на место', 'onsite', phoneHints.onsite)}

      {/* Происшествие */}
      <div className="topstrip-cell topstrip-incident">
        <div className="topstrip-incident-info">
          <b>Происшествие {incidentNo}</b>
          {savedAt && <><br />{savedAt}</>}
          {operInfo && <><br />{operInfo}</>}
        </div>
        <div className="topstrip-sidebtns">
          <button type="button" className="topstrip-view" onClick={() => onView?.()}>просмотр</button>
          <button type="button" className="topstrip-add" onClick={() => onAdd?.()}>дополнение</button>
        </div>
      </div>

      {/* Таймер */}
      {timer && (
        <div className={`topstrip-timer${timerOver ? ' over' : ''}`}>{timer}</div>
      )}
    </div>
  );
}
