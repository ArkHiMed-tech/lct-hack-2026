import { useEffect, useState } from 'react';

function fmt(totalMs) {
  const s = Math.floor(totalMs / 1000);
  const m = Math.floor(s / 60);
  const ss = String(s % 60).padStart(2, '0');
  return `${String(m).padStart(2, '0')}:${ss}`;
}

export default function CallTimer({ startedAtMs, answeredAtMs }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);

  const base = startedAtMs ?? now;
  const waiting = answeredAtMs == null;
  const elapsed = Math.max(0, (waiting ? now - base : now - answeredAtMs));
  const breached = waiting && answeredAtMs == null && elapsed > 8000;

  return (
    <div className={`call-timer ${breached ? 'is-breached' : ''}`}>
      <div className="call-timer-clock">{fmt(elapsed)}</div>
      <div className="call-timer-label">
        {waiting ? (breached ? 'Нужно ответить!' : 'Время до ответа') : 'Время разговора'}
      </div>
    </div>
  );
}