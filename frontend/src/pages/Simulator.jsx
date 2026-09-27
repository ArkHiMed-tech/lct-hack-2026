import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import useJson from '../hooks/useJson';
import useCallSocket from '../hooks/useCallSocket';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import CallInfoPanel from '../components/CallInfoPanel';
import CallTimer from '../components/CallTimer';
import CallFeed from '../components/CallFeed';
import ChatInput from '../components/ChatInput';
import QuickReplyPanel from '../components/QuickReplyPanel';
import DispatchPanel from '../components/DispatchPanel';
import ActionBar from '../components/ActionBar';
import { categoryLabel, serviceLabel } from '../lib/meta';

const SESSION_KEY = 'sim112-last-result';
// Код происшествия по категории (как чёрная шапка «Происшествие 101» на Рисунке1).
const GROUP_CODE = { fire: '101', police: '102', ambulance: '103', gas: '104', dth: '102', 101: '101', 102: '102', 103: '103', 104: '104' };

// Сценарий из БД (/api/scenarios/:id, в т.ч. card-*) с фолбэком на статику.
function useScenario(id) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    fetch(`/api/scenarios/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => { if (!cancelled) setState({ data, loading: false, error: null }); })
      .catch(() => {
        fetch(`/data/scenarios/${id}.json`)
          .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
          .then((data) => { if (!cancelled) setState({ data, loading: false, error: null }); })
          .catch((err) => { if (!cancelled) setState({ data: null, loading: false, error: err.message }); });
      });
    return () => { cancelled = true; };
  }, [id]);
  return state;
}
const OKRUGA = ['ЦАО', 'САО', 'СВАО', 'ВАО', 'ЮВАО', 'ЮАО', 'ЮЗАО', 'ЗАО', 'СЗАО', 'ЗелАО', 'ТАО', 'НАО'];

function stamp() {
  const n = new Date();
  const p = (v) => String(v).padStart(2, '0');
  return `${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;
}

export default function Simulator() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const scenario = useScenario(id);
  const rubric = useJson('/data/rubrics/rubric-112-base.json');

  const [status, setStatus] = useState('ringing');
  const [now, setNow] = useState(() => Date.now());
  const [messages, setMessages] = useState([]);
  const [sentSeq, setSentSeq] = useState(0);
  const [form, setForm] = useState({});
  const [services, setServices] = useState([]);
  const [dispatchedAtMs, setDispatchedAtMs] = useState(null);
  const [endedAtMs, setEndedAtMs] = useState(null);
  const [input, setInput] = useState('');
  const [toast, setToast] = useState(null);
  // Части адреса из сетки (как на Рисунке1: округ/район/улица/дом/...).
  const [addrParts, setAddrParts] = useState({ okrug: '', rayon: '', street: '', house: '', corpus: '', flat: '' });

  const startedAtRef = useRef(null);
  const answeredAtRef = useRef(null);
  const voiceSeq = useRef(2000);
  const voice = useCallSocket({
    onServerMessage: (msg) => {
      if (!msg || msg.type === 'ready' || msg.type === 'ended') return;
      voiceSeq.current += 1;
      setMessages((prev) => [
        ...prev,
        { seq: voiceSeq.current, sender: 'system', text: `Голосовой канал: ${msg.text ?? msg.type}`, time: stamp() },
      ]);
    },
  });

  useEffect(() => () => voice.disconnect(), []);

  useEffect(() => {
    startedAtRef.current = Date.now();
    const t = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(t);
  }, []);

  const timeline = scenario.data?.timeline ?? [];

  // Предвыбор служб из карточки 112 (display-имена → id дока ДДС).
  const DDS_BY_LABEL = { 'Служба 101': 'fire', 'Служба 104': 'gas', 'Служба 102': 'police', 'Деп. ЖКХ': 'utility', 'ЦЭМП': 'ambulance', 'Служба 103': 'ambulance', 'ЦОДД': 'codd', 'Мос.Без.': 'mosbez' };
  const servicesSeeded = useRef(false);
  useEffect(() => {
    if (servicesSeeded.current || !scenario.data?.expected?.expected_services) return;
    servicesSeeded.current = true;
    const ids = (scenario.data.expected.expected_services || [])
      .map((s) => DDS_BY_LABEL[s] ?? s)
      .filter((s, i, a) => s && a.indexOf(s) === i);
    if (ids.length) setServices(ids);
    const a = scenario.data.expected.address;
    if (a && typeof a === 'object' && !a.city) {
      setAddrParts((p) => ({
        ...p,
        street: a.street ?? '', house: a.house ?? '', corpus: a.corpus ?? '',
        flat: a.flat ?? '', okrug: a.okrug ?? '', rayon: a.rayon ?? '',
      }));
    }
  }, [scenario.data]);

  useEffect(() => {
    if (status !== 'connected' || answeredAtRef.current === null) return;
    const due = timeline.filter((m) => m.seq > sentSeq && answeredAtRef.current + m.t_sec * 1000 <= now);
    if (!due.length) return;
    const maxSeq = Math.max(...due.map((m) => m.seq));
    setMessages((prev) => [
      ...prev,
      ...due.map((m) => ({ seq: m.seq, sender: m.speaker, text: m.text, emotion: m.emotion, time: stamp() })),
    ]);
    setSentSeq(maxSeq);
  }, [now, status, timeline, sentSeq]);

  // Склейка адреса из сетки в form.address (подстроковый матч токенов — скоринг цел).
  useEffect(() => {
    const city = scenario.data?.expected?.address?.city ?? 'Москва';
    const bits = [`г. ${city}`];
    if (addrParts.street.trim()) bits.push(`ул. ${addrParts.street.trim()}`);
    if (addrParts.house.trim()) bits.push(`д. ${addrParts.house.trim()}`);
    if (addrParts.corpus.trim()) bits.push(`корп. ${addrParts.corpus.trim()}`);
    if (addrParts.flat.trim()) bits.push(`кв. ${addrParts.flat.trim()}`);
    if (addrParts.okrug) bits.push(addrParts.okrug);
    if (addrParts.rayon.trim()) bits.push(addrParts.rayon.trim());
    const filled = Object.values(addrParts).some((v) => v.trim() !== '');
    const composed = filled ? bits.join(', ') : '';
    setForm((prev) => (prev.address === composed ? prev : { ...prev, address: composed }));
  }, [addrParts, scenario.data]);

  const handleAnswer = () => {
    if (answeredAtRef.current || status !== 'ringing') return;
    answeredAtRef.current = Date.now();
    setStatus('connected');
    voice.connect(id);
    setMessages((prev) => [...prev, { seq: Number.MAX_SAFE_INTEGER, sender: 'system', text: 'Вызов принят. Линия подключена.', time: stamp() }]);
  };

  const nextUserSeq = useRef(1000);
  const handleSend = () => {
    const text = input.trim();
    if (!text || status !== 'connected') return;
    nextUserSeq.current += 1;
    setMessages((prev) => [...prev, { seq: nextUserSeq.current, sender: 'operator', text, time: stamp() }]);
    setInput('');
  };
  const handleInsertQuick = (text) => setInput(text.replace(/\s+/g, ' '));
  const handleToggleService = (sid) => setServices((prev) => (prev.includes(sid) ? prev.filter((s) => s !== sid) : [...prev, sid]));
  const handleDispatch = () => {
    if (!services.length) {
      setToast('Выберите хотя бы одну службу в серой полосе «Службы» внизу.');
      return;
    }
    setDispatchedAtMs(Date.now());
    nextUserSeq.current += 1;
    setMessages((prev) => [...prev, { seq: nextUserSeq.current, sender: 'system', text: `Вызов передан в службы: ${services.join(', ')}.`, time: stamp() }]);
  };
  const endingRef = useRef(false);
  const handleEnd = () => {
    if (endingRef.current) return;
    endingRef.current = true;
    voice.disconnect();
    setEndedAtMs(Date.now());
  };

  useEffect(() => {
    if (endedAtMs == null || !scenario.data || !rubric.data) return;

    const payload = {
      user_id: user?.id ?? null,
      scenario_id: scenario.data.id,
      rubric_id: rubric.data.id,
      answer_latency_sec: answeredAtRef.current && startedAtRef.current
        ? (answeredAtRef.current - startedAtRef.current) / 1000
        : null,
      messages,
      form,
      services,
      dispatched_at_ms: dispatchedAtMs,
      ended_at_ms: endedAtMs,
    };

    const submitResult = async () => {
      try {
        const response = await fetch('/api/sessions/finish', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const result = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(result?.detail || 'Не удалось сохранить результат');
        }

        try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(result)); } catch { /* ignore */ }
        navigate('/results', { state: { result, scenario: scenario.data } });
      } catch (error) {
        setToast(error.message || 'Не удалось завершить тренировку');
      }
    };

    submitResult();
  }, [endedAtMs, messages, form, services, dispatchedAtMs, scenario.data, rubric.data, user, navigate]);

  if (scenario.loading || rubric.loading) {
    return (<div className="app-shell"><AppHeader /><LoadingSpinner label="Подготовка рабочего места…" /></div>);
  }
  if (scenario.error || rubric.error) {
    return (<div className="app-shell"><AppHeader /><ErrorBanner message={scenario.error ?? rubric.error} /></div>);
  }

  const sc = scenario.data;
  const incidentNum = 36814845;
  const groupCode = GROUP_CODE[sc.category] ?? '101';
  const expectedServices = sc.expected?.expected_services ?? [];
  const city = sc.expected?.address?.city ?? sc.expected?.address?.subject ?? sc.expected?.address_str ?? 'Москва';
  const setPart = (k) => (e) => setAddrParts((p) => ({ ...p, [k]: e.target.value }));
  // Живая строка-сводка тэгов (как белая строка на Рисунке1).
  const tagSummary = [
    form.what || sc.title,
    ...(form.factors ?? []),
    form.threat ? `Угроза: ${form.threat}` : null,
    form.conditions || null,
  ].filter(Boolean).join(' . ');

  return (
    <div className="app-shell">
      <AppHeader title={`Происшествие ${incidentNum}`} />

      <div className="dds-back dark">
        <Link to="/">← К списку происшествий</Link>
        <Link to="/card">Создать карточку</Link>
      </div>

      <div className="arm-wrap">
        {/* Верхний ряд как на Рисунке1: телефоны + инфо-блок + просмотр/дополнение */}
        <div className="arm-toprow">
          <div className="arm-phones arm-phones-sim">
            <div className="arm-phone arm-off">
              <span className="arm-tel-ico">☎</span>
              <div><b>Отключение</b><div className="arm-minibtns"><span>записи звонков</span><span>список SMS</span></div></div>
            </div>
            <div className="arm-phone">
              <span className="arm-tel-ico">☎</span>
              <div><small>АОН</small><div className="arm-telnum">{sc.call?.phone ?? '+7 (__) __-__'}</div></div>
              <span className="arm-chat">💬</span>
            </div>
            <div className="arm-phone">
              <span className="arm-tel-ico">☎</span>
              <div><small>предоставленный</small><div className="arm-telnum">+7 (__) __-__</div></div>
              <span className="arm-aohtag">AOH</span>
              <span className="arm-chat">💬</span>
            </div>
            <div className="arm-phone">
              <span className="arm-tel-ico">☎</span>
              <div><small>телефон на место</small><div className="arm-telnum">+7 (__) __-__</div></div>
              <span className="arm-aohtag">AOH</span>
              <span className="arm-chat">💬</span>
            </div>
          </div>
          <div className="arm-incident">
            <div className="arm-incident-info">
              <b>Происшествие {incidentNum}</b>
              <br />Сохр. 17.09.2026 в 11:12:43
              <br />Опер. , АРМ 4, УМЦ О п
            </div>
            <div className="arm-sidebtns">
              <button type="button" className="view">просмотр</button>
              <button type="button" className="add">дополнение</button>
            </div>
            <CallTimer startedAtMs={startedAtRef.current} answeredAtMs={answeredAtRef.current} />
          </div>
        </div>

        {/* Заявитель как на Рисунке1 */}
        <div className="arm-appline">
          <label>Фамилия и имя заявителя
            <input
              value={form.caller_name ?? ''}
              onChange={(e) => setForm((prev) => ({ ...prev, caller_name: e.target.value }))}
              disabled={!!endedAtMs}
              placeholder=""
            />
          </label>
          <div className="arm-apptrio">
            Пострадавшие: {form.victims || 'нет'} &nbsp; Отказ от скорой: нет &nbsp; Заблокированные: нет &nbsp;&nbsp;
            <span className="arm-badges">
              <span className="arm-badge">ЧС ⚡</span>
              <span className="arm-badge red">ЧП ⚠</span>
              <button type="button" className="arm-editbtn" title="редактировать">✎</button>
            </span>
          </div>
        </div>

        <div className="arm-cols">
          {/* СЛЕВА: адрес (район) + логи вызова */}
          <section style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
            <div className="arm-card">
              <div className="arm-addr-summary">
                Россия, {city}, ({addrParts.okrug || '…'}, {addrParts.rayon || addrParts.street || '…'}) <span className="arm-pin">📍</span>
              </div>
              <div className="arm-addr-sub">{form.address || 'адрес уточняется в диалоге'}</div>
              <div className="arm-addr-grid">
                <label>Округ:<select value={addrParts.okrug} onChange={setPart('okrug')} disabled={!!endedAtMs}><option value="">—</option>{OKRUGA.map((o) => <option key={o} value={o}>{o}</option>)}</select></label>
                <label>Район:<input value={addrParts.rayon} onChange={setPart('rayon')} disabled={!!endedAtMs} /></label>
                <label>Улица:<input value={addrParts.street} onChange={setPart('street')} disabled={!!endedAtMs} /></label>
                <label>Дом/Вл:<input value={addrParts.house} onChange={setPart('house')} disabled={!!endedAtMs} /></label>
                <label>Корпус:<input value={addrParts.corpus} onChange={setPart('corpus')} disabled={!!endedAtMs} /></label>
                <label>Квартира/офис:<input value={addrParts.flat} onChange={setPart('flat')} disabled={!!endedAtMs} /></label>
              </div>
            </div>
            <div className="arm-card">
              <div className="arm-cardhead">Логи вызова <span style={{ opacity: 0.7 }}>· голос: {voice.state}</span></div>
              <CallFeed messages={messages} connected={status !== 'ringing'} />
              <div style={{ marginTop: 8 }}>
                <ChatInput value={input} onChange={setInput} onSend={handleSend} disabled={status !== 'connected'} />
                <QuickReplyPanel quickReplies={sc.quick_replies} onInsert={handleInsertQuick} disabled={status !== 'connected'} />
              </div>
            </div>
          </section>

          {/* СПРАВА: заполненная карточка */}
          <section style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
            <div className="arm-card">
              <div className="arm-blackhead">Происшествие {groupCode}</div>
              <div className="arm-sumrow">{tagSummary}</div>
              <div className="arm-sumrow">Класс.: {categoryLabel(sc.category)}{form.what ? `: ${form.what}` : ''} ;</div>
              <div className="arm-sumrow">[ВИС] Класс.:</div>
              <div className="arm-tagpanel">
                <div className="arm-tagrow">
                  <div className="arm-taglabel">Ожидаемые службы</div>
                  <div className="arm-tagopts">
                    {expectedServices.length
                      ? expectedServices.map((s) => <span key={s} className="arm-tag">{serviceLabel(s)}</span>)
                      : <span className="arm-hint">определяются по ходу заполнения</span>}
                  </div>
                </div>
                <div className="arm-tagrow">
                  <div className="arm-taglabel">Выбрано служб</div>
                  <div className="arm-tagopts">
                    {services.length
                      ? services.map((s) => <span key={s} className="arm-tag sel">{serviceLabel(s)}</span>)
                      : <span className="arm-hint">отметьте в серой полосе внизу</span>}
                  </div>
                </div>
              </div>
            </div>
            <CallInfoPanel scenario={sc} status={status} callerKnown={false} />
          </section>
        </div>

        {/* ВНИЗУ: серая полоса служб + действия */}
        <div className="arm-services sim-gray">
          <DispatchPanel scenario={sc} selected={services} onToggle={handleToggleService} disabled={!!dispatchedAtMs} />
          <ActionBar
            status={status} dispatched={dispatchedAtMs != null} servicesSelected={services.length > 0}
            onAnswer={handleAnswer} onDispatch={handleDispatch} onEnd={handleEnd}
            onRestart={() => window.location.reload()}
          />
        </div>
      </div>

      {toast && (
        <div className="toast" role="status">
          {toast}
          <button type="button" className="toast-close" onClick={() => setToast(null)}>×</button>
        </div>
      )}
    </div>
  );
}
