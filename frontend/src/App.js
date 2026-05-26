import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Records from './pages/Records';
import Ingest from './pages/Ingest';
import LoginPage from './pages/Login';
import './index.css';

function Layout({ children, onLogout }) {
  const loc = useLocation();
  const nav = [
    { path: '/', label: 'Dashboard', icon: '◈' },
    { path: '/records', label: 'Records', icon: '≡' },
    { path: '/ingest', label: 'Ingest', icon: '↑' },
  ];
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside style={{
        width: 200, background: 'var(--bg2)', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', padding: '24px 0', flexShrink: 0
      }}>
        <div style={{ padding: '0 20px 24px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontFamily: 'var(--font-head)', fontSize: 18, fontWeight: 800,
            color: 'var(--green)', letterSpacing: '-0.5px' }}>BREATHE</div>
          <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 2 }}>ESG PLATFORM</div>
        </div>
        <nav style={{ flex: 1, padding: '16px 12px' }}>
          {nav.map(n => (
            <Link key={n.path} to={n.path} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
              borderRadius: 6, marginBottom: 2, textDecoration: 'none',
              color: loc.pathname === n.path ? 'var(--green)' : 'var(--text2)',
              background: loc.pathname === n.path ? 'var(--green-dim)' : 'transparent',
              fontWeight: loc.pathname === n.path ? 500 : 400,
              border: loc.pathname === n.path ? '1px solid #2a5a3a' : '1px solid transparent',
              transition: 'all 0.15s',
            }}>
              <span style={{ fontSize: 16 }}>{n.icon}</span>
              <span style={{ fontSize: 12 }}>{n.label}</span>
            </Link>
          ))}
        </nav>
        <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
          <div style={{ color: 'var(--text3)', fontSize: 11, marginBottom: 8 }}>
            Acme Manufacturing Ltd
          </div>
          <button className="btn-ghost" style={{ width: '100%', fontSize: 11 }}
            onClick={onLogout}>Sign out</button>
        </div>
      </aside>
      <main style={{ flex: 1, overflow: 'auto' }}>{children}</main>
    </div>
  );
}

function App() {
  const [authed, setAuthed] = useState(!!localStorage.getItem('auth_token'));

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setAuthed(false);
  };

  if (!authed) return <LoginPage onLogin={() => setAuthed(true)} />;

  return (
    <BrowserRouter>
      <Layout onLogout={handleLogout}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/records" element={<Records />} />
          <Route path="/ingest" element={<Ingest />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
