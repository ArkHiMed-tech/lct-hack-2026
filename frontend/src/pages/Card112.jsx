import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import {
  INCIDENT_TYPES as BUNDLED_TYPES,
  TAG_SETS as BUNDLED_TAGS,
  QUICK_TYPES,
  SIGNIFICANT_TYPES,
  CHANNELS,
  searchTypes,
  detailOptionsFor,
  autoServicesFor,
} from '../lib/incidentClassifier';
import { INFO_TYPES, SMELL_SIGN, visibleTagRows, pruneHiddenTags } from '../lib/tagVisibility';
import { SERVICE_CATALOG, SVC_102, SVC_103, SVC_104, serviceShortName, isMainService } from '../lib/serviceCatalog';

// Таймер: отсчет с открытия до «Сохранить» для отчетов (норматив — только для скоринга тренажера).
const CARD_SLA_SEC = 75;
const INCIDENT_NO = 36812195;
const APPLICANT_STATUSES = ['очевидец', 'пострадавший', 'родственник', 'знакомый', 'ребенок', 'участник'];
const EXTERNAL_SYSTEM = 'Интеграция ВИС (мок)';
const OKRUGA = ['ЦАО', 'САО', 'СВАО', 'ВАО', 'ЮВАО', 'ЮАО', 'ЮЗАО', 'ЗАО', 'СЗАО', 'ЗелАО', 'ТАО', 'НАО'];
// Мок адресного поиска: источник влияет на поведение (ФИАС — службы вручную).
const ADDR_SUGGEST = [
  { label: 'Москва, Новая Басманная улица, 10с1', src: 'Яндекс.Карты', okrug: 'ЦАО', rayon: 'Басманный район', street: 'Новая Басманная улица', house: '10', corpus: '', stroenie: '1' },
  { label: 'Москва, Манежная площадь, 1, стр. 2', src: 'Яндекс.Организации', warn: 'организации иногда теряют дом — проверьте', okrug: 'ЦАО', rayon: 'Тверской район', street: 'Манежная площадь', house: '1', corpus: '', stroenie: '2' },
  { label: 'Москва, Тверская улица, 7 (ФИАС)', src: 'ФИАС', fias: true, okrug: 'ЦАО', rayon: 'Тверской район', street: 'Тверская улица', house: '7', corpus: '', stroenie: '' },
];
const SOCIAL_OBJECTS = [
  { name: 'Школа № 91', dist: 35 },
  { name: 'Станция метро "Александровский сад"', dist: 120 },
  { name: 'Больница № 1', dist: 400 },
];
const EMPTY_TAGS = { where: '', sign: '', access: '', detail: '', place: '', threat: '', violation: '', medical: '', evac: '', gas: '', tagDesc: '' };
const isNoAutoType = (t) => !!t && INFO_TYPES.includes(t.title);
// Автокапитализация ФИО побуквенно.
const capitalizeName = (s) => String(s ?? '').split(/(\s+|-)/).map((p) => (/^\s+$|^-$/.test(p) || !p ? p : p[0].toUpperCase() + p.slice(1))).join('');
// Автоопределение канала по префиксу (мок): 901/902→Теле2, 910-919→МТС, 920-929→Мегафон, 960-969→Билайн.
const autoChannel = (phone) => {
  const d = String(phone ?? '').replace(/\D/g, '');
  const p = d.startsWith('8') ? d.slice(1, 4) : d.startsWith('7') ? d.slice(1, 4) : d.slice(0, 3);
  const n = Number(p);
  if (n >= 901 && n <= 902) return 'Теле2';
  if (n >= 910 && n <= 919) return 'МТС';
  if (n >= 920 && n <= 929) return 'Мегафон';
  if (n >= 960 && n <= 969) return 'Билайн';
  return '';
};

function TagRow({ label, options, value, onPick }) {
  return (
    <div className="arm-tagrow">
      <div className="arm-taglabel">{label}</div>
      <div className="arm-tagopts">
        {options.map((o) => (
          <button key={o} type="button" className={`arm-tag ${value === o ? 'sel' : ''}`} onClick={() => onPick(value === o ? '' : o)}>{o}</button>
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
  const [types, setTypes] = useState(BUNDLED_TYPES);
  const [tagSets, setTagSets] = useState(BUNDLED_TAGS);
  const [selectedTypes, setSelectedTypes] = useState([]); // мультивыбор синими плашками
  const [refusal103, setRefusal103] = useState(false); // Отказ от реагирования (103)
  const [tags, setTags] = useState({ ...EMPTY_TAGS });
  const [formError, setFormError] = useState('');
  const [manualServices, setManualServices] = useState([]);
  const [excludedServices, setExcludedServices] = useState([]);
  const [visServices, setVisServices] = useState([]); // добавлены внешней системой (пометка ВИС)
  const [svcMenuOpen, setSvcMenuOpen] = useState(false);
  const [svcSearch, setSvcSearch] = useState('');
  // Адрес
  const [addrQuery, setAddrQuery] = useState('');
  const [addrSuggestOpen, setAddrSuggestOpen] = useState(false);
  const [addrSrc, setAddrSrc] = useState('');
  const [fiasWarn, setFiasWarn] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [coords, setCoords] = useState({ lat: '', lng: '' });
  const [mapRadius, setMapRadius] = useState(200);
  const [addr, setAddr] = useState({ country: 'Россия', subject: 'Москва', settlement: 'Москва', object: '', okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' });
  // Телефоны
  const [phones, setPhones] = useState({ aon: '', provided: '', onsite: '' });
  const [foreignNum, setForeignNum] = useState(false);
  const [channel, setChannel] = useState('');
  const [subscriberOpen, setSubscriberOpen] = useState(false);
  const [smsOpen, setSmsOpen] = useState(false);
  const [smsText, setSmsText] = useState('');
  const [recordsOpen, setRecordsOpen] = useState(false);
  // Заявитель
  const [applicant, setApplicant] = useState('');
  const [appStatus, setAppStatus] = useState('');
  const [foreignLang, setForeignLang] = useState(false);
  // Нет контакта / срыв + пострадавшие
  const [emptyModal, setEmptyModal] = useState(null); // 'nocontact' | 'break'
  const [victims, setVictims] = useState('Нет');
  const [victimsCount, setVictimsCount] = useState('');
  const [victimsModal, setVictimsModal] = useState(false);
  const [desc, setDesc] = useState('');
  const [toast, setToast] = useState(null);
  const [savedScenarioId, setSavedScenarioId] = useState(null);
  const [saved, setSaved] = useState(false); // после сохранения: lock ФИО/статуса, признак «Создана вручную»
  const [manualCreated] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveConfirm, setSaveConfirm] = useState(false);
  // Связи
  const [linksOpen, setLinksOpen] = useState(false);
  const [links, setLinks] = useState([]); // [{id, role}]
  const [linkCandidates] = useState([{ id: '36812180', by: 'тот же АОН' }, { id: '36812177', by: 'тот же адрес' }]);
  const [matchBy] = useState('АОН +7(9__) ___-__-__'); // мок кнопки «Совпадение»
  // Пост-карточка
  const [genLoading, setGenLoading] = useState(false);
  const applyGenerated = (card) => {
    if (!card) return;
    resetAll();
    // Тип: ищем в справочнике по точному названию, иначе собираем из payload.
    const found = (types || []).find((t) => t.title === card.what)
      || (card.what ? { title: card.what, groups: [card.incident_category || '101'], kind: card.incident_kind || 'generic' } : null);
    if (found) setSelectedTypes([found]);
    if (card.tags) setTags({ ...EMPTY_TAGS, ...card.tags });
    if (card.address_obj) setAddr((a) => ({ ...a, ...card.address_obj }));
    if (card.address) setAddrQuery(card.address);
    if (card.address_src) setAddrSrc(card.address_src);
    if (card.phones) setPhones({ aon: card.phones.aon || '', provided: card.phones.provided || '', onsite: card.phones.onsite || '' });
    if (card.channel) setChannel(card.channel);
    if (card.caller_name) setApplicant(card.caller_name);
    if (card.caller_status) setAppStatus(card.caller_status);
    if (card.victims && card.victims !== 'нет') { setVictims('Есть'); setVictimsCount(card.victims); }
    if (card.description) setDesc(card.description);
    if (Array.isArray(card.services) && card.services.length) setManualServices(card.services);
    setFormError('');
    setSavedScenarioId(null);
  };
  const handleGenerate = async () => {
    setGenLoading(true);
    setFormError('');
    try {
      const seed = Math.floor(Math.random() * 1e9);
      const res = await fetch(`/api/cards/generate?seed=${seed}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const card = await res.json();
      applyGenerated(card);
      setToast(`Сгенерировано обходом графа: «${card.what}» (seed ${seed}). Проверьте поля и нажмите «сохранить».`);
    } catch {
      setFormError('Генератор недоступен (бэкенд не отвечает).');
    } finally {
      setGenLoading(false);
    }
  };
  const [otrab, setOtrab] = useState([]);
  const [otrabDraft, setOtrabDraft] = useState({ service: '', where: '', phone: '', who: '', msg: '' });
  const [supplement, setSupplement] = useState(false);
  const [done, setDone] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [reminder, setReminder] = useState({ text: '', time: '' });
  const [histOpen, setHistOpen] = useState(null);
  // Телефония (мок): статус + входящий звонок
  const [telStatus, setTelStatus] = useState('доступен');
  const [incomingOpen, setIncomingOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/incident-types').then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))).then((data) => {
      if (!cancelled && Array.isArray(data.items) && data.items.length >= 51) setTypes(data.items);
    }).catch(() => {});
    fetch('/api/incident-tree?path=' + encodeURIComponent('101')).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))).then((data) => {
      if (!cancelled && data && data.tag_sets && Object.keys(data.tag_sets).length) setTagSets(data.tag_sets);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const startedAtRef = useRef(Date.now());
  const typeListRef = useRef(null);
  const svcMenuRef = useRef(null);
  const addrRef = useRef(null);
  const refs = { f1: useRef(null), f2: useRef(null), f3: useRef(null), ch: useRef(null), q: useRef(null), a: useRef(null), t: useRef(null), o: useRef(null), s: useRef(null) };
  useEffect(() => {
    const onDown = (e) => {
      if (typeListRef.current && !typeListRef.current.contains(e.target)) setListOpen(false);
      if (svcMenuRef.current && !svcMenuRef.current.contains(e.target)) setSvcMenuOpen(false);
      if (addrRef.current && !addrRef.current.contains(e.target)) setAddrSuggestOpen(false);
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
  // Горячие клавиши по инструкции: Alt+F1/F2/F3 — телефоны, Alt+K — канал, Alt+Q — заявитель,
  // Alt+A — адрес, Alt+T — что случилось, Alt+O — описание, Alt+S — сохранить, Insert — новая, Esc — закрыть.
  useEffect(() => {
    const onKey = (e) => {
      if (!e.altKey) {
        if (e.key === 'Insert') { e.preventDefault(); resetAll(); }
        if (e.key === 'Escape') { setListOpen(false); setSvcMenuOpen(false); setMapOpen(false); setSaveConfirm(false); setEmptyModal(null); }
        return;
      }
      const k = e.key.toLowerCase();
      const go = (r) => { e.preventDefault(); r?.current?.focus(); };
      if (e.key === 'F1') go(refs.f1);
      else if (e.key === 'F2') go(refs.f2);
      else if (e.key === 'F3') go(refs.f3);
      else if (k === 'к' || k === 'k') go(refs.ch);
      else if (k === 'й' || k === 'q') go(refs.q);
      else if (k === 'ф' || k === 'a') go(refs.a);
      else if (k === 'е' || k === 't') go(refs.t);
      else if (k === 'щ' || k === 'o') go(refs.o);
      else if (k === 'ы' || k === 's') { e.preventDefault(); setSaveConfirm(true); }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
  const elapsedSec = Math.floor((now - startedAtRef.current) / 1000);
  const overtime = elapsedSec > CARD_SLA_SEC;
  const mm = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
  const ss = String(elapsedSec % 60).padStart(2, '0');

  const selectedType = selectedTypes[0] ?? null;
  const group = selectedType ? selectedType.groups[0] : null;
  const isFire = selectedType ? selectedType.kind === 'fire101' : false;

  const autoServices = useMemo(() => {
    if (!selectedType || isNoAutoType(selectedType)) return [];
    if (fiasWarn) return []; // ФИАС: службы вручную
    const flat = Object.values(tags).filter(Boolean);
    let auto = autoServicesFor(selectedType.groups[0], flat);
    const hasViolation = tags.violation === 'Да' || tags.violation === 'Есть' || tags.violation === 'Есть правонарушение';
    if (hasViolation && !auto.includes(SVC_102)) auto = [...auto, SVC_102];
    if (tags.medical === 'Да' && !auto.includes(SVC_103)) auto = [...auto, SVC_103];
    if (tags.sign === SMELL_SIGN) auto = auto.filter((s) => s !== SVC_102 && s !== SVC_104);
    return [...new Set(auto)];
  }, [selectedType, tags, fiasWarn]);

  const services = useMemo(
    () => [...new Set([...autoServices.filter((s) => !excludedServices.includes(s)), ...manualServices.filter((s) => !excludedServices.includes(s))])],
    [autoServices, manualServices, excludedServices],
  );

  const vis = useMemo(
    () => visibleTagRows({ kind: selectedType?.kind, title: selectedType?.title, tags }),
    [selectedType, tags],
  );

  const filteredTypes = useMemo(() => searchTypes(types, query), [query, types]);
  useEffect(() => { // автоподбор при полном совпадении без дублей
    const exact = types.find((t) => t.title.toLowerCase() === query.trim().toLowerCase());
    if (exact && query.trim() && filteredTypes.length > 1) { /* подсказка остается списком */ }
  }, [query, types, filteredTypes.length]);

  const pickType = (t) => {
    if (selectedTypes.some((x) => x.title === t.title)) return;
    setSelectedTypes((p) => [...p, t]);
    setQuery(''); setListOpen(false); setFormError(''); setSavedScenarioId(null);
    if (selectedTypes.length === 0) { setTags({ ...EMPTY_TAGS }); setManualServices([]); setExcludedServices([]); }
  };
  const removeType = (title) => {
    setSelectedTypes((p) => {
      const next = p.filter((x) => x.title !== title);
      if (!next.length) { setTags({ ...EMPTY_TAGS }); setManualServices([]); setExcludedServices([]); }
      return next;
    });
  };
  const resetAll = () => {
    setSelectedTypes([]); setTags({ ...EMPTY_TAGS }); setManualServices([]); setExcludedServices([]);
    setQuery(''); setRefusal103(false); setVictims('Нет'); setVictimsCount(''); setDesc(''); setSaved(false); setOtrab([]);
    setApplicant(''); setAppStatus(''); setPhones({ aon: '', provided: '', onsite: '' }); setAddrQuery('');
    setAddr((a) => ({ ...a, okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' }));
    setFiasWarn(false); setAddrSrc('');
  };

  const setTag = (key, v) => {
    let next = { ...tags, [key]: v };
    if (key === 'where' && next.detail && !detailOptionsFor(v, tagSets).includes(next.detail)) next.detail = '';
    next = pruneHiddenTags(next, visibleTagRows({ kind: selectedType?.kind, title: selectedType?.title, tags: next }));
    setTags(next); setFormError('');
  };

  const validate = () => {
    if (!selectedTypes.length) return 'Выберите «Что случилось?» — поле обязательно.';
    if (isFire && !tags.where) return 'Укажите «Где» для происшествия 101.';
    if (isFire && !tags.sign) return 'Укажите признак: «Открытое пламя / Дым» или «Запах гари».';
    if (!applicant.trim()) return 'Заполните «ФИО заявителя».';
    if (!appStatus) return 'Выберите «Статус заявителя».';
    return '';
  };

  const addService = (s, viaVis = false) => {
    setExcludedServices((p) => p.filter((x) => x !== s));
    setManualServices((p) => (p.includes(s) ? p : [...p, s]));
    if (viaVis) setVisServices((p) => (p.includes(s) ? p : [...p, s]));
    setSvcMenuOpen(false); setSvcSearch('');
  };
  const removeService = (s) => {
    setManualServices((p) => p.filter((x) => x !== s));
    setExcludedServices((p) => (p.includes(s) ? p : [...p, s]));
  };

  const pickAddr = (s) => {
    setAddr((a) => ({ ...a, okrug: s.okrug, rayon: s.rayon, street: s.street, house: s.house, corpus: s.corpus, stroenie: s.stroenie }));
    setAddrQuery(s.label); setAddrSrc(s.src); setAddrSuggestOpen(false);
    setFiasWarn(!!s.fias); // ФИАС — службы вручную
  };
  const clearAddress = (onlyQuery) => {
    if (onlyQuery) { setAddrQuery(''); return; }
    setAddr((a) => ({ ...a, okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' }));
    setAddrQuery(''); setAddrSrc(''); setFiasWarn(false);
  };
  const applyCoords = () => {
    // Мок «Указать на карте»: координаты заполняют адрес.
    if (coords.lat && coords.lng) {
      setAddr((a) => ({ ...a, descr: `${a.descr ? a.descr + ' ' : ''}[${coords.lat}, ${coords.lng}]`.trim() }));
      const near = SOCIAL_OBJECTS[0];
      if (near.dist <= 50) setAddr((a) => ({ ...a, descr: `${a.descr} ${near.name}`.trim() }));
    }
    setMapOpen(false);
  };

  const doSave = async (asEmpty) => {
    const err = asEmpty ? '' : validate();
    if (err) { setFormError(err); return; }
    setSaving(true); setSavedScenarioId(null);
    const addrStr = [addr.subject, addr.okrug && `округ ${addr.okrug}`, addr.street && `ул. ${addr.street}`, addr.house && `д. ${addr.house}`].filter(Boolean).join(', ');
    const finalServices = asEmpty ? [] : [...services];
    const payload = {
      user_id: user?.id ?? null, what: selectedTypes.map((t) => t.title).join(' + ') || (asEmpty ? (emptyModal === 'break' ? '<Срыв связи>' : '<Нет контакта>') : ''),
      incident_category: group, incident_kind: selectedType?.kind, address: addrStr, address_obj: addr,
      address_src: addrSrc, phones, phone_foreign: foreignNum, channel, caller_name: applicant,
      caller_status: appStatus, caller_foreign_lang: foreignLang, external_system: EXTERNAL_SYSTEM,
      victims: victims === 'Есть' ? victimsCount || '1' : 'нет', refusal103, factors: Object.entries(tags).filter(([, v]) => v).map(([k, v]) => `${k}:${v}`),
      tags, services: finalServices, services_manual: manualServices.filter((s) => !excludedServices.includes(s)),
      services_vis: visServices, description: desc, elapsed_sec: elapsedSec, overtime, empty: asEmpty ? emptyModal : null, links,
    };
    try {
      const res = await fetch('/api/reports/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      let scenarioId = null;
      try {
        const pub = await fetch(`/api/reports/${data.report_id}/publish`, { method: 'POST' });
        if (pub.ok) scenarioId = (await pub.json()).scenario_id ?? null;
      } catch { /* карточка уже в БД */ }
      if (scenarioId) setSavedScenarioId(scenarioId);
      setSaved(true);
      setToast(`Сохранено в БД: карточка №${data.report_id}${scenarioId ? `, происшествие ${scenarioId}` : ''}, служб: ${finalServices.length}. Статус: ${asEmpty ? 'Завершена + Проверено' : 'зарегистрирована'}.`);
    } catch {
      console.log('[card112 save fallback]', payload);
      setSaved(true);
      setToast(`Бэкенд недоступен — локальное сохранение (мок): служб: ${finalServices.length}. При восстановлении сети карточка попадет в систему.`);
    } finally {
      setSaving(false); setSaveConfirm(false); setEmptyModal(null);
    }
  };

  const setA = (k) => (e) => setAddr({ ...addr, [k]: e.target.value });
  const setP = (k) => (e) => {
    const v = e.target.value;
    setPhones((p) => ({ ...p, [k]: v }));
    if (k === 'aon') { const ch = autoChannel(v); if (ch) setChannel(ch); }
  };
  const today = new Date().toLocaleDateString('ru-RU');
  const detailOptions = detailOptionsFor(tags.where, tagSets);
  const detailLabel = !tags.where || tags.where === 'Улица' ? 'Улица (пламя, дым)' : tags.where === 'Транспорт' ? 'Транспорт (пламя, дым)' : `${tags.where} (детализация)`;
  const signLabel = tags.where === 'Транспорт' ? 'Признак пожара (транспорт)' : 'Признак пожара (улица)';
  const addrFiltered = ADDR_SUGGEST.filter((s) => !addrQuery.trim() || s.label.toLowerCase().includes(addrQuery.trim().toLowerCase()));
  const svcFiltered = SERVICE_CATALOG.filter((s) => !services.includes(s) && (!svcSearch.trim() || s.toLowerCase().includes(svcSearch.trim().toLowerCase())));
  const descOver03 = desc.length > 100;

  return (
    <div className="app-shell">
      <AppHeader title="Карточка происшествия 112" showCreateButton={false} />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="dds-back">
            <Link to="/">← К списку происшествий</Link>
            <button type="button" className="btn-reset" onClick={resetAll} title="Insert — новая карточка">Новая карточка (Insert)</button>
            <button type="button" className="btn-reset" onClick={handleGenerate} disabled={genLoading} title="Сгенерировать карточку обходом графа (GET /api/cards/generate) и заполнить поля">{genLoading ? 'Генерация…' : '⚄ Сгенерировать'}</button>
            <button type="button" className="btn-reset" onClick={() => setIncomingOpen(true)} title="Мок входящего звонка">Входящий звонок</button>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
              <span title="Статус телефонии (мок). Недоступен проставляется при открытой карточке">☎ {telStatus}</span>
              <select value={telStatus} onChange={(e) => setTelStatus(e.target.value)} title="Переключить вручную">
                <option value="доступен">доступен</option>
                <option value="недоступен">недоступен</option>
                <option value="не подключен">не подключен</option>
                <option value="ошибка">ошибка</option>
              </select>
            </span>
          </div>

          <div className="arm-wrap">
            <div className="arm-titlebar">
              <span>Происшествие {INCIDENT_NO}</span>
              <span className="arm-titleinfo">Сохр. {today} · Опер., АРМ 2, УМЦ О п · {EXTERNAL_SYSTEM}</span>
              {manualCreated && <span className="arm-typechip" title="Признак из инструкции 2.0">Создана вручную</span>}
              {links.length > 0 && <span className="arm-typechip" title="Связанные карточки">🔗 {links.length}: {links.map((l) => `${l.id} (${l.role})`).join(', ')}</span>}
              <span className={`arm-timer ${overtime ? 'over' : ''}`}>{mm}:{ss}<small>минут секунд</small></span>
            </div>

            {/* Телефоны: АОН / предоставленный / на место + канал */}
            <div className="arm-phones">
              <div className="arm-phone arm-off">
                <span className="arm-tel-ico">📞</span>
                <div><b>Отключение</b>
                  <div className="arm-minibtns">
                    <button type="button" className="arm-minibtn" onClick={() => setRecordsOpen((v) => !v)}>записи звонков</button>
                    <button type="button" className="arm-minibtn" onClick={() => setSmsOpen((v) => !v)}>список SMS{smsText ? ' •' : ''}</button>
                  </div>
                </div>
              </div>
              {[
                ['АОН', 'aon', refs.f1, 'Alt+F1'],
                ['предоставленный', 'provided', refs.f2, 'Alt+F2'],
                ['телефон на место', 'onsite', refs.f3, 'Alt+F3'],
              ].map(([label, key, ref, hint]) => (
                <div className="arm-phone" key={key}>
                  <span className="arm-tel-ico">📞</span>
                  <div style={{ flex: 1 }}>
                    <small>{label} <span style={{ opacity: 0.6 }}>({hint})</span></small>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <input ref={ref} value={phones[key]} onChange={setP(key)} placeholder="+7 (__) __-__" style={{ border: 'none', borderBottom: '1px solid #1c7fb8', background: 'transparent', fontSize: 14, width: 150 }} />
                      <button type="button" className="arm-minibtn" title="Исходящий звонок (мок)" onClick={() => setToast(`Исходящий вызов на ${phones[key] || label} (мок).`)}>📞</button>
                      {key !== 'aon' && <button type="button" className="arm-minibtn" title="Скопировать АОН" onClick={() => setPhones((p) => ({ ...p, [key]: p.aon }))}>АОН</button>}
                      {key === 'aon' && <button type="button" className="arm-minibtn" title="Данные абонента (нов. 2.1)" onClick={() => setSubscriberOpen((v) => !v)}>👤</button>}
                      <button type="button" className="arm-minibtn" title="Отправить СМС (нов. 1.8)" onClick={() => setSmsOpen(true)}>💬</button>
                    </div>
                    {key === 'aon' && !phones.aon && <small style={{ color: '#777' }}>Без SIM карты — поле пустое (вариант по инструкции)</small>}
                  </div>
                </div>
              ))}
            </div>
            <div className="arm-appline" style={{ gap: 16 }}>
              <label>Канал связи (Alt+K)
                <input ref={refs.ch} list="channels" value={channel} onChange={(e) => setChannel(e.target.value)} placeholder="поиск по списку" style={{ minWidth: 140 }} />
                <datalist id="channels">{CHANNELS.map((c) => <option key={c} value={c} />)}</datalist>
              </label>
              <label style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <input type="checkbox" checked={foreignNum} onChange={(e) => setForeignNum(e.target.checked)} style={{ minWidth: 0 }} /> зарубежный номер (не +7)
              </label>
              {channel && <span className="arm-typechip">канал: {channel} {autoChannel(phones.aon) === channel ? '(авто)' : ''}</span>}
              {subscriberOpen && <span className="arm-typechip">Данные абонента: ФИО/ДР/адрес от оператора связи (мок)</span>}
              {recordsOpen && <span className="arm-typechip">Записей не найдено · плеер мм:сс · скачать (мок)</span>}
              {smsOpen && (
                <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input value={smsText} onChange={(e) => setSmsText(e.target.value)} placeholder="текст СМС заявителю" style={{ minWidth: 220 }} />
                  <button type="button" className="arm-minibtn" onClick={() => { setToast(smsText ? `СМС отправлено (мок): ${smsText}` : 'Введите текст СМС'); setSmsText(''); }}>Отправить</button>
                  <button type="button" className="arm-minibtn" onClick={() => setSmsOpen(false)}>История сообщений</button>
                </span>
              )}
            </div>

            {/* Заявитель + статусы + пострадавшие + нет контакта/срыв */}
            <div className="arm-appline">
              <label>Фамилия и имя заявителя (Alt+Q)
                <input ref={refs.q} value={applicant} disabled={saved && !supplement} onChange={(e) => setApplicant(capitalizeName(e.target.value))} placeholder="" />
              </label>
              <label>выберите статус
                <select value={appStatus} disabled={saved && !supplement} onChange={(e) => setAppStatus(e.target.value)}>
                  <option value="">—</option>
                  {APPLICANT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <label style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} title="Признак вызова на иностранном языке">
                <input type="checkbox" checked={foreignLang} onChange={(e) => setForeignLang(e.target.checked)} style={{ minWidth: 0 }} /> 🌐 иностранный язык
              </label>
              <span className="arm-typechip" title="Источник карточки">{EXTERNAL_SYSTEM}</span>
              <span style={{ display: 'flex', gap: 8, alignItems: 'center', marginLeft: 'auto' }}>
                <span>Пострадавшие:</span>
                <button type="button" className={`arm-appchip ${victims === 'Нет' ? 'sel' : ''}`} onClick={() => { setVictims('Нет'); setVictimsCount(''); }}>Нет</button>
                <button type="button" className={`arm-appchip ${victims === 'Есть' ? 'sel' : ''}`} onClick={() => setVictimsModal(true)}>Есть</button>
                {victims === 'Есть' && <b>{victimsCount || '1'}</b>}
                <button type="button" className="arm-appchip red" onClick={() => setEmptyModal('nocontact')}>нет контакта</button>
                <button type="button" className="arm-appchip red" onClick={() => setEmptyModal('break')}>срыв звонка</button>
              </span>
            </div>

            <div className="arm-cols">
              {/* СЛЕВА: адрес + описание */}
              <section className="arm-card">
                <div className="arm-cardhead">Адрес: <b>Москва</b> <span style={{ opacity: 0.6 }}>(Alt+A)</span></div>
                <div className="arm-searchwrap" ref={addrRef} style={{ marginBottom: 8 }}>
                  <input ref={refs.a} value={addrQuery} placeholder="единая адресная строка: введите адрес с домом" onChange={(e) => { setAddrQuery(e.target.value); setAddrSuggestOpen(true); }} onFocus={() => setAddrSuggestOpen(true)} style={{ fontSize: 14 }} />
                  {addrSuggestOpen && (
                    <div className="arm-typelist">
                      {addrFiltered.map((s) => (
                        <button key={s.label} type="button" onClick={() => pickAddr(s)}>
                          {s.label} <small>· {s.src}</small>{s.warn && <small style={{ color: '#a00' }}> · {s.warn}</small>}
                        </button>
                      ))}
                      {!addrFiltered.length && <span className="arm-empty">Ничего не найдено (попробуйте синоним или часть слова)</span>}
                    </div>
                  )}
                </div>
                {addrSrc && <div className="arm-hint">Источник: {addrSrc}{fiasWarn ? ' — службы добавьте вручную' : ''}</div>}
                <div className="arm-grid3">
                  <label>Страна:<input value={addr.country} onChange={setA('country')} /></label>
                  <label>Субъект:<input value={addr.subject} onChange={setA('subject')} /></label>
                  <label>Населенный пункт:<input value={addr.settlement} onChange={setA('settlement')} /></label>
                </div>
                <div className="arm-grid3">
                  <label>Объект:<input value={addr.object} onChange={setA('object')} /></label>
                  <label>Округ (поиск):<input list="okruga" value={addr.okrug} onChange={setA('okrug')} placeholder="начните ввод" /><datalist id="okruga">{OKRUGA.map((o) => <option key={o} value={o} />)}</datalist></label>
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
                <label className="arm-block">Описательный адрес:<textarea rows={2} value={addr.descr} onChange={setA('descr')} placeholder="заполняется в т.ч. соцобъектом в 50 м" /></label>
                <div className="arm-rowend" style={{ gap: 6 }}>
                  <button type="button" className="arm-minibtn" onClick={() => setMapOpen(true)}>📍 карта / указать на карте</button>
                  <button type="button" className="arm-minibtn" onClick={() => clearAddress(true)} title="Удаляет только поисковый запрос">очистить запрос</button>
                  <button type="button" className="arm-minibtn" onClick={() => clearAddress(false)}>очистить адрес</button>
                </div>

                <div className="arm-desc">
                  <div className="arm-deschead">Описание со слов заявителя (Alt+O){descOver03 && <span style={{ color: '#a00' }}> · в службу 03 уйдут первые 100 символов</span>}</div>
                  <textarea ref={refs.o} rows={6} maxLength={1999} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="введите" />
                  <div className="arm-counter">{desc.length} / 1999{descOver03 ? ` · 03: ${desc.slice(0, 100)}…` : ''}</div>
                </div>
              </section>

              {/* СПРАВА: что случилось */}
              <section className="arm-right">
                <div className="arm-card">
                  <div className="arm-linkhead">Введите тип происшествия <span className="arm-count">{types.length}</span> <span style={{ opacity: 0.6 }}>(Alt+T)</span></div>
                  <div className="arm-searchwrap" ref={typeListRef}>
                    <input ref={refs.t} className="arm-what" value={query} placeholder="что случилось? (поиск + синонимы: пожар, дтп, газ…)" onChange={(e) => { setQuery(e.target.value); setListOpen(true); }} onFocus={() => setListOpen(true)} />
                    {listOpen && (
                      <div className="arm-typelist">
                        {filteredTypes.map((t) => (
                          <button key={t.title} type="button" onClick={() => pickType(t)}>{t.title} <small>· {t.groups.join(',')}</small></button>
                        ))}
                        {!filteredTypes.length && <span className="arm-empty">Ничего не найдено — попробуйте синоним («пожар»→101, «авария»→ДТП)</span>}
                      </div>
                    )}
                  </div>
                  {selectedTypes.length > 0 && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                      {selectedTypes.map((t) => (
                        <button key={t.title} type="button" className="arm-tag sel" title="Нажмите, чтобы отменить выбор" onClick={() => removeType(t.title)}>
                          {t.title} ×
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="arm-quick">
                    {QUICK_TYPES.map((q) => {
                      const found = types.find((t) => t.title.toLowerCase() === q.toLowerCase());
                      return <button key={q} type="button" className="arm-tag" onClick={() => found && pickType(found)}>{q}</button>;
                    })}
                  </div>
                  <div className="arm-signif">Значимые типы происшествий:</div>
                  <div className="arm-quick">
                    {SIGNIFICANT_TYPES.map((q) => {
                      const found = types.find((t) => t.title === q);
                      return <button key={q} type="button" className="arm-tag" onClick={() => found && pickType(found)}>{q}</button>;
                    })}
                  </div>
                  <div className="arm-hint">Строка «добавить тип происшествия»: введите выше и выберите — типы комбинируются. Совпадение кнопки «Совпадение»: {matchBy}.</div>
                  {group === '103' && (
                    <label style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 8 }}>
                      <input type="checkbox" checked={refusal103} onChange={(e) => setRefusal103(e.target.checked)} /> Отказ от реагирования (103)
                    </label>
                  )}
                  {selectedType && (
                    <>
                      <div className="arm-typechip">Происшествие {group} · {selectedType.kind === 'fire101' ? 'ветка 101' : 'общая ветка'}</div>
                      <div className="arm-blackhead" title="Справочная система: сплошное подчеркивание — страница создана">Происшествие {group} <span onClick={() => removeType(selectedType.title)}>×</span></div>
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
                            {vis.length === 0 && <div className="arm-hint">Информационный тип без выезда: только описание, службы не подбираются.</div>}
                            {vis.length > 0 && <div className="arm-hint">Общая ветка ({group}): полный каскад 101 не применяется.</div>}
                          </>
                        )}
                      </div>
                    </>
                  )}
                  {formError && <div className="arm-err">{formError}</div>}
                </div>
              </section>
            </div>

            {/* ВНИЗУ: полоса служб */}
            <div className="arm-services">
              <span className="arm-svclabel">Службы:{fiasWarn ? ' (ФИАС — вручную)' : ''}</span>
              <div className="arm-svcchips">
                {services.map((s) => (
                  <span key={s} className={`arm-svc ${isMainService(group, s) ? 'main' : ''}`} title={`${s}${isMainService(group, s) ? ' — основная (двойное подчеркивание)' : ''}${visServices.includes(s) ? ' · добавлена ВИС' : ''}`}>
                    <span className="arm-svctel">📞</span>
                    <span className="arm-svcname">{serviceShortName(s)}{visServices.includes(s) ? ' [ВИС]' : ''}</span>
                    <button type="button" className="arm-histbtn" title="История статусов" onClick={() => setHistOpen(s)}>▴</button>
                    <button type="button" onClick={() => removeService(s)} title="убрать">×</button>
                    {histOpen === s && (
                      <span className="arm-histpop">Добавлена · Получена службой · <button type="button" className="arm-minibtn" onClick={() => setHistOpen(null)}>закрыть</button></span>
                    )}
                  </span>
                ))}
                <div className="arm-svcadd" ref={svcMenuRef}>
                  <button type="button" className="arm-plus" onClick={() => setSvcMenuOpen((v) => !v)} title="Добавить службу">+</button>
                  {svcMenuOpen && (
                    <div className="arm-svcmenu" style={{ minWidth: 300 }}>
                      <div style={{ padding: 8, position: 'sticky', top: 0, background: '#fff' }}>
                        <input value={svcSearch} onChange={(e) => setSvcSearch(e.target.value)} placeholder="Поиск ..." style={{ width: '100%' }} />
                      </div>
                      {svcFiltered.slice(0, 60).map((s) => (
                        <button key={s} type="button" onClick={() => addService(s)} title={autoServices.includes(s) ? 'авто (синяя)' : 'вручную (серая)'}
                          style={autoServices.includes(s) ? { background: '#1c7fb8', color: '#fff' } : {}}>
                          {s}
                        </button>
                      ))}
                      {!svcFiltered.length && <span className="arm-empty">Ничего не найдено</span>}
                      <div style={{ display: 'flex', gap: 8, padding: 8 }}>
                        <button type="button" className="arm-minibtn" onClick={() => setSvcMenuOpen(false)}>Сохранить и закрыть</button>
                        <button type="button" className="arm-minibtn" onClick={() => { const s = SERVICE_CATALOG.find((x) => !services.includes(x)); if (s) addService(s, true); }} title="Мок: служба от внешней системы">+ ВИС</button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <div className="arm-actions">
                <button ref={refs.s} type="button" className="arm-save" onClick={() => setSaveConfirm(true)} disabled={saving} title="Alt+S">{saving ? 'сохранение…' : 'сохранить'}</button>
                <button type="button" className="arm-icobtn" title="Связи / Совпадение" onClick={() => setLinksOpen(true)}>🔗</button>
                <button type="button" className="arm-icobtn" title="Напоминание-будильник" onClick={() => setReminderOpen(true)}>🔔</button>
                <button type="button" className="arm-icobtn" title="Важное происшествие" onClick={() => setToast('Главному специалисту отправлен сигнал: АРМ 2, требуется консультация (мок).')}>✋</button>
                <button type="button" className="arm-icobtn" title="Сообщить о проблеме" onClick={() => setToast('Сообщение в техподдержку отправлено (мок, можно приложить скриншот).')}>💬</button>
                <button type="button" className="arm-icobtn" title="Закрыть (Esc)">×</button>
              </div>
            </div>
            {overtime && <div className="arm-overhint">Время набора карточки превышено (ориентир тренажера {CARD_SLA_SEC} сек) — учитывается в скоринге.</div>}

            {/* Пост-карточка: отработки, записи, дополнить/отработана */}
            {saved && (
              <div className="arm-card" style={{ marginTop: 6 }}>
                <div className="arm-cardhead">Отработки происшествия · Записи разговоров (мм:сс, скачать — мок) · {done ? 'Отработана' : 'в работе'}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  <button type="button" className="arm-minibtn" onClick={() => setSupplement((v) => !v)}>{supplement ? 'закрыть дополнение' : 'дополнить (пустые поля + описание)'} · просмотр</button>
                  <button type="button" className="arm-minibtn" onClick={() => { setDone(true); setToast('Карточка отмечена «Отработана».'); }}>Отработана</button>
                  <button type="button" className="arm-minibtn" onClick={() => setToast('Окно «Напоминание» появится при закрытой карточке каждые 20 сек (мок).')}>проверить напоминание</button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, marginBottom: 8 }}>
                  {[
                    ['Служба', 'service', 'выбор из списка'],
                    ['Куда звонили', 'where', 'если службы нет в списке'],
                    ['Телефон', 'phone', 'авто или вручную'],
                    ['Кто принял', 'who', 'фамилия/номер диспетчера'],
                    ['Суть сообщения', 'msg', 'итог дозвона'],
                  ].map(([label, key, ph]) => (
                    <label key={key} style={{ display: 'flex', flexDirection: 'column', fontSize: 11, color: '#555' }}>{label}:
                      <input value={otrabDraft[key]} onChange={(e) => setOtrabDraft({ ...otrabDraft, [key]: e.target.value })} placeholder={ph} />
                    </label>
                  ))}
                </div>
                <button type="button" className="arm-minibtn" disabled={!Object.values(otrabDraft).some((v) => v.trim())}
                  onClick={() => { setOtrab((p) => [...p, { ...otrabDraft, id: Date.now() }]); setOtrabDraft({ service: '', where: '', phone: '', who: '', msg: '' }); }}>
                  ✓ сохранить отработку (Enter)
                </button>
                {otrab.map((o) => (
                  <div key={o.id} className="arm-hint">{o.service || o.where} · {o.phone} · {o.who} · {o.msg} · <button type="button" className="arm-minibtn" onClick={() => setToast(`Исходящий вызов в службу ${o.phone || ''} (мок).`)}>📞</button></div>
                ))}
              </div>
            )}
          </div>

          {toast && (
            <div className="toast" role="status">{toast}{' '}
              {savedScenarioId && <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate(`/scenario/${savedScenarioId}`)}>Открыть в тренажёре →</button>}
              <button type="button" className="toast-close" onClick={() => setToast(null)}>×</button>
            </div>
          )}
        </main>
      </div>

      {/* Модалка карты (мок) */}
      {mapOpen && (
        <div className="arm-modal" role="dialog" aria-label="Карта">
          <div className="arm-modal-box" style={{ maxWidth: 560 }}>
            <b>Карта места происшествия (мок, масштаб 1:50)</b>
            <div style={{ display: 'flex', gap: 8, margin: '8px 0' }}>
              <input value={coords.lat} onChange={(e) => setCoords({ ...coords, lat: e.target.value })} placeholder="Широта" />
              <input value={coords.lng} onChange={(e) => setCoords({ ...coords, lng: e.target.value })} placeholder="Долгота" />
              <button type="button" className="arm-minibtn" onClick={() => setCoords({ lat: '55,752445', lng: '37,598124' })}>Указать на карте (мок)</button>
              <label>Радиус: <select value={mapRadius} onChange={(e) => setMapRadius(Number(e.target.value))}><option value={50}>50 м</option><option value={200}>200 м</option><option value={1000}>1000 м</option></select></label>
            </div>
            <div className="arm-hint">Слои: Камеры / Техника / Объекты. Соцобъекты в радиусе {mapRadius} м:</div>
            {SOCIAL_OBJECTS.filter((o) => o.dist <= mapRadius).map((o) => (
              <div key={o.name} className="arm-hint">{o.name} — {o.dist} м{o.dist <= 50 ? ' → попадет в Описательный адрес' : ''}</div>
            ))}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button type="button" className="arm-minibtn" onClick={applyCoords}>ОК</button>
              <button type="button" className="arm-minibtn" onClick={() => setMapOpen(false)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {/* Нет контакта / срыв */}
      {emptyModal && (
        <div className="arm-modal" role="dialog">
          <div className="arm-modal-box">
            <b>{emptyModal === 'break' ? 'Срыв звонка' : 'Нет контакта'} — карточка станет «Завершена + Проверено»</b>
            <div className="arm-hint">Сохранить как пустую или вернуться к заполнению (если кнопка нажата по ошибке).</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button type="button" className="arm-minibtn" onClick={() => doSave(true)}>Сохранить пустую</button>
              <button type="button" className="arm-minibtn" onClick={() => setEmptyModal(null)}>Вернуться к заполнению</button>
            </div>
          </div>
        </div>
      )}

      {/* Пострадавшие */}
      {victimsModal && (
        <div className="arm-modal" role="dialog">
          <div className="arm-modal-box">
            <b>Количество пострадавших</b>
            <input value={victimsCount} onChange={(e) => setVictimsCount(e.target.value.replace(/\D/g, ''))} placeholder="введите число" style={{ width: '100%', marginTop: 8 }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button type="button" className="arm-minibtn" onClick={() => { setVictims('Есть'); if (!victimsCount) setVictimsCount('1'); setVictimsModal(false); }}>ОК</button>
              <button type="button" className="arm-minibtn" onClick={() => setVictimsModal(false)}>Отмена</button>
            </div>
          </div>
        </div>
      )}

      {/* Сохранение */}
      {saveConfirm && (
        <div className="arm-modal" role="dialog">
          <div className="arm-modal-box">
            <b>Сохранение карточки и оповещение служб</b>
            <div className="arm-hint">Проверьте список служб внизу. Основные подчеркнуты двойной линией, добавленные ВИС — с пометкой.</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button type="button" className="arm-save" style={{ borderColor: '#1c7fb8', color: '#1c7fb8' }} onClick={() => doSave(false)} disabled={saving}>Оповестить и сохранить карточку</button>
              <button type="button" className="arm-minibtn" onClick={() => setSaveConfirm(false)}>Вернуться к заполнению</button>
            </div>
            {formError && <div className="arm-err">{formError}</div>}
          </div>
        </div>
      )}

      {/* Связи */}
      {linksOpen && (
        <div className="arm-modal" role="dialog">
          <div className="arm-modal-box" style={{ maxWidth: 520 }}>
            <b>Совпадение и связи (мок)</b>
            <div className="arm-hint">Кнопка «Совпадение» показана по: {matchBy}. Связь считается установленной после сохранения.</div>
            {linkCandidates.map((c) => (
              <div key={c.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
                <span>Карточка {c.id} ({c.by})</span>
                <button type="button" className="arm-minibtn" onClick={() => setLinks((p) => (p.some((l) => l.id === c.id) ? p : [...p, { id: c.id, role: p.length ? 'подчиненная' : 'главная' }]))}>Привязать</button>
              </div>
            ))}
            {links.map((l) => (
              <div key={l.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
                <span>{l.id} — {l.role}</span>
                <button type="button" className="arm-minibtn" onClick={() => setLinks((p) => p.map((x) => x.id === l.id ? { ...x, role: x.role === 'главная' ? 'подчиненная' : 'главная' } : x))}>сделать {l.role === 'главная' ? 'подчиненной' : 'главной'}</button>
                <button type="button" className="arm-minibtn" onClick={() => setLinks((p) => p.filter((x) => x.id !== l.id))}>отвязать</button>
              </div>
            ))}
            <div style={{ marginTop: 8 }}><button type="button" className="arm-minibtn" onClick={() => setLinksOpen(false)}>Закрыть</button></div>
          </div>
        </div>
      )}

      {/* Напоминание */}
      {reminderOpen && (
        <div className="arm-modal" role="dialog">
          <div className="arm-modal-box">
            <b>Установить напоминание (будильник)</b>
            <input value={reminder.text} onChange={(e) => setReminder({ ...reminder, text: e.target.value })} placeholder="текст" style={{ width: '100%', marginTop: 8 }} />
            <input value={reminder.time} onChange={(e) => setReminder({ ...reminder, time: e.target.value })} placeholder="время" style={{ width: '100%', marginTop: 8 }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button type="button" className="arm-minibtn" onClick={() => { setReminderOpen(false); setToast('Напоминание сохранено (мок). При закрытой карточке будет появляться каждые 20 сек.'); }}>Сохранить</button>
              <button type="button" className="arm-minibtn" onClick={() => setReminderOpen(false)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {/* Входящий звонок (мок телефонии Avaya) */}
      {incomingOpen && (
        <div className="arm-modal" role="dialog">
          <div className="arm-modal-box">
            <b>Входящий вызов (мок)</b>
            <div className="arm-hint">Окно с информацией о вызове и единственной кнопкой «Принять». После принятия откроется новая карточка.</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button type="button" className="arm-save" style={{ borderColor: '#27ae60', color: '#27ae60' }} onClick={() => { setIncomingOpen(false); setTelStatus('недоступен'); resetAll(); setToast('Вызов принят. Открыта новая карточка, статус — «недоступен» (мок).'); }}>Принять</button>
              <button type="button" className="arm-minibtn" onClick={() => setIncomingOpen(false)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
