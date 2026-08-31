import React, { useState, useEffect } from 'react';
import './HardwareWidget.css';

export default function HardwareWidget({ metrics = { cpu: 0, ram: 0, ping: 0 } }) {
  const [battery, setBattery] = useState({ level: 62, charging: true });
  const [network, setNetwork] = useState({ online: navigator.onLine, type: '4G' });
  const [btStatus, setBtStatus] = useState('READY');

  useEffect(() => {
    if (navigator.getBattery) {
      navigator.getBattery().then(batt => {
        const update = () => setBattery({
          level: Math.round(batt.level * 100),
          charging: batt.charging
        });
        update();
        batt.addEventListener('levelchange', update);
        batt.addEventListener('chargingchange', update);
        return () => {
          batt.removeEventListener('levelchange', update);
          batt.removeEventListener('chargingchange', update);
        };
      });
    }
  }, []);

  useEffect(() => {
    const updateNet = () => {
      const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      setNetwork({
        online: navigator.onLine,
        type: conn ? (conn.effectiveType || '4G').toUpperCase() : '4G'
      });
    };
    updateNet();
    window.addEventListener('online', updateNet);
    window.addEventListener('offline', updateNet);
    return () => {
      window.removeEventListener('online', updateNet);
      window.removeEventListener('offline', updateNet);
    };
  }, []);

  return (
    <div className="hw-card-2x2">
      <div className="hw-header-2x2">
        <span className="hw-title-2x2">SYSTEM STATUS</span>
      </div>

      <div className="hw-grid-2x3">
        {/* Cell 1: CPU */}
        <div className="hw-cell">
          <div className="hw-icon-wrapper">
            <span className="hw-icon-svg batt-icon">⚙️</span>
          </div>
          <div className="hw-cell-info">
            <span className="hw-cell-label">CPU CORE</span>
            <div className="hw-cell-val" style={{color: metrics.cpu > 80 ? '#ff3366' : '#00ff88'}}>
              {metrics.cpu.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Cell 2: RAM */}
        <div className="hw-cell">
          <div className="hw-icon-wrapper">
            <span className="hw-icon-svg net-icon">🧠</span>
          </div>
          <div className="hw-cell-info">
            <span className="hw-cell-label">MEMORY</span>
            <div className="hw-cell-val" style={{color: metrics.ram > 85 ? '#ffb020' : '#cce0ff'}}>
              {metrics.ram.toFixed(1)}%
            </div>
          </div>
        </div>
        
        {/* Cell 3: Latency */}
        <div className="hw-cell">
          <div className="hw-icon-wrapper">
            <span className="hw-icon-svg net-icon">🌐</span>
          </div>
          <div className="hw-cell-info">
            <span className="hw-cell-label">LATENCY</span>
            <div className="hw-cell-val" style={{color: metrics.ping > 150 ? '#ffb020' : '#00ff88'}}>
              {metrics.ping}ms
            </div>
          </div>
        </div>

        {/* Cell 4: Battery */}
        <div className="hw-cell">
          <div className="hw-icon-wrapper">
            <span className="hw-icon-svg batt-icon">🔌</span>
          </div>
          <div className="hw-cell-info">
            <span className="hw-cell-label">BATTERY</span>
            <div className="hw-cell-val">
              {battery.level}% <span className="hw-flash">{battery.charging ? '⚡' : ''}</span>
            </div>
          </div>
        </div>

        {/* Cell 5: Network */}
        <div className="hw-cell">
          <div className="hw-icon-wrapper">
            <span className="hw-icon-svg net-icon">📶</span>
          </div>
          <div className="hw-cell-info">
            <span className="hw-cell-label">NETWORK</span>
            <div className="hw-cell-val" style={{color: network.online ? '#0066FF' : '#ff2d55'}}>
              {network.online ? 'ONLINE' : 'OFFLINE'}
            </div>
          </div>
        </div>

        {/* Cell 6: Bluetooth */}
        <div className="hw-cell">
          <div className="hw-icon-wrapper">
            <span className="hw-icon-svg bt-icon" style={{color: '#0066FF', textShadow: '0 0 8px #0066FF'}}>ᛒ</span>
          </div>
          <div className="hw-cell-info">
            <span className="hw-cell-label">BLUETOOTH</span>
            <div className="hw-cell-val" style={{color: '#0066FF'}}>{btStatus}</div>
          </div>
        </div>

      </div>
    </div>
  );
}
