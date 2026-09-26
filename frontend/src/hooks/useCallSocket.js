import { useCallback, useEffect, useRef, useState } from 'react';

function wsUrl(path) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}

// Клиент WS звонка с заделом под эмуляцию ASR/TTS:
// - start при open, очередь send до open, состояния для UI,
// - sendAudio/sendText — точки под будущие чанки микрофона и реплики,
// - onMessage — точка под asr_partial/asr_final/tts_chunk.
export default function useCallSocket({ onServerMessage } = {}) {
  const socketRef = useRef(null);
  const pendingRef = useRef([]);
  const sessionRef = useRef(null);
  const onServerMessageRef = useRef(onServerMessage);
  const [state, setState] = useState('idle'); // idle | connecting | live | closed | error
  const [lastMessage, setLastMessage] = useState(null);

  useEffect(() => {
    onServerMessageRef.current = onServerMessage;
  }, [onServerMessage]);

  const flush = useCallback(() => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    while (pendingRef.current.length) socket.send(pendingRef.current.shift());
  }, []);

  const sendSafe = useCallback((obj) => {
    const str = JSON.stringify(obj);
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(str);
    else pendingRef.current.push(str);
  }, []);

  const connect = useCallback(
    (sessionId) => {
      const opened = socketRef.current;
      if (opened && [WebSocket.OPEN, WebSocket.CONNECTING].includes(opened.readyState)) {
        return sessionRef.current;
      }
      const id = sessionId || `demo-session-${Date.now().toString(36)}`;
      sessionRef.current = id;
      setState('connecting');
      const socket = new WebSocket(wsUrl('/api/connection/call'));
      socketRef.current = socket;

      socket.onopen = () => {
        setState('live');
        socket.send(JSON.stringify({ type: 'start', session_id: id }));
        flush();
      };
      socket.onmessage = (event) => {
        let msg = null;
        try {
          msg = JSON.parse(event.data);
        } catch {
          msg = { type: 'raw', data: event.data };
        }
        setLastMessage(msg);
        onServerMessageRef.current?.(msg);
      };
      socket.onerror = () => setState('error');
      socket.onclose = () => setState((s) => (s === 'live' || s === 'connecting' ? 'closed' : s));
      return id;
    },
    [flush],
  );

  // Будущий поток микрофона -> ASR: слать только после live.
  const sendAudio = useCallback(
    (chunk) => {
      if (!sessionRef.current) return;
      sendSafe({ type: 'audio', session_id: sessionRef.current, chunk });
    },
    [sendSafe],
  );

  // Будущие текстовые реплики оператора в голосовой канал.
  const sendText = useCallback(
    (text) => {
      if (!sessionRef.current) return;
      sendSafe({ type: 'operator_text', session_id: sessionRef.current, text });
    },
    [sendSafe],
  );

  const disconnect = useCallback(() => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN && sessionRef.current) {
      try {
        socket.send(JSON.stringify({ type: 'end', session_id: sessionRef.current }));
      } catch {
        /* ignore */
      }
    }
    try {
      socket?.close();
    } catch {
      /* ignore */
    }
    socketRef.current = null;
    pendingRef.current = [];
    setState('closed');
  }, []);

  useEffect(() => () => socketRef.current?.close(), []);

  return { state, lastMessage, sendAudio, sendText, connect, disconnect };
}
