import React from 'react';
import './SettingsPanel.css';

export default function SettingsPanel({ 
  settings, 
  updateSetting, 
  toggleBlobDrag, 
  isBlobDraggable,
  toggleTerminalDrag,
  isTerminalDraggable 
}) {
  
  // Format numeric values securely for display
  const sizeDisplay = Number(settings.size) || 300;
  const terminalSizeDisplay = Number(settings.terminalSize) || 65;

  return (
    <div className="settings-panel futuristic-glass">
      
      <div className="settings-body">
        
        {/* Blob Size Option */}
        <div className="setting-block">
          <div className="setting-title">BLOB SIZE: {sizeDisplay}PX</div>
          <input 
            type="range" 
            min="100" max="800" 
            value={sizeDisplay} 
            onChange={(e) => updateSetting('size', parseInt(e.target.value))}
            className="styled-range"
          />
        </div>

        <hr style={{width: '100%', borderColor: 'rgba(255,255,255,0.1)', margin: '14px 0'}} />

        {/* Terminal Size Option */}
        <div className="setting-block">
          <div className="setting-title">TERM WIDTH: {terminalSizeDisplay}%</div>
          <input 
            type="range" 
            min="30" max="100" 
            value={terminalSizeDisplay} 
            onChange={(e) => updateSetting('terminalSize', parseInt(e.target.value))}
            className="styled-range"
          />
        </div>

        <div style={{ marginTop: '20px', fontSize: '0.65rem', color: 'rgba(0, 243, 200, 0.5)', textAlign: 'center', letterSpacing: '0.1em' }}>
          TIP: RIGHT CLICK ANY WIDGET (INCLUDING THE BLOB) TO MOVE IT
        </div>
        
        {/* Hidden Emergency Reset */}
        <button 
           className="emergency-reset-btn"
           title="Emergency Reset Coordinates"
           onClick={() => {
              localStorage.removeItem('virus-blob-settings');
              window.location.reload();
           }}
        >
          RESET
        </button>

      </div>
    </div>
  );
}
