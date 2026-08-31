import React, { useState, useEffect } from 'react';
import './GreetingWidget.css';

export default function GreetingWidget() {
  const [greeting, setGreeting] = useState('');

  useEffect(() => {
    const updateGreeting = () => {
      const hour = new Date().getHours();
      if (hour < 12) setGreeting('Good Morning, Sir');
      else if (hour < 17) setGreeting('Good Afternoon, Sir');
      else setGreeting('Good Evening, Sir');
    };
    updateGreeting();
    // Update every minute to catch hour transitions
    const id = setInterval(updateGreeting, 60000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="greet-card">
      <div className="greet-text">
        {greeting}
      </div>
      <div className="greet-sub">
        Monitoring all systems.
      </div>
      <div className="greet-sign">
        - V . I . R . U . S .
      </div>
    </div>
  );
}
