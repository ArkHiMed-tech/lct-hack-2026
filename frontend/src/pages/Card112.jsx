import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import {
  INCIDENT_TYPES as BUNDLED_TYPES,
  TAG_SETS as BUNDLED_TAGS,
  QUICK_TYPES,
  detailOptionsFor,
  autoServicesFor,
} from '../lib/incidentClassifier';
import { INFO_TYPES, SMELL_SIGN, visibleTagRows, pruneHiddenTags } from '../lib/tagVisibility';
import { SERVICE_CATALOG, SVC_102, SVC_103, SVC_104, serviceShortName } from '../lib/serviceCatalog';

// Норматив набора карточки (сек). При превышении таймер краснеет (по ТЗ).
const CARD_SLA_SEC = 75;
const INCIDENT_NO = 36812195;

const EMPTY_TAGS = {
  where: '', sign: '', access: '', detail: '',
  place: '', threat: '', violation: '', medical: '', evac: '', gas: '', tagDesc: '',
};
// Умный каскад fire101: из всех уровней от соседних зависит только
// детализация (её список определяется «Где»), у остальных опции статичные.
// Поэтому выбор нижних параметров никогда не сбрасывает верхние,
// а смена «Где» чистит детализацию, только если значение стало невалидным.

// Каталог служб — полный справочник из тз/СЛУЖБЫ 112.docx (lib/serviceCatalog).
// BACKEND-READY: позже заменить на справочник с бэкенда.

// Типы без выезда служб: автоподбор отключён полностью (вручную через «+» добавить можно).
// Список живёт в lib/tagVisibility (там же используется для видимости ТЭГов).
const isNoAutoType = (t) => !!t && INFO_TYPES.includes(t.title);

const OKRUGA = ['ЦАО', 'САО', 'СВАО', 'ВАО', 'ЮВАО', 'ЮАО', 'ЮЗАО', 'ЗАО', 'СЗАО', 'ЗелАО', 'ТАО', 'НАО'];
const APPLICANT_STATUS = ['Пострадавшие', 'Нет на месте/\nОтказ от скорой', 'Нет доступа/\nЗаблокированные', 'нет контакта', 'срыв звонка'];

function TagRow({ label, options, value, onPick }) {
  return (
    <div className="arm-tagrow">
      <div className="arm-taglabel">{label}</div>
      <div className="arm-tagopts">
        {options.map((o) => (
          <button key={o} type="button" className={`arm-tag ${value === o ? 'sel' : ''}`} onClick={() => onPick(value === o ? '' : o)}>
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Card112() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [listOpen, setListOpen] = useState(false);
  // Классификатор: пробуем бэкенд /api/incident-types, иначе бандл из ТЗ.
  const [types, setTypes] = useState(BUNDLED_TYPES);
  const [tagSets, setTagSets] = useState(BUNDLED_TAGS);
  const [selectedType, setSelectedType] = useState(null); // {title, groups, kind}
  const [tags, setTags] = useState({ ...EMPTY_TAGS });
  const [formError, setFormError] = useState('');
  // Службы: авто-подбор считается заново от типа+ТЭГов при каждом рендере,
  // ручные добавления — в manualServices, снятые крестиком — в excludedServices
  // (авто их больше не возвращает). Итог уходит в БД одним списком.
  const [manualServices, setManualServices] = useState([]);
  const [excludedServices, setExcludedServices] = useState([]);
  const [svcMenuOpen, setSvcMenuOpen] = useState(false);
  const [addr, setAddr] = useState({ country: '', subject: 'Москва', settlement: '', object: '', okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' });
  const [applicant, setApplicant] = useState('');
  const [appStatuses, setAppStatuses] = useState([]);
  const [desc, setDesc] = useState('');
  const [toast, setToast] = useState(null);
  const [savedScenarioId, setSavedScenarioId] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/incident-types')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (cancelled || !data) return;
        if (Array.isArray(data.items) && data.items.length >= 51) setTypes(data.items);
      })
      .catch(() => { /* offline fallback: бандл */ });
    fetch('/api/incident-tree?path=' + encodeURIComponent('101'))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled && data && data.tag_sets && Object.keys(data.tag_sets).length) setTagSets(data.tag_sets);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const startedAtRef = useRef(Date.now());
  const typeListRef = useRef(null);
  const svcMenuRef = useRef(null);
  // Клик вне всплывающих списков — скрыть их.
  useEffect(() => {
    const onDown = (e) => {
      if (typeListRef.current && !typeListRef.current.contains(e.target)) setListOpen(false);
      if (svcMenuRef.current && !svcMenuRef.current.contains(e.target)) setSvcMenuOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    startedAtRef.current = Date.now();
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const elapsedSec = Math.floor((now - startedAtRef.current) / 1000);
  const overtime = elapsedSec > CARD_SLA_SEC;
  const mm = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
  const ss = String(elapsedSec % 60).padStart(2, '0');

  const group = selectedType ? selectedType.groups[0] : null;
  const isFire = selectedType ? selectedType.kind === 'fire101' : false;

  // Авто-службы: пересчёт от актуальных типа+ТЭГов (без залипания старых).
  // При «Запахе гари» 102 и 104 не подбираются (ни за нарушение, ни за газ).
  const autoServices = useMemo(() => {
    if (!selectedType || isNoAutoType(selectedType)) return [];
    const flat = Object.values(tags).filter(Boolean);
    let auto = autoServicesFor(selectedType.groups[0], flat);
    const hasViolation = tags.violation === 'Да' || tags.violation === 'Есть' || tags.violation === 'Есть правонарушение';
    if (hasViolation && !auto.includes(SVC_102)) auto = [...auto, SVC_102];
    if (tags.medical === 'Да' && !auto.includes(SVC_103)) auto = [...auto, SVC_103];
    if (tags.sign === SMELL_SIGN) auto = auto.filter((s) => s !== SVC_102 && s !== SVC_104);
    return [...new Set(auto)];
  }, [selectedType, tags]);

  const services = useMemo(
    () => [...new Set([
      ...autoServices.filter((s) => !excludedServices.includes(s)),
      ...manualServices.filter((s) => !excludedServices.includes(s)),
    ])],
    [autoServices, manualServices, excludedServices],
  );

  // Видимые ряды ТЭГов по матрице lib/tagVisibility (скрытые значения чистятся в setTag).
  const vis = useMemo(
    () => visibleTagRows({ kind: selectedType?.kind, title: selectedType?.title, tags }),
    [selectedType, tags],
  );

  const filteredTypes = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return types;
    return types.filter((t) => t.title.toLowerCase().includes(q));
  }, [query, types]);

  // Выбор типа: ПОЛНЫЙ сброс всех ТЭГов (решение пользователя), пересчет служб.
  const pickType = (t) => {
    setSelectedType(t);
    setQuery('');
    setListOpen(false);
    setTags({ ...EMPTY_TAGS });
    setFormError('');
    setSavedScenarioId(null);
    setManualServices([]);
    setExcludedServices([]);
  };

  const clearType = () => {
    setSelectedType(null);
    setTags({ ...EMPTY_TAGS });
    setFormError('');
    setSavedScenarioId(null);
    setManualServices([]);
    setExcludedServices([]);
    setQuery('');
  };

  const setTag = (key, v) => {
    let next = { ...tags, [key]: v };
    if (key === 'where' && next.detail && !detailOptionsFor(v, tagSets).includes(next.detail)) {
      next.detail = '';
    }
    // Скрытые матрицей видимости ряды — очистить (не уйдут в БД и службы).
    next = pruneHiddenTags(next, visibleTagRows({ kind: selectedType?.kind, title: selectedType?.title, tags: next }));
    setTags(next);
    setFormError('');
    // Службы пересчитаются сами через autoServices (мемоизация от tags).
  };

  const validate = () => {
    if (!selectedType) return 'Выберите «Что случилось?» — поле обязательно.';
    if (isFire && !tags.where) return 'Укажите «Где» для происшествия 101.';
    if (isFire && !tags.sign) return 'Укажите признак: «Открытое пламя / Дым» или «Запах гари».';
    return '';
  };

  const toggleAppStatus = (s) => setAppStatuses((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]));
  // Ручное добавление: запоминаем ВСЕГДА (даже если служба сейчас есть в авто —
  // иначе при смене ТЭГов авто её роняет и ручной выбор теряется).
  // Снимает службу из исключённых.
  const addService = (s) => {
    setExcludedServices((p) => p.filter((x) => x !== s));
    setManualServices((p) => (p.includes(s) ? p : [...p, s]));
    setSvcMenuOpen(false);
  };
  // Крестик: убирает службу из показа; авто-подбор её больше не вернёт
  // (повторно добавить можно через «+»). Сбрасывается при смене типа.
  const removeService = (s) => {
    setManualServices((p) => p.filter((x) => x !== s));
    setExcludedServices((p) => (p.includes(s) ? p : [...p, s]));
  };

  const clearAddress = () => setAddr({ country: '', subject: 'Москва', settlement: '', object: '', okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' });

  const handleSave = async () => {
    const err = validate();
    if (err) { setFormError(err); return; }
    setSaving(true);
    setSavedScenarioId(null);
    const addrStr = [addr.subject, addr.okrug && `округ ${addr.okrug}`, addr.street && `ул. ${addr.street}`, addr.house && `д. ${addr.house}`]
      .filter(Boolean).join(', ');
    // Итог в БД: авто (минус снятые крестиком) + ВСЕ ручные. Ручные не теряются,
    // даже если совпадают с авто или ТЭГи менялись после добавления.
    const finalServices = [...services];
    const manualCount = manualServices.filter((s) => !excludedServices.includes(s)).length;
    const payload = {
      user_id: user?.id ?? null,
      what: selectedType.title,
      incident_category: group,
      incident_kind: selectedType.kind,
      address: addrStr,
      address_obj: addr,
      caller_name: applicant,
      caller_statuses: appStatuses,
      factors: Object.entries(tags).filter(([, v]) => v).map(([k, v]) => `${k}:${v}`),
      tags,
      services: finalServices,
      services_manual: manualServices.filter((s) => !excludedServices.includes(s)),
      description: desc,
      elapsed_sec: elapsedSec,
      overtime,
    };
    try {
      const res = await fetch('/api/reports/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      let scenarioId = null;
      try {
        const pub = await fetch(`/api/reports/${data.report_id}/publish`, { method: 'POST' });
        if (pub.ok) scenarioId = (await pub.json()).scenario_id ?? null;
      } catch { /* карточка уже в БД, происшествие создадим позже */ }
      if (scenarioId) setSavedScenarioId(scenarioId);
      setToast(`Сохранено в БД: «${selectedType.title}», карточка №${data.report_id}${scenarioId ? `, происшествие ${scenarioId}` : ''}, служб: ${finalServices.length} (авто: ${finalServices.length - manualCount}, вручную: ${manualCount}).`);
    } catch {
      console.log('[card112 save fallback]', payload);
      setToast(`Бэкенд недоступен — мок-сохранение: «${selectedType.title}», служб: ${services.length}.`);
    } finally {
      setSaving(false);
    }
  };

  const setA = (k) => (e) => setAddr({ ...addr, [k]: e.target.value });
  const today = new Date().toLocaleDateString('ru-RU');
  const detailOptions = detailOptionsFor(tags.where, tagSets);
  const detailLabel = !tags.where || tags.where === 'Улица' ? 'Улица (пламя, дым)'
    : tags.where === 'Транспорт' ? 'Транспорт (пламя, дым)'
    : `${tags.where} (детализация)`;
  const signLabel = tags.where === 'Транспорт' ? 'Признак пожара (транспорт)' : 'Признак пожара (улица)';

  return (
    <div className="app-shell">
      <AppHeader title="Карточка происшествия 112" showCreateButton={false} />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="dds-back">
            <Link to="/">← К списку происшествий</Link>
            <Link to="/card">Новая карточка</Link>
          </div>

          <div className="arm-wrap">
            {/* Шапка карточки: заголовок + таймер */}
            <div className="arm-titlebar">
              <span>Происшествие {INCIDENT_NO}</span>
              <span className="arm-titleinfo">Сохр. {today} · Опер., АРМ 2, УМЦ О п</span>
              <span className={`arm-timer ${overtime ? 'over' : ''}`}>{mm}:{ss}<small>минут секунд</small></span>
            </div>

            {/* Телефоны */}
            <div className="arm-phones">
              <div className="arm-phone arm-off">
                <span className="arm-tel-ico">📞</span>
                <div><b>Отключение</b><div className="arm-minibtns"><span>записи звонков</span><span>список SMS</span></div></div>
              </div>
              {[['АОН', 0], ['предоставленный', 1], ['телефон на место', 2]].map(([label]) => (
                <div className="arm-phone" key={label}>
                  <span className="arm-tel-ico">📞</span>
                  <div><small>{label}</small><div className="arm-telnum">+7 (__) __-__</div></div>
                </div>
              ))}
            </div>

            {/* Заявитель + статусы */}
            <div className="arm-appline">
              <label>Фамилия и имя заявителя <input value={applicant} onChange={(e) => setApplicant(e.target.value)} placeholder="" /></label>
              <label>выберите статус
                <select value={appStatuses[0] ?? ''} onChange={(e) => e.target.value && toggleAppStatus(e.target.value)}>
                  <option value="">—</option>
                  {APPLICANT_STATUS.map((s) => <option key={s} value={s}>{s.replace('\n', ' ')}</option>)}
                </select>
              </label>
              <div className="arm-appchips">
                {APPLICANT_STATUS.map((s) => (
                  <button key={s} type="button" className={`arm-appchip ${appStatuses.includes(s) ? 'sel' : ''} ${s === 'нет контакта' || s === 'срыв звонка' ? 'red' : ''}`} onClick={() => toggleAppStatus(s)}>
                    {s.split('\n').map((p, i) => <span key={i}>{p}<br /></span>)}
                  </button>
                ))}
              </div>
            </div>

            <div className="arm-cols">
              {/* СЛЕВА: адрес */}
              <section className="arm-card">
                <div className="arm-cardhead">Адрес: <b>Москва</b></div>
                <div className="arm-grid3">
                  <label>Страна:<input value={addr.country} onChange={setA('country')} /></label>
                  <label>Субъект:<input value={addr.subject} onChange={setA('subject')} /></label>
                  <label>Населенный пункт:<input value={addr.settlement} onChange={setA('settlement')} /></label>
                </div>
                <div className="arm-grid3">
                  <label>Объект:<input value={addr.object} onChange={setA('object')} /></label>
                  <label>Округ:<select value={addr.okrug} onChange={setA('okrug')}><option value="">—</option>{OKRUGA.map((o) => <option key={o} value={o}>{o}</option>)}</select></label>
                  <label>Район:<input value={addr.rayon} onChange={setA('rayon')} /></label>
                </div>
                <div className="arm-grid3">
                  <label>Улица:<input value={addr.street} onChange={setA('street')} /></label>
                  <label>Дом/Вл:<input value={addr.house} onChange={setA('house')} /></label>
                  <label>Корпус:<input value={addr.corpus} onChange={setA('corpus')} /></label>
                </div>
                <div className="arm-grid5">
                  <label>Стр/соор:<input value={addr.stroenie} onChange={setA('stroenie')} /></label>
                  <label>Квартира/офис:<input value={addr.flat} onChange={setA('flat')} /></label>
                  <label>Подъезд:<input value={addr.entrance} onChange={setA('entrance')} /></label>
                  <label>Этаж:<input value={addr.floor} onChange={setA('floor')} /></label>
                  <label>Код:<input value={addr.code} onChange={setA('code')} /></label>
                </div>
                <label className="arm-block">Описательный адрес:<textarea rows={2} value={addr.descr} onChange={setA('descr')} /></label>
                <div className="arm-rowend"><button type="button" className="arm-minibtn" onClick={clearAddress}>очистить адрес</button></div>

                <div className="arm-desc">
                  <div className="arm-deschead">Описание со слов заявителя</div>
                  <textarea rows={6} maxLength={1999} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="введите" />
                  <div className="arm-counter">{desc.length} / 1999</div>
                </div>
              </section>

              {/* СПРАВА: происшествие — переписано под КАРТОЧКА 112.docx */}
              <section className="arm-right">
                {!selectedType ? (
                  <div className="arm-card">
                    <div className="arm-linkhead">Введите тип происшествия <span className="arm-count">{types.length}</span></div>
                    <div className="arm-searchwrap" ref={typeListRef}>
                      <input
                        className="arm-what" value={query} placeholder="что случилось? (поиск по 51 типу)"
                        onChange={(e) => { setQuery(e.target.value); setListOpen(true); }}
                        onFocus={() => setListOpen(true)}
                      />
                      {listOpen && (
                        <div className="arm-typelist">
                          {filteredTypes.map((t) => (
                            <button key={t.title} type="button" onClick={() => pickType(t)}>
                              {t.title} <small>· {t.groups.join(',')}</small>
                            </button>
                          ))}
                          {!filteredTypes.length && <span className="arm-empty">Ничего не найдено</span>}
                        </div>
                      )}
                    </div>
                    <div className="arm-quick">
                      {QUICK_TYPES.map((q) => {
                        const found = types.find((t) => t.title.toLowerCase().startsWith(q.toLowerCase().replace('справка-', 'справка ')));
                        return <button key={q} type="button" className="arm-tag" onClick={() => found && pickType(found)}>{q}</button>;
                      })}
                    </div>
                    <div className="arm-signif">Значимые типы происшествий:</div>
                    {formError && <div className="arm-err">{formError}</div>}
                  </div>
                ) : (
                  <div className="arm-card">
                    <button type="button" className="arm-linkhead" onClick={clearType}>добавить тип происшествия</button>
                    <div className="arm-typechip">Происшествие {group} · {selectedType.kind === 'fire101' ? 'ветка 101' : 'общая ветка'}</div>
                    <div className="arm-blackhead">Происшествие {group} <span onClick={clearType}>×</span></div>
                    <div className="arm-selectedwhat">{selectedType.title}</div>
                    <div className="arm-tagpanel">
                      {isFire ? (
                        <>
                          {vis.includes('where') && <TagRow label="Где" options={tagSets.where} value={tags.where} onPick={(v) => setTag('where', v)} />}
                          {vis.includes('sign') && <TagRow label={signLabel} options={tagSets.sign} value={tags.sign} onPick={(v) => setTag('sign', v)} />}
                          {vis.includes('access') && <TagRow label="Доступ к людям" options={tagSets.access} value={tags.access} onPick={(v) => setTag('access', v)} />}
                          {vis.includes('detail') && <TagRow label={detailLabel} options={detailOptions} value={tags.detail} onPick={(v) => setTag('detail', v)} />}
                          {vis.includes('place') && <TagRow label="Место происшествия" options={tagSets.place} value={tags.place} onPick={(v) => setTag('place', v)} />}
                          {vis.includes('threat') && <TagRow label="Угроза людям" options={tagSets.threat} value={tags.threat} onPick={(v) => setTag('threat', v)} />}
                          {vis.includes('violation') && <TagRow label="Правонарушение" options={['Да', 'Нет']} value={tags.violation} onPick={(v) => setTag('violation', v)} />}
                          {vis.includes('medical') && <TagRow label="Медицинская помощь" options={tagSets.medical} value={tags.medical} onPick={(v) => setTag('medical', v)} />}
                          {vis.includes('evac') && <TagRow label="Требуется эвакуация" options={tagSets.evac} value={tags.evac} onPick={(v) => setTag('evac', v)} />}
                          {vis.includes('gas') && <TagRow label="Проведена ли газификация" options={tagSets.gas} value={tags.gas} onPick={(v) => setTag('gas', v)} />}
                          <div className="arm-tagrow">
                            <div className="arm-taglabel">Описание</div>
                            <input className="arm-tagdesc" value={tags.tagDesc} onChange={(e) => setTag('tagDesc', e.target.value)} placeholder="уточнение ТЭГа" />
                          </div>
                        </>
                      ) : (
                        <>
                          {vis.includes('threat') && <TagRow label="Угроза людям" options={['Да', 'Нет']} value={tags.threat} onPick={(v) => setTag('threat', v)} />}
                          {vis.includes('violation') && <TagRow label="Правонарушение" options={['Есть правонарушение']} value={tags.violation} onPick={(v) => setTag('violation', v)} />}
                          {vis.includes('medical') && <TagRow label="Медицинская помощь" options={['Да', 'Нет']} value={tags.medical} onPick={(v) => setTag('medical', v)} />}
                          {vis.includes('evac') && <TagRow label="Требуется эвакуация" options={['Да', 'Нет']} value={tags.evac} onPick={(v) => setTag('evac', v)} />}
                          {vis.includes('gas') && <TagRow label="Проведена ли газификация" options={['Да', 'Нет', 'Нет данных']} value={tags.gas} onPick={(v) => setTag('gas', v)} />}
                          <div className="arm-tagrow">
                            <div className="arm-taglabel">Описание</div>
                            <input className="arm-tagdesc" value={tags.tagDesc} onChange={(e) => setTag('tagDesc', e.target.value)} placeholder="уточнение" />
                          </div>
                          {vis.length > 0 && <div className="arm-hint">Общая ветка ({group}): полный каскад 101 не применяется.</div>}
                        </>
                      )}
                    </div>
                    {formError && <div className="arm-err">{formError}</div>}
                  </div>
                )}
              </section>
            </div>

            {/* ВНИЗУ: оранжевая полоса служб */}
            <div className="arm-services">
              <span className="arm-svclabel">Службы:</span>
              <div className="arm-svcchips">
                {services.map((s) => (
                  <span key={s} className="arm-svc" title={s}><span className="arm-svctel">📞</span> <span className="arm-svcname">{serviceShortName(s)}</span> <button type="button" onClick={() => removeService(s)} title="убрать">×</button></span>
                ))}
                <div className="arm-svcadd" ref={svcMenuRef}>
                  <button type="button" className="arm-plus" onClick={() => setSvcMenuOpen((v) => !v)}>+</button>
                  {svcMenuOpen && (
                    <div className="arm-svcmenu">
                      {SERVICE_CATALOG.filter((s) => !services.includes(s)).map((s) => (
                        <button key={s} type="button" onClick={() => addService(s)}>{s}</button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="arm-actions">
                <button type="button" className="arm-save" onClick={handleSave} disabled={saving}>{saving ? 'сохранение…' : 'сохранить'}</button>
                <button type="button" className="arm-icobtn" title="связи">🔗</button>
                <button type="button" className="arm-icobtn" title="таймер">⏱</button>
                <button type="button" className="arm-icobtn" title="привлечь внимание">✋</button>
                <button type="button" className="arm-icobtn" title="напоминание">🔔</button>
                <button type="button" className="arm-icobtn" title="сообщение">💬</button>
                <button type="button" className="arm-icobtn" title="закрыть">×</button>
              </div>
            </div>
            {overtime && <div className="arm-overhint">Время набора карточки превышено (норматив {CARD_SLA_SEC} сек) — поле подсвечено красным.</div>}
          </div>

          {toast && (
            <div className="toast" role="status">
              {toast}{' '}
              {savedScenarioId && (
                <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate(`/scenario/${savedScenarioId}`)}>
                  Открыть в тренажёре →
                </button>
              )}
              <button type="button" className="toast-close" onClick={() => setToast(null)}>×</button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
