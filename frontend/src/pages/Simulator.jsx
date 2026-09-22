import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import useJson from '../hooks/useJson';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import CallInfoPanel from '../components/CallInfoPanel';
import CallTimer from '../components/CallTimer';
import CallFeed from '../components/CallFeed';
import ChatInput from '../components/ChatInput';
import QuickReplyPanel from '../components/QuickReplyPanel';
import IncidentForm from '../components/IncidentForm';
import DispatchPanel from '../components/DispatchPanel';
import ChecklistProgress from '../components/ChecklistProgress';
import ActionBar from '../components/ActionBar';
import { computeDraftPreview } from '../lib/scoring';

const SESSION_KEY = 'sim112-last-result';

export default function Simulator() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const scenario = useJson(`/data/scenarios/${id}.json`);
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

  const startedAtRef = useRef(null);
  const answeredAtRef = useRef(null);

  useEffect(() => {
    startedAtRef.current = Date.now();
    const t = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(t);
  }, []);

  const timeline = scenario.data?.timeline ?? [];

  useEffect(() => {
    if (status !== 'connected' || answeredAtRef.current === null) return;
    const due = timeline.filter((m) => m.seq > sentSeq && answeredAtRef.current + m.t_sec * 1000 <= now);
    if (!due.length) return;
    const maxSeq = Math.max(...due.map((m) => m.seq));
    setMessages((prev) => [
      ...prev,
      ...due.map((m) => ({ seq: m.seq, sender: m.speaker, text: m.text, emotion: m.emotion })),
    ]);
    setSentSeq(maxSeq);
  }, [now, status, timeline, sentSeq]);

  const live = useMemo(() => {
    if (!scenario.data || !rubric.data) return null;
    const session = {
      messages, form, services,
      dispatched: dispatchedAtMs != null,
      dispatchedAtMs, endedAtMs: null,
      answerLatencySec: answeredAtRef.current ? (answeredAtRef.current - startedAtRef.current) / 1000 : null,
      call: scenario.data.call,
    };
    return computeDraftPreview(session, scenario.data, rubric.data, user);
  }, [messages, form, services, dispatchedAtMs, scenario.data, rubric.data, user]);

  const groups = live
    ? Object.entries(live.scores).map(([gid, score]) => ({ id: gid, title: (rubric.data.groups.find((g) => g.id === gid) || {}).title ?? gid, score }))
    : [];
  const totalLive = live ? live.total_score / 100 : null;

  const handleAnswer = () => {
    if (answeredAtRef.current || status !== 'ringing') return;
    answeredAtRef.current = Date.now();
    setStatus('connected');
    setMessages((prev) => [...prev, { seq: Number.MAX_SAFE_INTEGER, sender: 'system', text: 'Вызов принят. Линия подключена.' }]);
  };

  const nextUserSeq = useRef(1000);
  const handleSend = () => {
    const text = input.trim();
    if (!text || status !== 'connected') return;
    nextUserSeq.current += 1;
    setMessages((prev) => [...prev, { seq: nextUserSeq.current, sender: 'operator', text }]);
    setInput('');
  };
  const handleInsertQuick = (text) => setInput(text.replace(/\s+/g, ' '));
  const handleToggleService = (sid) => setServices((prev) => (prev.includes(sid) ? prev.filter((s) => s !== sid) : [...prev, sid]));
  const handleDispatch = () => {
    if (!services.length) {
      setToast('Выберите хотя бы одну службу в нижнем доке «Службы».');
      return;
    }
    setDispatchedAtMs(Date.now());
    nextUserSeq.current += 1;
    setMessages((prev) => [...prev, { seq: nextUserSeq.current, sender: 'system', text: `Вызов передан в службы: ${services.join(', ')}.` }]);
  };
  const endingRef = useRef(false);
  const handleEnd = () => {
    if (endingRef.current) return;
    endingRef.current = true;
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
  const lastMsg = [...messages].reverse().find((m) => m.sender === 'citizen');

  return (
    <div className="app-shell">
      <AppHeader title={`Происшествие ${incidentNum}`} />

      <div className="dds-back dark">
        <Link to="/incidents">← К списку происшествий</Link>
        <Link to="/">На главную</Link>
      </div>

      <div className="dds-card-title">Происшествие {incidentNum}</div>

      <div className="dds-phones">
        <div className="dds-phone">
          <b>☎ Отключение</b>
          <div className="mini-btns"><span>записи звонков</span><span>список SMS</span></div>
        </div>
        <div className="dds-phone"><b>☎ АОН</b><span className="tel">{sc.call?.phone ?? ''}</span></div>
        <div className="dds-phone"><b>☎ предоставленный</b></div>
        <div className="dds-phone"><b>☎ телефон на место</b></div>
        <div style={{ display: 'flex', gap: 4 }}>
          <div className="dds-incident-info" style={{ flex: 1 }}>
            <b>Происшествие {incidentNum}</b>
            <br />Сохр. 17.09.2026 в 11:12:43
            <br />Опер. , АРМ 4, УМЦ О п
          </div>
          <div className="dds-side-btns">
            <button type="button" className="view">просмотр</button>
            <button type="button" className="add">дополнение</button>
          </div>
        </div>
      </div>

      <div className="dds-meta">
        <div className="dds-meta-cell">ФИО заявителя</div>
        <div className="dds-meta-cell">
          Пострадавшие: нет &nbsp; Отказ от скорой: нет &nbsp; Заблокированные: нет &nbsp;&nbsp;
          <span className="dds-badges">
            <span className="dds-badge">ЧС ⚡</span>
            <span className="dds-badge red">ЧП ⚠</span>
            <button type="button" className="dds-edit" title="редактировать">✎</button>
          </span>
        </div>
      </div>
      <div className="dds-addr">
        Россия, Москва, (ТАО, Вороновское)
        <small>Троицкий административный округ</small>
      </div>

      <div className="dds-body">
        <div className="dds-left-white">
          <div className="t">17.09.2026 11:13:19 &nbsp; 0 УМЦ О.п.</div>
          <div>{lastMsg ? lastMsg.text : sc.title}</div>
          <div style={{ marginTop: 10, background: '#fff', border: '1px solid #ccc', padding: 8 }}>
            <CallTimer startedAtMs={startedAtRef.current} answeredAtMs={answeredAtRef.current} />
            <div style={{ marginTop: 8 }}>
              <CallInfoPanel scenario={sc} status={status} callerKnown={false} />
            </div>
          </div>
        </div>
        <div className="dds-right-gray">
          <div className="h">Происшествие 101</div>
          <div className="r">Дом . Открытое пламя / Дым (дом), Запах гари (дом) . Дом многоквартирный . квартира . Есть угроза людям . Есть газификация .</div>
          <div className="r">Класс.: пожар: квартира ;</div>
          <div className="r">[ВИС] Класс.:</div>
          <div className="r">
            <ChecklistProgress groups={groups} total={totalLive} />
          </div>
        </div>
      </div>

      <div className="dds-train">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <CallFeed messages={messages} connected={status !== 'ringing'} />
          <div className="panel">
            <ChatInput value={input} onChange={setInput} onSend={handleSend} disabled={status !== 'connected'} />
            <QuickReplyPanel quickReplies={sc.quick_replies} onInsert={handleInsertQuick} disabled={status !== 'connected'} />
          </div>
          <ActionBar
            status={status} dispatched={dispatchedAtMs != null} servicesSelected={services.length > 0}
            onAnswer={handleAnswer} onDispatch={handleDispatch} onEnd={handleEnd}
            onRestart={() => window.location.reload()}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <IncidentForm scenario={sc} values={form} onChange={(fieldId, v) => setForm((prev) => ({ ...prev, [fieldId]: v }))} disabled={!!endedAtMs} />
        </div>
      </div>

      <DispatchPanel scenario={sc} selected={services} onToggle={handleToggleService} disabled={!!dispatchedAtMs} />

      {toast && (
        <div className="toast" role="status">
          {toast}
          <button type="button" className="toast-close" onClick={() => setToast(null)}>×</button>
        </div>
      )}
    </div>
  );
}
