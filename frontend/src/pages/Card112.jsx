import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';

// Норматив набора карточки (сек). При превышении таймер краснеет (по ТЗ).
const CARD_SLA_SEC = 30;
const INCIDENT_NO = 36812195;

// Быстрые типы из скриншота АРМ ("что случилось?").
const QUICK_TYPES = [
  'Отмена вызова', 'Тестовый вызов', 'Передача дежурства', 'ДТП', 'Консультация',
  'Вызов на иностранном языке', 'Ошибочно набран номер', 'Справка-101', 'Справка-102', 'Справка-103',
];

// Полный список "Что случилось" из КАРТОЧКА 112.docx.
const INCIDENT_TYPES = [
  { title: 'Аварии и происшествия в городском хозяйстве', groups: ['104'] },
  { title: 'Аварии и происшествия на транспортных объектах', groups: ['101'] },
  { title: 'Аварии на гидротехнических сооружениях', groups: ['101'] },
  { title: 'Аварии на опасных и производственных объектах', groups: ['101'] },
  { title: 'Благодарность службам', groups: ['101', '102', '103', '104'] },
  { title: 'БПЛА', groups: ['101', '102'] },
  { title: 'Взрыв', groups: ['101', '102'] },
  { title: 'Внутренний звонок (звонок от работников)', groups: ['101', '102', '103', '104'] },
  { title: 'Вызов на иностранном языке', groups: ['101', '102', '103', '104'] },
  { title: 'Дополнительный звонок от заявителя', groups: ['101', '102', '103', '104'] },
  { title: 'Дорожные помехи', groups: ['102'] },
  { title: 'ДТП', groups: ['101', '102', '103'] },
  { title: 'Жалоба на действие или бездействие служб', groups: ['101', '102', '103', '104'] },
  { title: 'Животные', groups: ['104'] },
  { title: 'Консультация', groups: ['101', '102', '103', '104'] },
  { title: 'Нецелевой вызов', groups: ['101', '102', '103', '104'] },
  { title: 'Обрушение', groups: ['101'] },
  { title: 'Отзыв о работе 112 Москва', groups: ['101', '102', '103', '104'] },
  { title: 'Отмена вызова', groups: ['101', '102', '103', '104'] },
  { title: 'Ошибочно набран номер', groups: ['101', '102', '103', '104'] },
  { title: 'Передача дежурства', groups: ['101', '102', '103', '104'] },
  { title: 'Помощь службам', groups: ['101', '102', '103', '104'] },
  { title: 'Природная стихия', groups: ['101'] },
  { title: 'Прочие происшествия', groups: ['101', '102', '103', '104'] },
  { title: 'Радиация', groups: ['101'] },
  { title: 'Разбитый градусник', groups: ['104'] },
  { title: 'Ребенок в опасности', groups: ['102', '103'] },
  { title: 'Сбор', groups: ['101', '102', '103', '104'] },
  { title: 'Скопление воды', groups: ['104'] },
  { title: 'Смертельный исход', groups: ['102', '103'] },
  { title: 'Социальная помощь', groups: ['103', '104'] },
  { title: 'Справка 101', groups: ['101'] },
  { title: 'Справка 102', groups: ['102'] },
  { title: 'Справка 103', groups: ['103'] },
  { title: 'Справка 104', groups: ['104'] },
  { title: 'Справка ГИБДД', groups: ['102'] },
  { title: 'Справка Городское хозяйство', groups: ['104'] },
  { title: 'Справка МЧС', groups: ['101'] },
  { title: 'Тестовый вызов', groups: ['101', '102', '103', '104'] },
  { title: 'Технический сбой (сбой оборудования 112 Москва)', groups: ['101', '102', '103', '104'] },
  { title: 'Тренировка', groups: ['101', '102', '103', '104'] },
  { title: 'Уведомление о ЧС', groups: ['101'] },
  { title: 'Угроза взрыва/террористического акта', groups: ['101', '102'] },
  { title: 'Угроза выброса опасных веществ и радиации', groups: ['101'] },
  { title: 'Угроза обрушения', groups: ['101'] },
  { title: 'Человек в опасности', groups: ['101', '102', '103'] },
  { title: 'Экологическое происшествие', groups: ['104'] },
];

// ТЭГ-группы "Происшествие 101" — по скриншотам АРМ.
const WHERE_OPTIONS = ['Улица', 'Транспорт', 'Дом', 'Здание / объект', 'Опасный объект'];
const STREET_DETAIL = ['Мусор', 'Трава, пух', 'Парк', 'Лес', 'Торф', 'Мачта освещения', 'Опора контактной сети', 'ЛЭП', 'Провода', 'Дерево, деревья', 'Горит человек', 'Что горит неизвестно'];
const TRANSPORT_DETAIL = ['Общественный транспорт', 'Автомашина', 'ДТП с пожаром', 'Опасный груз', 'Воздушный транспорт', 'Аэропорт', 'Ж/Д транспорт', 'Вокзал Ж/Д, платформа Ж/Д', 'Транспорт прочее', 'Водный', 'Мост', 'Эстакада', 'Тоннель', 'Переход подземный/наземный', 'Метро', 'МЦК, МЦД', 'Ж/Д пути', 'Релейный шкаф Ж/Д'];

// Каталог служб (из скриншотов) — мок. BACKEND-READY: позже заменить на справочник с бэкенда.
const SERVICE_CATALOG = ['Служба 101', 'Служба 102', 'Служба 103', 'Служба 104', 'Деп. ЖКХ', 'ЦЭМП', 'ЦОДД', 'Мосгортранс', 'Мос.Без.', 'ОАТИ', 'Гормост', 'Мосводоканал'];

// Мок-правило авто-подбора служб по типу и тэгам (по скриншотам: 101+транспорт → 101, 102, ЖКХ, ЦЭМП, ЦОДД, ...).
function autoServicesFor(group, tags) {
  const out = [];
  const push = (s) => { if (!out.includes(s)) out.push(s); };
  if (group === '101') push('Служба 101');
  if (group === '102') push('Служба 102');
  if (group === '103') { push('Служба 103'); push('ЦЭМП'); }
  if (group === '104') push('Деп. ЖКХ');
  const t = tags.join(' ');
  if (/Транспорт|Общественный|Автомашина|Метро|Мост|Тоннель|Эстакада|МЦК|Ж\/Д|Вокзал|Аэропорт|ДТП с пожаром/.test(t)) { push('ЦОДД'); push('Мосгортранс'); }
  if (/Мусор|Парк|Лес|Торф|Трава|Дерево|ЛЭП|Провода|Мачта|Опора/.test(t)) push('Деп. ЖКХ');
  if (/Угроза людям - Да|Медицинская помощь - Да/.test(t)) push('ЦЭМП');
  if (/Правонарушение|Есть правонарушение/.test(t)) push('Служба 102');
  if (/Требуется эвакуация - Да/.test(t)) push('Мос.Без.');
  if (/Газификация - Да/.test(t)) push('Служба 104');
  return out;
}

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
  const [query, setQuery] = useState('');
  const [listOpen, setListOpen] = useState(false);
  const [selectedType, setSelectedType] = useState(null); // {title, groups}
  const [tags, setTags] = useState({ where: '', sign: '', access: '', detail: '', place: '', threat: '', violation: '', medical: '', evac: '', gas: '', tagDesc: '' });
  const [services, setServices] = useState([]); // ручные + авто (итог храним явно для визуала)
  const [svcMenuOpen, setSvcMenuOpen] = useState(false);
  const [addr, setAddr] = useState({ country: '', subject: 'Москва', settlement: '', object: '', okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' });
  const [applicant, setApplicant] = useState('');
  const [appStatuses, setAppStatuses] = useState([]);
  const [desc, setDesc] = useState('');
  const [toast, setToast] = useState(null);

  const startedAtRef = useRef(Date.now());
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

  const filteredTypes = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return INCIDENT_TYPES;
    return INCIDENT_TYPES.filter((t) => t.title.toLowerCase().includes(q));
  }, [query]);

  const pickType = (t) => {
    setSelectedType(t);
    setQuery('');
    setListOpen(false);
    setTags({ where: '', sign: '', access: '', detail: '', place: '', threat: '', violation: '', medical: '', evac: '', gas: '', tagDesc: '' });
    setServices(autoServicesFor(t.groups[0], []));
  };

  const setTag = (key, v) => {
    const next = { ...tags, [key]: v };
    // смена "Где" сбрасывает детализацию другого раздела
    if (key === 'where') next.detail = '';
    setTags(next);
    if (selectedType) {
      const flat = Object.values(next).filter(Boolean);
      setServices((prev) => [...new Set([...prev, ...autoServicesFor(selectedType.groups[0], flat)])]);
    }
  };

  const toggleAppStatus = (s) => setAppStatuses((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]));
  const addService = (s) => { setServices((p) => (p.includes(s) ? p : [...p, s])); setSvcMenuOpen(false); };
  const removeService = (s) => setServices((p) => p.filter((x) => x !== s));

  const clearAddress = () => setAddr({ country: '', subject: 'Москва', settlement: '', object: '', okrug: '', rayon: '', street: '', house: '', corpus: '', stroenie: '', flat: '', entrance: '', floor: '', code: '', descr: '' });

  const handleMockSave = () => {
    // BACKEND-READY: форма совместима с POST /api/reports/create.
    const payload = {
      user_id: user?.id ?? null, what: selectedType?.title ?? '', incident_category: group,
      address: addr, caller_name: applicant, caller_statuses: appStatuses,
      factors: Object.values(tags).filter(Boolean), services,
      description: desc, elapsed_sec: elapsedSec, overtime,
    };
    console.log('[card112 mock save]', payload);
    setToast(`Мок-сохранение: «${selectedType?.title ?? 'тип не выбран'}», служб: ${services.length}. Бэкенд не вызывается.`);
  };

  const setA = (k) => (e) => setAddr({ ...addr, [k]: e.target.value });
  const today = new Date().toLocaleDateString('ru-RU');

  return (
    <div className="app-shell">
      <AppHeader title="Карточка происшествия 112" />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="dds-back">
            <Link to="/">← Главная</Link>
            <Link to="/incidents">Поиск происшествий</Link>
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
                <span className="arm-tel-ico">☎</span>
                <div><b>Отключение</b><div className="arm-minibtns"><span>записи звонков</span><span>список SMS</span></div></div>
              </div>
              {[['АОН', 0], ['предоставленный', 1], ['телефон на место', 2]].map(([label]) => (
                <div className="arm-phone" key={label}>
                  <span className="arm-tel-ico">☎</span>
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

              {/* СПРАВА: происшествие */}
              <section className="arm-right">
                {!selectedType ? (
                  <div className="arm-card">
                    <div className="arm-linkhead">Введите тип происшествия</div>
                    <div className="arm-searchwrap">
                      <input
                        className="arm-what" value={query} placeholder="что случилось?"
                        onChange={(e) => { setQuery(e.target.value); setListOpen(true); }}
                        onFocus={() => setListOpen(true)}
                      />
                      {listOpen && (
                        <div className="arm-typelist">
                          {filteredTypes.map((t) => (
                            <button key={t.title} type="button" onClick={() => pickType(t)}>{t.title}</button>
                          ))}
                          {!filteredTypes.length && <span className="arm-empty">Ничего не найдено</span>}
                        </div>
                      )}
                    </div>
                    <div className="arm-quick">
                      {QUICK_TYPES.map((q) => {
                        const found = INCIDENT_TYPES.find((t) => t.title.toLowerCase().startsWith(q.toLowerCase()));
                        return <button key={q} type="button" className="arm-tag" onClick={() => found && pickType(found)}>{q}</button>;
                      })}
                    </div>
                    <div className="arm-signif">Значимые типы происшествий:</div>
                  </div>
                ) : (
                  <div className="arm-card">
                    <button type="button" className="arm-linkhead" onClick={() => setSelectedType(null)}>добавить тип происшествия</button>
                    <div className="arm-typechip">Происшествие {group}</div>
                    <div className="arm-blackhead">Происшествие {group} <span onClick={() => setSelectedType(null)}>×</span></div>
                    <div className="arm-tagpanel">
                      {group === '101' ? (
                        <>
                          <TagRow label="Где" options={WHERE_OPTIONS} value={tags.where} onPick={(v) => setTag('where', v)} />
                          <TagRow label={tags.where === 'Транспорт' ? 'Признак пожара (транспорт)' : 'Признак пожара (улица)'} options={['Открытое пламя / Дым', 'Запах гари']} value={tags.sign} onPick={(v) => setTag('sign', v)} />
                          <TagRow label="Доступ" options={['Нет доступа', 'Есть доступ']} value={tags.access} onPick={(v) => setTag('access', v)} />
                          {tags.where === 'Транспорт' && (
                            <TagRow label="Транспорт (пламя, дым)" options={TRANSPORT_DETAIL} value={tags.detail} onPick={(v) => setTag('detail', v)} />
                          )}
                          {tags.where !== 'Транспорт' && (
                            <TagRow label="Улица (пламя, дым)" options={STREET_DETAIL} value={tags.detail} onPick={(v) => setTag('detail', v)} />
                          )}
                          <TagRow label="Место происшествия" options={['Тоннель', 'Пешеходный переход']} value={tags.place} onPick={(v) => setTag('place', v)} />
                          <TagRow label="Угроза людям" options={['Да', 'Нет']} value={tags.threat} onPick={(v) => setTag('threat', v)} />
                          <TagRow label="Правонарушение" options={['Есть правонарушение']} value={tags.violation} onPick={(v) => setTag('violation', v)} />
                          <TagRow label="Медицинская помощь" options={['Да', 'Нет']} value={tags.medical} onPick={(v) => setTag('medical', v)} />
                          <TagRow label="Требуется эвакуация" options={['Да', 'Нет']} value={tags.evac} onPick={(v) => setTag('evac', v)} />
                          <TagRow label="Проведена ли газификация" options={['Да', 'Нет', 'Нет данных']} value={tags.gas} onPick={(v) => setTag('gas', v)} />
                          <div className="arm-tagrow">
                            <div className="arm-taglabel">Описание</div>
                            <input className="arm-tagdesc" value={tags.tagDesc} onChange={(e) => setTag('tagDesc', e.target.value)} />
                          </div>
                        </>
                      ) : (
                        <>
                          <TagRow label="Угроза людям" options={['Да', 'Нет']} value={tags.threat} onPick={(v) => setTag('threat', v)} />
                          <TagRow label="Правонарушение" options={['Есть правонарушение']} value={tags.violation} onPick={(v) => setTag('violation', v)} />
                          <TagRow label="Медицинская помощь" options={['Да', 'Нет']} value={tags.medical} onPick={(v) => setTag('medical', v)} />
                          <TagRow label="Требуется эвакуация" options={['Да', 'Нет']} value={tags.evac} onPick={(v) => setTag('evac', v)} />
                          <div className="arm-tagrow">
                            <div className="arm-taglabel">Описание</div>
                            <input className="arm-tagdesc" value={tags.tagDesc} onChange={(e) => setTag('tagDesc', e.target.value)} />
                          </div>
                          <div className="arm-hint">Полный набор ТЭГов группы {group} подключается из классификатора (демо).</div>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </section>
            </div>

            {/* ВНИЗУ: оранжевая полоса служб */}
            <div className="arm-services">
              <span className="arm-svclabel">Службы:</span>
              <div className="arm-svcchips">
                {services.map((s) => (
                  <span key={s} className="arm-svc">☎ {s} <button type="button" onClick={() => removeService(s)} title="убрать">×</button></span>
                ))}
                <div className="arm-svcadd">
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
                <button type="button" className="arm-save" onClick={handleMockSave}>сохранить</button>
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
              {toast}
              <button type="button" className="toast-close" onClick={() => setToast(null)}>×</button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
