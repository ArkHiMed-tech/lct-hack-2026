import { useEffect, useRef } from 'react';

export default function ChatInput({ value, onChange, onSend, disabled }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (!disabled) textareaRef.current?.focus();
  }, [disabled]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSend();
    }
  };

  return (
    <div className="chat-input-wrap">
      <textarea
        ref={textareaRef}
        className="chat-input"
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={disabled ? 'После ответа на вызов ввод доступен' : 'Введите ответ (Enter — отправить)'}
      />
      <button
        type="button"
        className="btn btn-primary chat-send"
        onClick={onSend}
        disabled={disabled || !value.trim()}
      >
        Отправить
      </button>
    </div>
  );
}