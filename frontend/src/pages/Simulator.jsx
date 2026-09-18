import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import useJson from '../hooks/useJson';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
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
import { computeDraftResult } from '../lib/scoring';

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
      messages,
      form,
      services,
      dispatched: dispatchedAtMs != null,
      dispatchedAtMs,
      endedAtMs: null,
      answerLatencySec: answeredAtRef.current ? (answeredAtRef.current - startedAtRef.current) / 1000 : null,
      call: scenario.data.call,
    };
    const res = computeDraftResult(session, scenario.data, rubric.data, user);
    return res;
  }, [messages, form, services, dispatchedAtMs, scenario.data, rubric.data, user]);

  const groups = live
    ? Object.entries(live.scores)
        .map(([gid, score]) => ({ id: gid, title: (rubric.data.groups.find((g) => g.id === gid) || {}).title ?? gid, score }))
    : [];

  const totalLive = live ? live.total_score / 100 : null;

  const handleAnswer = () => {
    if (answeredAtRef.current || status !== 'ringing') return;
    answeredAtRef.current = Date.now();
    setStatus('connected');
    setMessages((prev) => [
      ...prev,
      { seq: Number.MAX_SAFE_INTEGER, sender: 'system', text: 'Вызов принят. Линия подключена.' },
    ]);
  };

  const nextUserSeq = useRef(1000);
  const handleSend = () => {
    const text = input.trim();
    if (!text || status !== 'connected') return;
    nextUserSeq.current += 1;
    setMessages((prev) => [...prev, { seq: nextUserSeq.current, sender: 'operator', text }]);
    setInput('');
  };

  const handleInsertQuick = (text) => {
    setInput(text.replace(/\s+/g, ' '));
  };

  const handleToggleService = (sid) => {
    setServices((prev) => (prev.includes(sid) ? prev.filter((s) => s !== sid) : [...prev, sid]));
  };

  const handleDispatch = () => {
    if (!services.length) {
      setToast('Выберите хотя бы одну экстренную службу для передачи вызова.');
      return;
    }
    setDispatchedAtMs(Date.now());
    nextUserSeq.current += 1;
    setMessages((prev) => [
      ...prev,
      { seq: nextUserSeq.current, sender: 'system', text: `Вызов передан в экстренные службы: ${services.join(', ')}.` },
    ]);
  };

  const handleEnd = () => {
    if (endingRef.current) return;
    endingRef.current = true;
    setEndedAtMs(Date.now());
  };

  const endingRef = useRef(false);

  useEffect(() => {
    if (endedAtMs == null) return;
    const session = {
      messages,
      form,
      services,
      dispatched: dispatchedAtMs != null,
      dispatchedAtMs,
      endedAtMs,
      answerLatencySec: answeredAtRef.current ? (answeredAtRef.current - startedAtRef.current) / 1000 : null,
      call: scenario.data.call,
    };
    const result = computeDraftResult(session, scenario.data, rubric.data, user);
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(result));
    } catch {
      /* ignore */
    }
    navigate('/results', { state: { result, scenario: scenario.data } });
  }, [endedAtMs]);

  const handleRestart = () => {
    window.location.reload();
  };

  if (scenario.loading || rubric.loading) {
    return (
      <div className="app-shell">
        <AppHeader />
        <LoadingSpinner label="Подготовка рабочего места…" />
      </div>
    );
  }
  if (scenario.error || rubric.error) {
    return (
      <div className="app-shell">
        <AppHeader />
        <ErrorBanner message={scenario.error ?? rubric.error} onRetry={window.location.reload} />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content sim-content">
          <header className="sim-head">
            <div>
              <h1>{scenario.data.title}</h1>
              <p>Категория: {scenario.data.category} · Требуемые службы: {scenario.data.expected.expected_services.join(', ')}</p>
            </div>
            <CallTimer startedAtMs={startedAtRef.current} answeredAtMs={answeredAtRef.current} />
          </header>

          <div className="sim-top">
            <CallInfoPanel scenario={scenario.data} status={status} callerKnown={false} />
          </div>

          <div className="sim-workspace">
            <div className="sim-left">
              <CallFeed messages={messages} connected={status !== 'ringing'} />
              <div className="sim-composer">
                <ChatInput value={input} onChange={setInput} onSend={handleSend} disabled={status !== 'connected'} />
                <QuickReplyPanel quickReplies={scenario.data.quick_replies} onInsert={handleInsertQuick} disabled={status !== 'connected'} />
              </div>
            </div>

            <aside className="sim-right">
              <ChecklistProgress groups={groups} total={totalLive} />
              <DispatchPanel scenario={scenario.data} selected={services} onToggle={handleToggleService} disabled={!!dispatchedAtMs} />
              <IncidentForm scenario={scenario.data} values={form} onChange={(fieldId, v) => setForm((prev) => ({ ...prev, [fieldId]: v }))} disabled={!!endedAtMs} />
            </aside>
          </div>

          <ActionBar
            status={status}
            dispatched={dispatchedAtMs != null}
            servicesSelected={services.length > 0}
            onAnswer={handleAnswer}
            onDispatch={handleDispatch}
            onEnd={handleEnd}
            onRestart={handleRestart}
          />
        </main>
      </div>

      {toast && (
        <div className="toast" role="status">
          {toast}
          <button type="button" className="toast-close" onClick={() => setToast(null)}>
            ×
          </button>
        </div>
      )}
    </div>
  );
}