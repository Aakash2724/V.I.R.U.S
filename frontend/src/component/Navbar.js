import React from 'react';
import './Navbar.css';

export default function Navbar({ showSettings, toggleSettings }) {
  return (
    <div className="navbar-frame">
      <nav className="futuristic-navbar">
        {/* Logo */}
        <div className="navbar-logo">
          <span className="logo-text">V.I.R.U.S.</span>
        </div>

        {/* Nav links */}
        <div className="navbar-links">
          <a href="#home"      className="nav-link">HOME</a>
          <a href="#dashboard" className="nav-link">DASHBOARD</a>
          <a
            href="#settings"
            className={`nav-link ${showSettings ? 'active' : ''}`}
            onClick={(e) => { e.preventDefault(); if (toggleSettings) toggleSettings(); }}
          >
            SETTINGS
          </a>
          <a href="#about" className="nav-link">ABOUT</a>
        </div>
      </nav>
    </div>
  );
}
