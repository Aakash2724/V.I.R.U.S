import React from 'react';
import './Terminal.css';

const STATUS_MODE = {
  idle: { label: 'STANDBY', color: '#0066FF' },
  listening: { label: 'LISTENING', color: '#0066FF' },
  processing: { label: 'THINKING', color: '#0066FF' },
  speaking: { label: 'SPEAKING', color: '#0066FF' },
  disconnected: { label: 'OFFLINE', color: '#0066FF' },
};

export default function Terminal({
  color = '#0066FF',
  transcript = '',
  interim = '',
  llmReply = '',
  status = 'idle',
  style = {},
  onPointerDown,
  onSendMessage,
}) {
  const [typedInput, setTypedInput] = React.useState('');
  const hasTranscript = !!transcript || !!interim;
  const hasReply = !!llmReply;
  const mode = STATUS_MODE[status] || STATUS_MODE.idle;
  const glowColor = color;

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && typedInput.trim()) {
      onSendMessage?.(typedInput.trim());
      setTypedInput('');
    }
  };

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '100%', ...style }}
      onPointerDown={onPointerDown}
    >
      {/* First Box: User Transcript */}
      <div
        className="terminal-container"
        style={{
          borderColor: hasTranscript ? `${glowColor}44` : 'rgba(0,102,255,0.15)',
          boxShadow: hasTranscript
            ? `0 0 0 1px ${glowColor}18, 0 20px 70px rgba(0,0,0,0.85), inset 0 0 30px ${glowColor}08`
            : undefined,
        }}
      >
        <div className="terminal-header">
          <span
            className="terminal-header-dot"
            style={{
              backgroundColor: mode.color,
              color: mode.color,
              boxShadow: `0 0 8px ${mode.color}`,
            }}
          />
          <span className="terminal-header-title">SYSTEM_LOG // USER_INPUT</span>
          <span
            className="terminal-header-mode"
            style={{ color: mode.color, borderColor: `${mode.color}40` }}
          >
            {mode.label}
          </span>
        </div>
        <div className="terminal-body" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {transcript && (
            <div
              className="terminal-text speech"
              style={{ color: '#00d2ff', textShadow: '0 0 10px rgba(0, 210, 255, 0.6)', fontSize: '13px' }}
            >
              {transcript}
            </div>
          )}
          {interim && (
            <div
              className="terminal-text speech-interim"
              style={{ color: '#00f3c8', fontStyle: 'italic', opacity: 0.85, fontSize: '13px' }}
            >
              {interim}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
            <span style={{ color: '#00f3c8', fontWeight: 'bold' }}>{'>'}</span>
            <input
              type="text"
              value={typedInput}
              onChange={(e) => setTypedInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Speak aloud or type a command..."
              style={{
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#00f3c8',
                fontFamily: 'inherit',
                fontSize: '14px',
                flex: 1,
              }}
            />
          </div>
        </div>
      </div>

      {/* Second Box: AI Response */}
      <div
        className="terminal-container"
        style={{
          borderColor: hasReply ? `${glowColor}44` : 'rgba(0,102,255,0.15)',
          boxShadow: hasReply
            ? `0 0 0 1px ${glowColor}18, 0 20px 70px rgba(0,0,0,0.85), inset 0 0 30px ${glowColor}08`
            : undefined,
        }}
      >
        <div className="terminal-header">
          <span
            className="terminal-header-dot"
            style={{
              backgroundColor: mode.color,
              color: mode.color,
              boxShadow: `0 0 8px ${mode.color}`,
            }}
          />
          <span className="terminal-header-title">SYSTEM_LOG // V.I.R.U.S.</span>
        </div>
        <div className="terminal-body">
          <div
            className="terminal-prompt"
            style={{
              color: hasReply ? '#00f3c8' : 'rgba(0,243,200,0.3)',
              textShadow: hasReply ? '0 0 12px #00f3c8' : 'none',
            }}
          >
            {'>'}
          </div>
          <div className="terminal-text-area" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {hasReply && (
              <span
                className="terminal-text ai-text"
                style={{ color: '#00f3c8', textShadow: '0 0 10px rgba(0, 243, 200, 0.6)' }}
              >
                {llmReply}
              </span>
            )}
          </div>
          <div
            className="terminal-cursor"
            style={{
              backgroundColor: '#00f3c8',
              boxShadow: `0 0 10px #00f3c8`,
              opacity: status === 'speaking' ? 1 : 0.15,
            }}
          />
        </div>
      </div>
    </div>
  );
}
