import React, { useState, useEffect } from 'react';
import './SystemInfoWidget.css';

const WEATHER_ICONS = {
  Clear: '☀️', Clouds: '☁️', Rain: '🌧️', Drizzle: '🌦️',
  Thunderstorm: '⛈️', Snow: '❄️', Mist: '🌫️', Haze: '🌫️', Fog: '🌫️',
};

export default function SystemInfoWidget({ commandCount = 0, startTime }) {
  const [time, setTime]         = useState(new Date());
  const [weather, setWeather]   = useState(null);
  const [location, setLocation] = useState('Locating…');
  const [uptime, setUptime]     = useState('0m');

  /* ── Clock ─────────────────────────────────────────────────────── */
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  /* ── Uptime ─────────────────────────────────────────────────────── */
  useEffect(() => {
    const id = setInterval(() => {
      if (!startTime) return;
      const secs  = Math.floor((Date.now() - startTime) / 1000);
      const h     = Math.floor(secs / 3600);
      const m     = Math.floor((secs % 3600) / 60);
      setUptime(h > 0 ? `${h}h ${m}m` : `${m}m`);
    }, 10_000);
    return () => clearInterval(id);
  }, [startTime]);

  /* ── Geolocation + Weather ──────────────────────────────────────── */
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        const { latitude: lat, longitude: lon } = coords;
        /* Reverse geocode via open-meteo geocoding (no key needed) */
        try {
          const geo = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`
          ).then(r => r.json());
          setLocation(geo.address?.city || geo.address?.town || geo.address?.county || 'Unknown');
        } catch { setLocation('India'); }

        /* Open-Meteo weather (no API key!) */
        try {
          const wmo2label = { 0:'Clear', 1:'Clear', 2:'Partly Cloudy', 3:'Overcast',
            45:'Fog', 48:'Fog', 51:'Drizzle', 53:'Drizzle', 55:'Drizzle',
            61:'Rain', 63:'Rain', 65:'Heavy Rain', 71:'Snow', 73:'Snow', 75:'Snow',
            80:'Showers', 81:'Showers', 95:'Thunderstorm', 96:'Thunderstorm', 99:'Thunderstorm' };
          const wmo2icon = { 0:'☀️', 1:'🌤️', 2:'⛅', 3:'☁️',
            45:'🌫️', 48:'🌫️', 51:'🌦️', 53:'🌦️', 55:'🌦️',
            61:'🌧️', 63:'🌧️', 65:'🌧️', 71:'❄️', 73:'❄️', 75:'❄️',
            80:'🌦️', 81:'🌦️', 95:'⛈️', 96:'⛈️', 99:'⛈️' };

          const w = await fetch(
            `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&temperature_unit=celsius`
          ).then(r => r.json());
          const cw = w.current_weather;
          setWeather({
            temp: Math.round(cw.temperature),
            label: wmo2label[cw.weathercode] || 'Clear',
            icon: wmo2icon[cw.weathercode] || '☀️',
            wind: Math.round(cw.windspeed),
          });
        } catch { setWeather({ temp: '--', label: 'N/A', icon: '🌡️', wind: '--' }); }
      },
      () => { setLocation('India'); setWeather({ temp: '--', label: 'N/A', icon: '🌡️', wind: '--' }); }
    );
  }, []);

  const HH   = String(time.getHours()).padStart(2, '0');
  const MM   = String(time.getMinutes()).padStart(2, '0');
  const SS   = String(time.getSeconds()).padStart(2, '0');
  const days = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  const mons = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const dateStr = `${days[time.getDay()]}, ${mons[time.getMonth()]} ${time.getDate()}`;

  return (
    <div className="siw-card">
      {/* Header */}
      <div className="siw-header">
        <span className="siw-title">SYSTEM_INFO</span>
        <span className="siw-dot-pulse" />
      </div>
      <div className="siw-divider" />

      {/* Weather */}
      <div className="siw-weather-row">
        <span className="siw-weather-icon">{weather ? weather.icon : '⏳'}</span>
        <div className="siw-weather-info">
          <span className="siw-temp">{weather ? `${weather.temp}°C` : '--°C'}</span>
          <span className="siw-condition">{weather ? weather.label.toUpperCase() : 'LOADING'}</span>
          {weather && weather.wind !== '--' && (
            <span className="siw-wind">💨 {weather.wind} km/h</span>
          )}
        </div>
      </div>

      <div className="siw-divider" />

      {/* Location */}
      <div className="siw-location-row">
        <span className="siw-pin">📍</span>
        <span className="siw-location-text">{location}</span>
      </div>

      <div className="siw-divider" />

      {/* Footer stats */}
      <div className="siw-footer">
        <div className="siw-stat">
          <span className="siw-stat-label">UPTIME</span>
          <span className="siw-stat-value">{uptime}</span>
        </div>
        <div className="siw-stat siw-stat-right">
          <span className="siw-stat-label">COMMANDS</span>
          <span className="siw-stat-value">{commandCount}</span>
        </div>
      </div>
    </div>
  );
}
