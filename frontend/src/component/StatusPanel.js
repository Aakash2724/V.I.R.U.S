import React from 'react';
import './StatusPanel.css';

export default function StatusPanel({ status = 'disconnected' }) {
    const isOnline = status !== 'disconnected';
    
    return (
        <div className="status-container">
            <div className="status-header">
                SYS_DIAGNOSTICS
            </div>
            <div className="status-body">
                <div className="status-row">
                    <span className={`status-dot ${isOnline ? 'active' : 'inactive'}`}></span>
                    <span>V.I.R.U.S. Core: <strong style={{color: isOnline ? '#00ff88':'#ff3366'}}>{isOnline ? 'ONLINE' : 'OFFLINE'}</strong></span>
                </div>
                <div className="status-row">
                    <span className={`status-dot ${isOnline ? 'active' : 'inactive'}`}></span>
                    <span>Microphone Node: {isOnline ? 'ACTIVE' : 'MUTED'}</span>
                </div>
                <div className="status-row">
                    <span className={`status-dot ${isOnline ? 'active' : 'inactive'}`}></span>
                    <span>System Permissions: GRANTED</span>
                </div>
                <div className="status-row">
                    <span className={`status-dot ${isOnline ? 'active' : 'inactive'}`}></span>
                    <span>API Connection: {isOnline ? 'CONNECTED' : 'DISCONNECTED'}</span>
                </div>
                <div className="status-row">
                    <span className={`status-dot ${isOnline ? 'active' : 'inactive'}`}></span>
                    <span>Synthesis (TTS): {isOnline ? 'ONLINE' : 'OFFLINE'}</span>
                </div>
                <div className="status-row">
                    <span className={`status-dot ${status === 'listening' ? 'pulse' : (isOnline ? 'active' : 'inactive')}`}></span>
                    <span>Audio Interface: {status.toUpperCase()}</span>
                </div>
            </div>
        </div>
    );
}
