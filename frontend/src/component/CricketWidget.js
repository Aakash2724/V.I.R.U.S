import React from 'react';
import './CricketWidget.css';

export default function CricketWidget({ data = { active: false, msg: "Fetching..." } }) {
  if (!data.active) {
    return (
      <div className="cricket-card">
        <div className="cricket-header">
          <span className="cricket-title">CRIC_SCORES</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60px' }}>
          <div style={{ color: 'rgba(204, 224, 255, 0.5)', fontSize: '0.9rem', letterSpacing: '0.05em', textTransform: 'uppercase', fontFamily: '"JetBrains Mono", monospace' }}>
            {data.msg || "NO MATCHES RIGHT NOW"}
          </div>
        </div>
      </div>
    );
  }

  const status    = data.status || "LIVE";
  const matchName = data.match  || "";
  const scoreText = data.score  || "";
  const batsmen   = data.batsmen || "";
  const bowler    = data.bowler || "";

  // Split "Team A vs Team B" for display
  const vsParts = matchName.split(/\s+vs\s+/i);
  const team1   = vsParts[0]?.trim() || matchName;
  const team2   = vsParts[1]?.trim() || "";

  const statusColor = {
    LIVE:     "#ff4d6d",
    UPCOMING: "#00cfff",
    RESULT:   "#a5d6a7",
  }[status] || "#00ff9d";

  return (
    <div className="cricket-card">
      <div className="cricket-header">
        <span className="cricket-title">CRIC_SCORES</span>
        <span
          className="cricket-live-badge"
          style={{
            background: statusColor,
            color: "#000",
            fontSize: '0.6rem',
            padding: '2px 6px',
            borderRadius: '3px',
            fontWeight: 700,
            letterSpacing: '0.08em',
            animation: status === "LIVE" ? "pulseGlow 1.5s infinite" : "none",
          }}
        >
          {status}
        </span>
      </div>

      <div className="cricket-teams" style={{ marginTop: '10px' }}>
        <span
          className="cricket-team"
          style={{ fontSize: team1.length > 18 ? '0.72rem' : '0.9rem', textAlign: 'center', fontWeight: 600 }}
        >
          {team1}
        </span>
        {team2 && <span className="cricket-vs" style={{ fontSize: '0.7rem', opacity: 0.6 }}>VS</span>}
        <span
          className="cricket-team"
          style={{ fontSize: team2.length > 18 ? '0.72rem' : '0.9rem', textAlign: 'center', fontWeight: 600 }}
        >
          {team2}
        </span>
      </div>

      <div
        className="cricket-score-row"
        style={{
          marginTop: '10px',
          color: '#00ff9d',
          textShadow: '0 0 8px rgba(0,255,157,0.5)',
          fontSize: '1rem',
          textAlign: 'center',
          fontFamily: '"JetBrains Mono", monospace',
          letterSpacing: '0.05em',
          wordBreak: 'break-word',
          padding: '0 6px',
        }}
      >
        {scoreText}
      </div>

      {(batsmen || bowler) && status === "LIVE" && (
        <div style={{ 
          marginTop: '12px', 
          padding: '8px 10px', 
          background: 'rgba(0, 0, 0, 0.3)', 
          borderRadius: '6px', 
          border: '1px solid rgba(0, 255, 157, 0.15)',
          fontSize: '0.75rem', 
          fontFamily: '"JetBrains Mono", monospace' 
        }}>
          {batsmen && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: bowler ? '6px' : '0' }}>
              <span style={{ color: 'rgba(255, 255, 255, 0.5)' }}>BAT</span>
              <span style={{ color: '#fff', fontWeight: 500, textAlign: 'right', maxWidth: '75%', wordBreak: 'break-word' }}>{batsmen}</span>
            </div>
          )}
          {bowler && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'rgba(255, 255, 255, 0.5)' }}>BOWL</span>
              <span style={{ color: '#00cfff', fontWeight: 500, textAlign: 'right', maxWidth: '75%', wordBreak: 'break-word' }}>{bowler}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
