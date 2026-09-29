import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import {
  CHANNELS,
  FLAG_DEFS,
  EMPTY_FLAGS,
  MAIN_SVC_GROUP,
  CASCADE_LEVELS,
  CASCADE_LABELS,
  searchLeaves,
  leafFactors,
  walkCascadeTree,
  cascadePathForLeaf,
} from '../lib/incidentClassifier';
import { INFO_TYPES } from '../lib/tagVisibility';
import { SERVICE_CATALOG, SVC_103, serviceShortName, isMainService } from '../lib/serviceCatalog';

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
const isInfoTitle = (t) => !!t && INFO_TYPES.includes(t);
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

export default function Card112() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [listOpen, setListOpen] = useState(false);
  const [leaves, setLeaves] = useState([]); // индекс классификатора (/api/classifier/leaves)
  const [tree, setTree] = useState(null); // дерево каскада (/api/classifier/tree)
  const [cascadePath, setCascadePath] = useState([]); // [{level,value,g?}] ручное ветвление
  const [selectedLeaf, setSelectedLeaf] = useState(null); // {code,result,path,group,section,main}
  const [infoType, setInfoType] = useState(''); // инфо-тип без выезда (вне классификатора)
  const [flags, setFlags] = useState({ ...EMPTY_FLAGS }); // флаги ТЭГов классификатора
  const [tagDesc, setTagDesc] = useState(''); // уточнение ТЭГа
  const [autoServices, setAutoServices] = useState([]); // диспетчеризация листа
  const [autoInformed, setAutoInformed] = useState([]); // уведомляемые (синие плашки)
  const [refusal103, setRefusal103] = useState(false); // Отказ от реагирования (103)
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
  const [otrab, setOtrab] = useState([]);
  const [otrabDraft, setOtrabDraft] = useState({ service: '', where: '', phone: '', who: '', msg: '' });
  const [supplement, setSupplement] = useState(false);
  const [done, setDone] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [reminder, setReminder] = useState({ text: '', time: '' });
  // Телефония (мок): статус + входящий звонок
  const [telStatus, setTelStatus] = useState('доступен');
  const [incomingOpen, setIncomingOpen] = useState(false);
  // Генератор карточек (бэкенд /api/scenarios/generate): seed + загрузка
  const [genSeed, setGenSeed] = useState('');
  const [genLoading, setGenLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // Индекс классификатора для выбора типа (Итоговый тип + путь признаков).
    fetch('/api/classifier/leaves?limit=2000').then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))).then((data) => {
      if (!cancelled && Array.isArray(data.items) && data.items.length) setLeaves(data.items);
    }).catch(() => {});
    // Дерево каскада «Что случилось?»: раздел -> Место -> Что -> Проявление.
    fetch('/api/classifier/tree').then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))).then((data) => {
      if (!cancelled && data && Array.isArray(data.roots) && data.roots.length) setTree(data);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Диспетчеризация выбранного листа по флагам (бэкенд считает по xlsx).
  useEffect(() => {
    let cancelled = false;
    if (!selectedLeaf || fiasWarn) { setAutoServices([]); setAutoInformed([]); return () => { cancelled = true; }; }
    const params = new URLSearchParams({ code: selectedLeaf.code });
    if (flags.no_access) params.set('nd', 'true');
    if (flags.threat) { params.set('threat', 'true'); params.set('ul', 'true'); }
    if (flags.violation) params.set('violation', 'true');
    if (flags.medical) params.set('medical', 'true');
    if (flags.evac) params.set('evac', 'true');
    if (flags.gas) params.set('gas', 'true');
    if (victims !== 'Нет') { params.set('victims', 'true'); params.set('pp', 'true'); }
    fetch(`/api/classifier/dispatch?${params}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))).then((data) => {
      if (cancelled) return;
      if (Array.isArray(data.services)) {
        setAutoServices(data.services);
        // Накопление: уже добавленные службы не сбрасываются при прокликивании флагов.
        setManualServices((prev) => [...new Set([...prev, ...data.services])]);
      }
      if (Array.isArray(data.informed)) setAutoInformed(data.informed);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedLeaf, flags, victims, fiasWarn]);

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

  const svcGroup = selectedLeaf ? (MAIN_SVC_GROUP[selectedLeaf.main] ?? '') : '';

  const services = useMemo(
    () => [...new Set([...autoServices.filter((s) => !excludedServices.includes(s)), ...manualServices.filter((s) => !excludedServices.includes(s))])],
    [autoServices, manualServices, excludedServices],
  );

  // Уведомляемые службы — синие плашки (голубой = уведомлены, не выезд).
  const informed = useMemo(
    () => [...new Set(autoInformed.filter((s) => !excludedServices.includes(s) && !services.includes(s)))],
    [autoInformed, excludedServices, services],
  );

  const filteredLeaves = useMemo(() => searchLeaves(leaves, query), [query, leaves]);
  // Инфо-типы без выезда в поиске (ряды плашек удалены).
  const filteredInfo = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return INFO_TYPES.filter((t) => t.toLowerCase().includes(q));
  }, [query]);

  // Текущий шаг каскада: все кнопки узла разом + выбираемые листья.
  const cascade = useMemo(() => walkCascadeTree(tree, cascadePath), [tree, cascadePath]);
  // Отвеченные уровни с реальным выбором (одиночные безвариантные — скрыты).
  const cascadeAnswered = useMemo(() => cascade.breadcrumb.map((b, i) => ({ b, i })).filter(({ i }) => {
    if (i >= cascadePath.length - 1) return false;
    const parent = walkCascadeTree(tree, cascadePath.slice(0, i));
    return parent.buttons.length !== 1 || parent.selectable.length > 0;
  }), [tree, cascade, cascadePath]);
  // Хвост автопройденных уровней (без развилки) — показать контекстом в активной плашке.
  const cascadeSkipped = useMemo(() => {
    const vals = [];
    for (let j = cascadePath.length - 1; j >= 0; j--) {
      const parent = walkCascadeTree(tree, cascadePath.slice(0, j));
      if (parent.buttons.length === 1 && !parent.selectable.length) vals.unshift(cascadePath[j].value);
      else break;
    }
    return vals;
  }, [tree, cascadePath]);
  // Вопрос активной плашки — следующий уровень (не последний отвеченный).
  const cascadeQuestion = CASCADE_LABELS[CASCADE_LEVELS[cascade.breadcrumb.length]] ?? 'Что случилось';
  const leafTitle = (code) => leaves.find((l) => String(l.code) === String(code))?.result || `№${code}`;
  const pickLeafByCode = (code) => {
    const found = leaves.find((l) => String(l.code) === String(code));
    if (found) pickLeaf(found);
  };
  const pushCascade = (b) => {
    let nextPath;
    if (b.g != null) {
      // Кнопка раздела — начать ветвление заново: раздел в поле, список скрыть.
      const root = (tree?.roots ?? []).find((r) => r.g === b.g);
      if (!root) return;
      nextPath = [{ level: 'section', value: root.title, g: root.g }];
      setQuery(root.title);
      setListOpen(false);
    } else if (!cascadePath.length) {
      return;
    } else {
      const next = CASCADE_LEVELS[cascadePath.length];
      if (!next) return;
      nextPath = [...cascadePath, { level: next, value: b.value }];
    }
    // Лист без разветвления — отобразить/выбрать сразу, иначе — до разветвления.
    // Линейный участок (единственная кнопка, без вариантов) — проскочить
    // автоматически до развилки.
    let path = nextPath;
    for (;;) {
      const step = walkCascadeTree(tree, path);
      if (step.buttons.length === 1 && !step.selectable.length) {
        const next = CASCADE_LEVELS[path.length];
        if (!next) break;
        path = [...path, { level: next, value: step.buttons[0].value }];
        continue;
      }
      break;
    }
    const final = walkCascadeTree(tree, path);
    if (!final.buttons.length && final.selectable.length === 1) {
      pickLeafByCode(final.selectable[0]);
    } else {
      setCascadePath(path);
    }
  };

  const pickLeaf = (leaf) => {
    setSelectedLeaf(leaf); setInfoType('');
    setCascadePath(cascadePathForLeaf(leaf));
    setQuery(leaf.section?.title || ''); setListOpen(false); setFormError(''); setSavedScenarioId(null);
    setFlags({ ...EMPTY_FLAGS }); setManualServices([]); setExcludedServices([]);
  };
  const pickInfo = (title) => {
    setInfoType(title); setSelectedLeaf(null); setAutoServices([]); setAutoInformed([]);
    setQuery(''); setListOpen(false); setFormError(''); setSavedScenarioId(null);
    setFlags({ ...EMPTY_FLAGS }); setManualServices([]); setExcludedServices([]);
  };
  const clearIncident = () => {
    setSelectedLeaf(null); setInfoType(''); setCascadePath([]); setQuery('');
    setFlags({ ...EMPTY_FLAGS }); setTagDesc(''); setManualServices([]); setExcludedServices([]); setAutoServices([]); setAutoInformed([]);
  };
  const resetAll = () => {
    clearIncident();
    setQuery(''); setRefusal103(false); setVictims('Нет'); setVictimsCount(''); setDesc(''); setSaved(false); setOtrab([]);
    setApplicant(''); setAppStatus(''); setPhones({ aon: '', provided: '', onsite: '' }); setAddrQuery('');
    setAddr((a) => ({ ...a, okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' }));
    setFiasWarn(false); setAddrSrc('');
  };

  // Разом заполнить карточку из генератора: GET /api/scenarios/generate
  // возвращает payload формата reports/create — раскладываем по состоянию формы.
  const applyGenerated = (item) => {
    const p = item.payload;
    resetAll();
    if (p.classifier_code && leaves.length) {
      const found = leaves.find((l) => String(l.code) === String(p.classifier_code));
      if (found) { setSelectedLeaf(found); setCascadePath(cascadePathForLeaf(found)); setQuery(found.section?.title || ''); }
      else { setQuery(p.what || ''); setManualServices(p.services || []); }
    } else if (p.what && isInfoTitle(p.what)) {
      setInfoType(p.what);
    } else {
      setQuery(p.what || '');
    }
    const pt = p.tags || {};
    setFlags({
      no_access: !!pt.no_access, threat: !!pt.threat, violation: !!pt.violation,
      medical: !!pt.medical, evac: !!pt.evac, gas: !!pt.gas,
    });
    setTagDesc(pt.tagDesc || '');
    // Службы генератора — как ручные: диспетчеризация листа их и так подтянет.
    setManualServices([]);
    setExcludedServices([]);
    if (p.address_obj) setAddr((a) => ({ ...a, ...p.address_obj }));
    setAddrQuery(p.address || '');
    setAddrSrc(p.address_src || '');
    setFiasWarn(p.address_src === 'ФИАС');
    setPhones({ aon: p.phones?.aon || '', provided: '', onsite: '' });
    if (p.channel) setChannel(p.channel);
    else if (p.phones?.aon) { const ch = autoChannel(p.phones.aon); if (ch) setChannel(ch); }
    setForeignNum(!!p.phone_foreign);
    setApplicant(p.caller_name || '');
    setAppStatus(p.caller_status || '');
    setForeignLang(!!p.caller_foreign_lang);
    if (p.victims && p.victims !== 'нет') { setVictims('Есть'); setVictimsCount(String(p.victims)); }
    setDesc(p.description || '');
    setSaved(false); setSavedScenarioId(null); setFormError('');
  };

  const fillFromGenerator = async () => {
    setGenLoading(true);
    try {
      const seed = genSeed.trim() === '' ? Math.floor(Math.random() * 2147483647) : Number(genSeed);
      const res = await fetch(`/api/scenarios/generate?seed=${seed}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const item = data.cards?.[0];
      if (!item) throw new Error('пустой ответ');
      applyGenerated(item);
      setGenSeed(String(data.seed));
      setToast(`Сгенерирована карточка (seed ${data.seed}): ${item.payload.what}. Проверьте и сохраните.`);
    } catch (e) {
      setToast(`Генератор недоступен: ${e.message}`);
    } finally {
      setGenLoading(false);
    }
  };

  const setFlag = (key, v) => {
    setFlags((f) => ({ ...f, [key]: v })); setFormError('');
  };

  const validate = () => {
    if (!selectedLeaf && !infoType) return 'Выберите «Что случилось?» — поле обязательно.';
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
    const finalInformed = asEmpty ? [] : [...informed];
    const leafPath = selectedLeaf ? (selectedLeaf.path || []) : [];
    const tags = {
      attr1: leafPath[0] || '', attr2: leafPath[1] || '', attr3: leafPath[2] || '',
      ...flags, tagDesc,
    };
    const payload = {
      user_id: user?.id ?? null,
      what: (selectedLeaf ? selectedLeaf.result : infoType) || (asEmpty ? (emptyModal === 'break' ? '<Срыв связи>' : '<Нет контакта>') : ''),
      classifier_code: selectedLeaf ? selectedLeaf.code : null,
      classifier_path: leafPath,
      classifier_section: selectedLeaf ? selectedLeaf.section : null,
      incident_category: selectedLeaf ? (selectedLeaf.group || '') : '',
      main_service: selectedLeaf ? (selectedLeaf.main || null) : null,
      address: addrStr, address_obj: addr,
      address_src: addrSrc, phones, phone_foreign: foreignNum, channel, caller_name: applicant,
      caller_status: appStatus, caller_foreign_lang: foreignLang, external_system: EXTERNAL_SYSTEM,
      victims: victims === 'Есть' ? victimsCount || '1' : 'нет', refusal103,
      factors: selectedLeaf ? leafFactors(selectedLeaf, flags, tagDesc) : (tagDesc ? [tagDesc] : []),
      tags, services: finalServices, services_informed: finalInformed, services_manual: manualServices.filter((s) => !excludedServices.includes(s)),
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
  const addrFiltered = ADDR_SUGGEST.filter((s) => !addrQuery.trim() || s.label.toLowerCase().includes(addrQuery.trim().toLowerCase()));
  const svcFiltered = SERVICE_CATALOG.filter((s) => !services.includes(s) && (!svcSearch.trim() || s.toLowerCase().includes(svcSearch.trim().toLowerCase())));
  const descOver03 = desc.length > 100;

  return (
    <div className="app-shell">
      <AppHeader
        title="Карточка происшествия 112"
        showCreateButton={false}
        actions={(
          <>
            <Link to="/" className="arm-topbtn">← К списку происшествий</Link>
            <button type="button" className="arm-topbtn" onClick={resetAll} title="Insert — новая карточка">Новая карточка (Insert)</button>
            <button type="button" className="arm-topbtn" onClick={() => setIncomingOpen(true)} title="Мок входящего звонка">Входящий звонок</button>
            <button type="button" className="arm-topbtn primary" onClick={fillFromGenerator} disabled={genLoading} title="Заполнить карточку из генератора (случайный обход графа, seed можно задать вручную)">🎲 {genLoading ? 'генерация…' : 'Сгенерировать'}</button>
            <input className="arm-topseed" value={genSeed} onChange={(e) => setGenSeed(e.target.value)} placeholder="seed" title="Seed генератора (пусто — случайно)" />
          </>
        )}
      />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="arm-topbar">
            <span className="arm-topmeta">Происшествие {INCIDENT_NO} · {today} · Опер., АРМ 2, УМЦ О п · {EXTERNAL_SYSTEM}</span>
            {manualCreated && <span className="arm-typechip" title="Признак из инструкции 2.0">Создана вручную</span>}
            {links.length > 0 && <span className="arm-typechip" title="Связанные карточки">🔗 {links.length}: {links.map((l) => `${l.id} (${l.role})`).join(', ')}</span>}
            <span className="arm-topright">
              <span title="Статус телефонии (мок). Недоступен проставляется при открытой карточке">☎ {telStatus}</span>
              <select value={telStatus} onChange={(e) => setTelStatus(e.target.value)} title="Переключить вручную">
                <option value="доступен">доступен</option>
                <option value="недоступен">недоступен</option>
                <option value="не подключен">не подключен</option>
                <option value="ошибка">ошибка</option>
              </select>
              <span className={`arm-timer ${overtime ? 'over' : ''}`}>{mm}:{ss}<small>минут секунд</small></span>
            </span>
          </div>

          <div className="arm-wrap">
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
                  <div className="arm-linkhead">Введите тип происшествия <span className="arm-count">{leaves.length}</span> <span style={{ opacity: 0.6 }}>(Alt+T, классификатор)</span></div>
                  <div className="arm-searchwrap" ref={typeListRef}>
                    <input ref={refs.t} className="arm-what" value={query} placeholder="что случилось? (поиск по классификатору: мусор, дтп, взрыв…)" onChange={(e) => { setQuery(e.target.value); setListOpen(true); }} onFocus={() => setListOpen(true)} />
                    {listOpen && (
                      <div className="arm-typelist">
                        {query.trim() ? (
                          <>
                            {filteredInfo.map((t) => (
                              <button key={`info-${t}`} type="button" onClick={() => pickInfo(t)}>{t} <small>· без выезда</small></button>
                            ))}
                            {filteredLeaves.map((l) => (
                              <button key={l.code} type="button" onClick={() => pickLeaf(l)}>{l.result} <small>· {(l.path || []).join(' → ')} · №{l.code}</small></button>
                            ))}
                            {!filteredLeaves.length && !filteredInfo.length && <span className="arm-empty">Ничего не найдено в классификаторе — попробуйте синоним («пожар», «дтп», «взрыв»)</span>}
                          </>
                        ) : (
                          <>
                            {(tree?.roots ?? []).map((r) => (
                              <button key={r.g} type="button" onClick={() => pushCascade({ g: r.g, value: r.title })}>
                                {r.title}
                              </button>
                            ))}
                            {!tree && <span className="arm-empty">Дерево загружается…</span>}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                  {/* Плашки ветвления: отвеченные шаги «Вопрос: ответ» (клик — назад),
                      активная плашка «Вопрос:» + кнопки (клик спавнит следующую). */}
                  {cascadePath.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                      {cascadeAnswered.map(({ b, i }) => (
                        <div key={`${b.level}-${i}`} className="arm-card" style={{ padding: '6px 10px', cursor: 'pointer' }} title="Вернуться на этот шаг" onClick={() => setCascadePath(cascadePath.slice(0, i + 1))}>
                          <div className="arm-taglabel">{b.label}: {b.value}</div>
                        </div>
                      ))}
                      <div className="arm-card" style={{ padding: '6px 10px' }}>
                        <div className="arm-taglabel">{cascadeQuestion}:</div>
                        {cascadeSkipped.length > 0 && <div className="arm-hint">{cascadeSkipped.join(' → ')}</div>}
                        {(cascade.buttons.length > 0 || cascade.selectable.length > 0) && (
                        <div className="arm-quick" style={{ marginTop: 6 }}>
                          {cascade.buttons.map((b) => (
                            <button key={b.value} type="button" className="arm-tag" onClick={() => pushCascade(b)}>
                              {b.value}{b.leaf_count ? ` · ${b.leaf_count}` : ''}
                            </button>
                          ))}
                          {cascade.selectable.map((code) => (
                            <button key={code} type="button" className="arm-tag sel" title="Выбрать этот тип" onClick={() => pickLeafByCode(code)}>
                              ✓ {leafTitle(code)}
                            </button>
                          ))}
                        </div>
                        )}
                      </div>
                    </div>
                  )}
                  {(selectedLeaf || infoType) && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                      <button type="button" className="arm-tag sel" title="Нажмите, чтобы отменить выбор" onClick={clearIncident}>
                        {selectedLeaf ? `${selectedLeaf.result} (№${selectedLeaf.code})` : infoType} ×
                      </button>
                    </div>
                  )}
                  {/* Плашки каскада выше; здесь результат выбора и флаги. */}
                  <div className="arm-hint">Тип выбирается из классификатора (Итоговый тип + путь признаков). Совпадение кнопки «Совпадение»: {matchBy}.</div>
                  {services.includes(SVC_103) && (
                    <label style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 8 }}>
                      <input type="checkbox" checked={refusal103} onChange={(e) => setRefusal103(e.target.checked)} /> Отказ от реагирования (103)
                    </label>
                  )}
                  {selectedLeaf && (
                    <>
                      <div className="arm-typechip">{selectedLeaf.group} · раздел {selectedLeaf.section?.g} «{selectedLeaf.section?.title}»{selectedLeaf.main ? ` · главная: ${selectedLeaf.main}` : ''}</div>
                      <div className="arm-blackhead" title="Итоговый тип происшествия по классификатору">№{selectedLeaf.code} <span onClick={clearIncident}>×</span></div>
                      <div className="arm-selectedwhat">{selectedLeaf.result}</div>
                      <div className="arm-hint">Путь: {(selectedLeaf.path || []).join(' → ') || '—'}</div>
                      <div className="arm-tagpanel">
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2px 12px' }}>
                        {FLAG_DEFS.map(({ key, label }) => (
                          <label key={key} className="arm-checkrow" style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0' }}>
                            <input type="checkbox" checked={!!flags[key]} onChange={(e) => setFlag(key, e.target.checked)} /> {label}
                          </label>
                        ))}
                        </div>
                        <div className="arm-tagrow">
                          <div className="arm-taglabel">Описание</div>
                          <input className="arm-tagdesc" value={tagDesc} onChange={(e) => setTagDesc(e.target.value)} placeholder="уточнение ТЭГа" />
                        </div>
                      </div>
                    </>
                  )}
                  {infoType && !selectedLeaf && (
                    <div className="arm-hint">Информационный тип без выезда: только описание, службы подбираются вручную.</div>
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
                  <span key={s} className={`arm-svc ${isMainService(svcGroup, s) ? 'main' : ''}`} title={`${s}${isMainService(svcGroup, s) ? ' — основная (двойное подчеркивание)' : ''}${visServices.includes(s) ? ' · добавлена ВИС' : ''}`}>
                    <span className="arm-svctel">📞</span>
                    <span className="arm-svcname">{serviceShortName(s)}{visServices.includes(s) ? ' [ВИС]' : ''}</span>
                    <button type="button" onClick={() => removeService(s)} title="убрать">×</button>
                  </span>
                ))}
                {informed.map((s) => (
                  <span key={`inf-${s}`} className="arm-svc informed" title={`${s} — уведомлена (не выезд)`}>
                    <span className="arm-svctel">✉</span>
                    <span className="arm-svcname">{serviceShortName(s)}</span>
                    <button type="button" onClick={() => removeService(s)} title="убрать">×</button>
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
