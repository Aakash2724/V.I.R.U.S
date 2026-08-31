import React, { useState, useEffect } from 'react';
import './CentralHUD.css';

export default function CentralHUD({ status = 'idle', color = '#00f3c8' }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const HH  = String(time.getHours()).padStart(2, '0');
  const MM  = String(time.getMinutes()).padStart(2, '0');
  const SS  = String(time.getSeconds()).padStart(2, '0');
  const days = ['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY'];
  const mons = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const dayStr  = days[time.getDay()];
  const dateStr = `${time.getDate()} ${mons[time.getMonth()]} ${time.getFullYear()}`;

  const STATUS_LABEL = {
    idle:         'STANDBY',
    listening:    'LISTENING',
    processing:   'PROCESSING',
    speaking:     'TRANSMITTING',
    disconnected: 'OFFLINE',
  };

  const c = color;

  return (
    <div className="chud-root" style={{ '--hud-color': c }}>

      {/* ── Huge ghost clock behind the blob ── */}
      <div className="chud-ghost-clock" aria-hidden="true">
        <span className="chud-ghost-hh">{HH}</span>
        <span className="chud-ghost-sep">:</span>
        <span className="chud-ghost-mm">{MM}</span>
      </div>

      {/* ── Rotating orbital rings ── */}
      <div className="chud-rings">
        {/* Inner orbit — fast CW */}
        <div className="chud-ring chud-ring-1" />
        {/* Middle orbit — slow CCW */}
        <div className="chud-ring chud-ring-2" />
        {/* Outer orbit — very slow CW */}
        <div className="chud-ring chud-ring-3" />
        {/* Accent arc */}
        <div className="chud-ring chud-ring-4" />
      </div>

      {/* ── Top data strip (above blob) ── */}
      <div className="chud-top-strip">
        <div className="chud-clock-main">
          <span className="chud-hh">{HH}</span>
          <span className="chud-colon">:</span>
          <span className="chud-mm">{MM}</span>
          <span className="chud-ss">:{SS}</span>
        </div>
        <div className="chud-date-strip">
          <span className="chud-day">{dayStr}</span>
          <span className="chud-sep-dot">·</span>
          <span className="chud-date">{dateStr}</span>
        </div>
      </div>

      {/* ── Four corner HUD marks on the viewport ── */}
      <div className="chud-corner chud-corner-tl" />
      <div className="chud-corner chud-corner-tr" />
      <div className="chud-corner chud-corner-bl" />
      <div className="chud-corner chud-corner-br" />

    </div>
  );
}
