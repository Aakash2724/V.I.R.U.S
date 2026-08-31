import React, { useState, useEffect } from 'react';
import './TodoWidget.css';

export default function TodoWidget() {
  const [tasks, setTasks] = useState(() => {
    try {
      const saved = localStorage.getItem('virus-todo');
      if (saved) return JSON.parse(saved);
    } catch (_) {}
    return [
      { id: 1, text: "Review Phase 2 Deploy", done: false },
      { id: 2, text: "Compile backend protocols", done: true }
    ];
  });
  
  const [inputText, setInputText] = useState("");

  useEffect(() => {
    localStorage.setItem('virus-todo', JSON.stringify(tasks));
  }, [tasks]);

  const addTask = (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    setTasks([...tasks, { id: Date.now(), text: inputText.trim(), done: false }]);
    setInputText("");
  };

  const toggleTask = (id) => {
    setTasks(tasks.map(t => t.id === id ? { ...t, done: !t.done } : t));
  };

  const removeTask = (id) => {
    setTasks(tasks.filter(t => t.id !== id));
  };

  return (
    <div className="todo-widget">
      <div className="todo-header">
        <span className="todo-title">TERMINAL TASKS</span>
      </div>
      
      <div className="todo-list">
        {tasks.map(task => (
          <div key={task.id} className={`todo-item ${task.done ? 'done' : ''}`}>
            <div className="todo-checkbox" onClick={() => toggleTask(task.id)}>
              {task.done && <div className="todo-checkbox-inner" />}
            </div>
            <span className="todo-text" onClick={() => toggleTask(task.id)}>{task.text}</span>
            <button className="todo-delete" onClick={() => removeTask(task.id)}>×</button>
          </div>
        ))}
      </div>

      <form className="todo-form" onSubmit={addTask}>
        <span className="todo-prompt">{">"}</span>
        <input 
          type="text" 
          placeholder="New task..." 
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          className="todo-input"
        />
      </form>
    </div>
  );
}
