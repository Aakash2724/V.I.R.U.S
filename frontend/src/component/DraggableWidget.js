import React, { useState, useEffect, useRef, useCallback } from 'react';
import './DraggableWidget.css';

/**
 * DraggableWidget — universal right-click to Move/Save wrapper.
 *
 * Positions are auto-saved to localStorage on mount and after every drag,
 * so they persist across page refreshes.
 * Right-click → "Move" option (drag, then auto-saves on mouse-up)
 * Right-click while moving → "Save" to lock, or continue
 */
export default function DraggableWidget({
  id,
  defaultPos,   // { x, y } in pixels — fallback if nothing in localStorage
  zIndex = 200,
  children,
}) {
  /* ── Position state — load from localStorage, else defaultPos ── */
  const [pos, setPos] = useState(() => {
    try {
      const s = localStorage.getItem(`vw-pos-${id}`);
      if (s) return JSON.parse(s);
    } catch (_) {}
    return defaultPos || null;  // null = CSS handles initial position
  });

  const [isMoving,     setIsMoving]     = useState(false);
  const [menu,         setMenu]         = useState(null);  // { x, y } or null
  const pickupOffset   = useRef({ x: 0, y: 0 });
  const wrapRef        = useRef(null);

  /* ── Auto-persist defaultPos on mount if nothing was stored ─── */
  useEffect(() => {
    if (!defaultPos) return;
    const stored = localStorage.getItem(`vw-pos-${id}`);
    if (!stored) {
      localStorage.setItem(`vw-pos-${id}`, JSON.stringify(defaultPos));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);  // run once on mount

  /* ── Right-click → open context menu ──────────────────────── */
  const onContextMenu = useCallback(e => {
    e.preventDefault();
    e.stopPropagation();
    setMenu({ x: e.clientX, y: e.clientY });
  }, []);

  /* ── "Move" clicked ─────────────────────────────────────────── */
  const handleMove = useCallback(e => {
    e.stopPropagation();
    const rect = wrapRef.current?.getBoundingClientRect();
    if (rect) {
      // Offset from the click position inside the widget
      const cx = menu?.x ?? rect.left + rect.width  / 2;
      const cy = menu?.y ?? rect.top  + rect.height / 2;
      pickupOffset.current = { x: cx - rect.left, y: cy - rect.top };
      // Anchor current pixel position so widget doesn't jump
      setPos({ x: rect.left, y: rect.top });
    }
    setMenu(null);
    setIsMoving(true);
  }, [menu]);

  /* ── "Save" clicked ─────────────────────────────────────────── */
  const handleSave = useCallback(e => {
    e.stopPropagation();
    const rect = wrapRef.current?.getBoundingClientRect();
    const finalPos = rect
      ? { x: rect.left, y: rect.top }
      : pos;
    if (finalPos) {
      localStorage.setItem(`vw-pos-${id}`, JSON.stringify(finalPos));
      setPos(finalPos);
    }
    setIsMoving(false);
    setMenu(null);
  }, [id, pos]);

  /* ── Follow cursor while moving & auto-save on mouse-up ─────── */
  useEffect(() => {
    if (!isMoving || menu) return;
    const onMove = e => {
      const rect = wrapRef.current?.getBoundingClientRect();
      if (!rect) return;
      const newX = Math.max(0, Math.min(window.innerWidth  - rect.width,  e.clientX - pickupOffset.current.x));
      const newY = Math.max(0, Math.min(window.innerHeight - rect.height, e.clientY - pickupOffset.current.y));
      setPos({ x: newX, y: newY });
    };
    const onUp = () => {
      // Auto-save position when the user releases the mouse
      const rect = wrapRef.current?.getBoundingClientRect();
      if (rect) {
        const finalPos = { x: rect.left, y: rect.top };
        localStorage.setItem(`vw-pos-${id}`, JSON.stringify(finalPos));
        setPos(finalPos);
      }
      setIsMoving(false);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup',   onUp);
    };
  }, [isMoving, menu, id]);

  /* ── Close menu on outside click ─────────────────────────────── */
  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    const t = setTimeout(() => window.addEventListener('click', close, { once: true }), 60);
    return () => { clearTimeout(t); window.removeEventListener('click', close); };
  }, [menu]);

  /* ── Position style ─────────────────────────────────────────── */
  const posStyle = pos
    ? { position: 'fixed', left: pos.x, top: pos.y,
        right: 'auto', bottom: 'auto', transform: 'none' }
    : {};

  /* ── Clamp menu to viewport ─────────────────────────────────── */
  const menuStyle = menu ? {
    left: Math.min(menu.x, window.innerWidth  - 180),
    top:  Math.min(menu.y, window.innerHeight - 120),
  } : {};

  return (
    <>
      <div
        ref={wrapRef}
        onContextMenu={onContextMenu}
        className={`dw-wrap ${isMoving ? 'dw-moving' : ''}`}
        style={{
          ...posStyle,
          zIndex: isMoving ? 9990 : zIndex,
          cursor: isMoving ? 'grabbing' : 'default',
        }}
      >
        {/* Moving indicator ring */}
        {isMoving && <div className="dw-move-ring" />}
        {children}
      </div>

      {/* Context menu */}
      {menu && (
        <div
          className="dw-ctx-menu"
          style={menuStyle}
          onContextMenu={e => e.preventDefault()}
        >
          <div className="dw-ctx-title">WIDGET CONTROL</div>
          <div className="dw-ctx-divider" />

          {/* Move — always available */}
          <button className="dw-ctx-item" onClick={handleMove}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M6 1v10M1 6h10M4 3l-3 3 3 3M8 3l3 3-3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            {isMoving ? 'Moving… (drag)' : 'Move'}
          </button>

          {/* Save Position — ALWAYS visible so user can lock any position */}
          <button className="dw-ctx-item dw-ctx-save" onClick={handleSave}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 6.5l3 3 5-6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Save Position
          </button>

          <div className="dw-ctx-divider" />

          {/* Reset to default — always available */}
          <button className="dw-ctx-item dw-ctx-reset"
            onClick={e => {
              e.stopPropagation();
              localStorage.removeItem(`vw-pos-${id}`);
              setPos(defaultPos || null);
              setIsMoving(false);
              setMenu(null);
            }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M10 2L2 10M2 2l8 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            Reset to Default
          </button>
        </div>
      )}
    </>
  );
}
