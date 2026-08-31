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
}) {
  const hasTranscript = !!transcript;
  const hasReply = !!llmReply;
  const mode = STATUS_MODE[status] || STATUS_MODE.idle;
  const glowColor = color;

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
        <div className="terminal-body">
          <div
            className="terminal-prompt"
            style={{
              color: hasTranscript ? '#ff2d55' : 'rgba(255,45,85,0.3)',
              textShadow: hasTranscript ? '0 0 12px #ff2d55' : 'none',
            }}
          >
            {'>'}
          </div>
          <div className="terminal-text-area" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {hasTranscript && (
              <span
                className="terminal-text speech"
                style={{ color: '#0066FF', textShadow: '0 0 10px rgba(0, 102, 255, 0.6)' }}
              >
                {transcript}
              </span>
            )}
          </div>
          <div
            className="terminal-cursor"
            style={{
              backgroundColor: glowColor,
              boxShadow: `0 0 10px ${glowColor}`,
              opacity: (status === 'listening' || hasTranscript) ? 1 : 0.15,
            }}
          />
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
