import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import Navbar           from './component/Navbar';
import PlasmaBlob       from './component/blob';
import SettingsPanel    from './component/SettingsPanel';
import Terminal         from './component/Terminal';
import StatusPanel      from './component/StatusPanel';
import SystemInfoWidget from './component/SystemInfoWidget';
import CentralHUD       from './component/CentralHUD';
import DraggableWidget  from './component/DraggableWidget';
import HardwareWidget   from './component/HardwareWidget';
import LocationWidget   from './component/LocationWidget';
import ActivityMonitor  from './component/ActivityMonitor';
import GreetingWidget   from './component/GreetingWidget';
import CricketWidget    from './component/CricketWidget';
import useVirusSocket   from './hooks/useVirusSocket';

/* ── Blob-specific defaults (centered + 500px) ────────────────── */
const DEFAULT_SETTINGS = {
  color: '#00f3c8',
  size: 500,
  sensitivity: 2.8,
  position: { x: 0, y: 0 },      // centered
  terminalPosition: { x: 0, y: 0 },
  terminalSize: 30,
};

/* ── Fixed pixel positions — matched to screenshot layout ─────── */
/*    Bump LAYOUT_VERSION to force a one-time reset to new defaults */
const DEFAULT_WIDGET_POS = {
  // Left column
  location: { x: 20,  y: 75  },
  hardware: { x: 215, y: 75  },
  activity: { x: 20,  y: 207 },
  cricket:  { x: 20,  y: 415 },

  // Right column
  status:   { x: 827, y: 75  },
  sysinfo:  { x: 827, y: 234 },

  // Bottom strip
  greeting: { x: 407, y: 413 },
  terminal: { x: 680, y: 413 },
};

/* ── One-time layout reset (bump version string to re-snap positions) */
const LAYOUT_VERSION = 'vw-layout-v3';
(function snapToDefaultPositions() {
  if (!localStorage.getItem(LAYOUT_VERSION)) {
    // Wipe old stored positions so the hardcoded defaults take effect
    Object.keys(localStorage)
      .filter(k => k.startsWith('vw-pos-'))
      .forEach(k => localStorage.removeItem(k));
    localStorage.setItem(LAYOUT_VERSION, '1');
  }
})();


function App() {
  /* ── Blob settings (use v5 key — new centered defaults) ─────── */
  const [blobSettings, setBlobSettings] = useState(() => {
    try {
      // Try v5 first (new centered defaults)
      const v5 = localStorage.getItem('virus-blob-state-v5');
      if (v5) {
        const p = JSON.parse(v5);
        if (p) return {
          ...DEFAULT_SETTINGS, ...p,
          position: { x: p.position?.x ?? 0, y: p.position?.y ?? 0 },
        };
      }
    } catch (_) {}
    return DEFAULT_SETTINGS;
  });

  /* ── App state ──────────────────────────────────────────────── */
  const [showSettings,    setShowSettings]    = useState(false);
  const [transcript,      setTranscript]      = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [llmReply,        setLlmReply]        = useState('');
  const [status,          setStatus]          = useState('disconnected');
  const [sysMetrics,      setSysMetrics]      = useState({ cpu: 0, ram: 0, ping: 0 });
  const [cricketData,     setCricketData]     = useState({ active: false, msg: "No matches right now" });
  const [commandCount,    setCommandCount]    = useState(0);
  const [startTime]                           = useState(() => Date.now());
  const resetNextTranscript = useRef(false);

  /* ── WebSocket ──────────────────────────────────────────────── */
  const levelRef = useVirusSocket({
    onTranscript: useCallback(({ text, isFinal }) => {
      if (resetNextTranscript.current) {
        setTranscript(''); setInterimTranscript(''); setLlmReply('');
        resetNextTranscript.current = false;
        if (isFinal) setTranscript(text);
        else         setInterimTranscript(text);
      } else {
        if (isFinal) {
          setTranscript(prev => (prev.trim() ? prev.trim() + ' ' + text : text));
          setInterimTranscript('');
          setCommandCount(c => c + 1);
        } else {
          setInterimTranscript(text);
        }
      }
    }, []),
    onReplyChunk: useCallback(chunk => setLlmReply(prev => prev + chunk), []),
    onReplyEnd:   useCallback(() => { resetNextTranscript.current = true; }, []),
    onStatus:     useCallback(s => setStatus(s), []),
    onSysMetrics: useCallback(m => setSysMetrics(m), []),
    onCricketUpdate: useCallback(data => setCricketData(data), [])
  });

  /* ── Persist blob settings ──────────────────────────────────── */
  useEffect(() => {
    localStorage.setItem('virus-blob-state-v5', JSON.stringify(blobSettings));
  }, [blobSettings]);

  const updateSetting = (key, val) =>
    setBlobSettings(prev => ({ ...prev, [key]: val }));

  /* ── Derived values ─────────────────────────────────────────── */
  const safeSize  = Number(blobSettings.size)        || 500;
  const safeColor = '#0066FF';
  const safeSens  = Number(blobSettings.sensitivity) || 1;
  const safeTermW = Number(blobSettings.terminalSize) || 44;
  const isOnline  = status !== 'disconnected';

  /* ── Tauri detection & window controls ──────────────── */
  const isTauri = typeof window !== 'undefined' && !!window.__TAURI__;
  const [isMaximized, setIsMaximized] = useState(false);

  // Use invoke for custom commands (close kills backend too)
  // Use appWindow directly for drag/minimize/maximize
  const tauriInvoke = (cmd) => {
    try { window.__TAURI__?.tauri?.invoke(cmd); } catch (_) {}
  };
  const tauriWin = () => {
    try { return window.__TAURI__?.window?.appWindow ?? null; } catch (_) { return null; }
  };

  const tauriClose    = () => { tauriInvoke('close_app');            };
  const tauriMinimize = () => { tauriWin()?.minimize();              };
  const tauriMaximize = async () => {
    const win = tauriWin();
    if (!win) return;
    const maximized = await win.isMaximized();
    maximized ? win.unmaximize() : win.maximize();
    setIsMaximized(!maximized);
  };
  const tauriDragStart= () => { tauriWin()?.startDragging();        };


  return (
    <div style={{
      height: '100vh', width: '100vw',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden', position: 'relative',
    }}>

      {/* Tauri frameless window titlebar (only visible inside the .exe) */}
      {isTauri && (
        <div className="tauri-titlebar">
          <div
            className="tauri-titlebar-drag"
            onMouseDown={tauriDragStart}
          >
            <span className="tauri-title">V.I.R.U.S.</span>
          </div>
          <div className="tauri-titlebar-btns">
            <button className="tauri-btn" onClick={tauriMinimize} title="Minimize">&#8722;</button>
            <button className="tauri-btn maximize" onClick={tauriMaximize} title={isMaximized ? 'Restore' : 'Maximize'}>
              {isMaximized ? '❐' : '&#9633;'}
            </button>
            <button className="tauri-btn close" onClick={tauriClose} title="Close V.I.R.U.S.">&#x2715;</button>
          </div>
        </div>
      )}

      {/* Navbar */}
      <Navbar
        showSettings={showSettings}
        toggleSettings={() => setShowSettings(s => !s)}
        isOnline={isOnline}
      />

      {/* ── Draggable panels ──────────────────────────────────── */}
      {/* Left side */}
      <DraggableWidget id="location-panel" defaultPos={DEFAULT_WIDGET_POS.location}>
        <LocationWidget />
      </DraggableWidget>

      <DraggableWidget id="hardware-v2" defaultPos={DEFAULT_WIDGET_POS.hardware}>
        <HardwareWidget metrics={sysMetrics} />
      </DraggableWidget>

      <DraggableWidget id="activity-monitor" defaultPos={DEFAULT_WIDGET_POS.activity}>
        <ActivityMonitor status={status} transcript={transcript} />
      </DraggableWidget>

      {/* Right side */}
      <DraggableWidget id="status-panel-v2" defaultPos={DEFAULT_WIDGET_POS.status}>
        <StatusPanel status={status} />
      </DraggableWidget>

      <DraggableWidget id="sys-info-v2" defaultPos={DEFAULT_WIDGET_POS.sysinfo}>
        <SystemInfoWidget commandCount={commandCount} startTime={startTime} />
      </DraggableWidget>

      <DraggableWidget id="cricket-score" defaultPos={DEFAULT_WIDGET_POS.cricket}>
        <CricketWidget data={cricketData} />
      </DraggableWidget>


      {/* Terminal */}
      <DraggableWidget
        id="terminal-v2"
        defaultPos={DEFAULT_WIDGET_POS.terminal}
        zIndex={100}
      >
        <Terminal
          color={safeColor}
          transcript={transcript}
          interim={interimTranscript}
          llmReply={llmReply}
          status={status}
          style={{ width: '30vw', minWidth: '280px' }}
        />
      </DraggableWidget>

      {/* Center Box */}
      <DraggableWidget id="greeting-box" defaultPos={DEFAULT_WIDGET_POS.greeting}>
        <GreetingWidget />
      </DraggableWidget>

      {/* Settings modal */}
      {showSettings && (
        <SettingsPanel
          settings={{ color: safeColor, size: safeSize,
                      sensitivity: safeSens, terminalSize: safeTermW }}
          updateSetting={updateSetting}
        />
      )}

      {/* ── Central stage: HUD + Blob ─────────────────────────── */}
      <div style={{
        flex: 1,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        pointerEvents: 'none',
      }}>

        {/* Jarvis HUD decorations (rings, clock, metrics) */}
        <CentralHUD status={status} color={safeColor} />

        {/* Plasma blob — perfectly centered originally, draggable via right-click */}
        <DraggableWidget id="central-blob" defaultPos={null} zIndex={50}>
          <div
            style={{
              position: 'relative',
              width:  `${safeSize}px`,
              height: `${safeSize}px`,
              touchAction: 'none',
              pointerEvents: 'auto',
              flexShrink: 0,
            }}
          >
            <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
              <PlasmaBlob
                key={`${safeColor}-${safeSize}`}
                sensitivity={safeSens}
                color={safeColor}
                size={safeSize}
                externalLevelRef={levelRef}
              />
            </div>
          </div>
        </DraggableWidget>
      </div>

    </div>
  );
}

export default App;
