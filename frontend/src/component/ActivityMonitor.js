import React, { useState, useEffect } from 'react';
import './ActivityMonitor.css';

export default function ActivityMonitor({ status = 'idle', transcript = '' }) {
  const [log, setLog] = useState([]);

  // Every time status changes to something active, add it to the log
  useEffect(() => {
    if (status === 'disconnected') return;
      
    // Create new log entry
    const time = new Date();
    const hh = String(time.getHours()).padStart(2, '0');
    const mm = String(time.getMinutes()).padStart(2, '0');
    const ss = String(time.getSeconds()).padStart(2, '0');
    
    let displayStatus = 'LISTENING';
    let colorClass = 'am-status-green';
    
    if (status === 'listening') {
      displayStatus = 'LISTENING';
      colorClass = 'am-status-green';
    } else if (status === 'processing') {
      displayStatus = 'PROCESSING';
      colorClass = 'am-status-blue';
    } else if (status === 'speaking') {
      displayStatus = 'RESPONDING';
      colorClass = 'am-status-amber';
    } else {
      displayStatus = 'STANDBY';
      colorClass = 'am-status-gray';
    }
    
    if (transcript && status === 'processing') {
      setLog(prev => {
        const newLog = [...prev, { time: `${hh}:${mm}:${ss}`, text: 'COMMAND RECEIVED', colorClass: 'am-status-cyan' }];
        if (newLog.length > 6) newLog.shift();
        return newLog;
      });
    }

    setLog(prev => {
      // Don't add back-to-back duplicate log entries purely for visual clutter
      const last = prev[prev.length - 1];
      if (last && last.text === displayStatus && last.colorClass === colorClass) {
        return prev;
      }
      const newLog = [...prev, { time: `${hh}:${mm}:${ss}`, text: displayStatus, colorClass }];
      if (newLog.length > 7) newLog.shift();
      return newLog;
    });

  }, [status, transcript]);

  // Main UI display map
  const MAIN_STATE = {
    idle:         { label: 'STANDBY',      icon: '⏸️', color: 'rgba(204,224,255,0.4)' },
    listening:    { label: 'LISTENING',    icon: '👂', color: '#00f3c8' },
    processing:   { label: 'PROCESSING',   icon: '⚙️', color: '#0066FF' },
    speaking:     { label: 'RESPONDING',   icon: '🔊', color: '#ffb020' },
    disconnected: { label: 'OFFLINE',      icon: '❌', color: '#ff2d55' },
  };

  const curr = MAIN_STATE[status] || MAIN_STATE.idle;

  return (
    <div className="am-card">
      <div className="am-header">
        <span className="am-title">ACTIVITY MONITOR</span>
        <span className="am-pulse" style={{ background: curr.color, boxShadow: `0 0 8px ${curr.color}` }}></span>
      </div>

      <div className="am-current-box" style={{ 
        boxShadow: `inset 0 0 20px ${curr.color}22`,
        border: `1px solid ${curr.color}40`
      }}>
        <div className="am-curr-icon">{curr.icon}</div>
        <div className="am-curr-text" style={{ color: curr.color, textShadow: `0 0 10px ${curr.color}80` }}>
          {curr.label}
        </div>
      </div>

      <div className="am-log-list">
        {log.map((entry, i) => (
          <div key={i} className="am-log-row animate-fade-in">
            <span className="am-log-time">{entry.time}</span>
            <span className="am-log-sep">—</span>
            <span className={`am-log-text ${entry.colorClass}`}>{entry.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
