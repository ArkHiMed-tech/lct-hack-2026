import { useEffect, useRef } from 'react';

function SpeakerName({ sender }) {
  if (sender === 'citizen') return <span className="feed-speaker feed-citizen">Абонент</span>;
  if (sender === 'operator') return <span className="feed-speaker feed-operator">Диспетчер</span>;
  return <span className="feed-speaker feed-system">Система</span>;
}

export default function CallFeed({ messages, connected }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const osHeading = !connected ? 'Вы в режиме ожидания вызова' : 'Идёт приём вызова';

  return (
    <div className="panel call-feed-wrap">
      <div className="panel-head">
        <span>{osHeading}</span>
        {!connected && <span className="feed-idle-light">◉</span>}
      </div>
      <div className="call-feed">
        {messages.length === 0 && (
          <div className="feed-empty">Реплики появятся после ответа на вызов.</div>
        )}
        {messages.map((m, i) => (
          <div
            key={`${m.seq ?? 'msg'}-${i}`}
            className={`feed-row feed-${m.sender}`}
            data-fresh={i === messages.length - 1}
          >
            <SpeakerName sender={m.sender} />
            {m.time && <span className="feed-time">{m.time}</span>}
            {m.emotion && <span className="feed-emotion">{m.emotion}</span>}
            <p>{m.text}</p>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}