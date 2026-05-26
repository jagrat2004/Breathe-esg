import React, { useState } from 'react';
import { login } from '../services/api';

export default function LoginPage({ onLogin }) {
  const [creds, setCreds] = useState({ username: 'analyst', password: 'demo1234' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await login(creds.username, creds.password);
      onLogin();
    } catch (err) {
      setError('Invalid credentials');
    } finally { setLoading(false); }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{ width: 360 }}>
        <div style={{ marginBottom: 32, textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-head)', fontSize: 32, fontWeight: 800,
            color: 'var(--green)', letterSpacing: '-1px', marginBottom: 4 }}>BREATHE ESG</div>
          <div style={{ color: 'var(--text3)', fontSize: 12, letterSpacing: 2 }}>EMISSIONS REVIEW PLATFORM</div>
        </div>

        <div className="card">
          <div style={{ marginBottom: 20, color: 'var(--text2)', fontSize: 12 }}>
            Demo credentials pre-filled. Click Sign In.
          </div>
          {error && (
            <div style={{ background: 'var(--red-dim)', border: '1px solid #5a2a2a',
              color: 'var(--red)', padding: '8px 12px', borderRadius: 4, marginBottom: 16, fontSize: 12 }}>
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 12 }}>
              <label style={{ color: 'var(--text3)', fontSize: 11, display: 'block', marginBottom: 4 }}>USERNAME</label>
              <input style={{ width: '100%' }} value={creds.username}
                onChange={e => setCreds(p => ({ ...p, username: e.target.value }))} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ color: 'var(--text3)', fontSize: 11, display: 'block', marginBottom: 4 }}>PASSWORD</label>
              <input type="password" style={{ width: '100%' }} value={creds.password}
                onChange={e => setCreds(p => ({ ...p, password: e.target.value }))} />
            </div>
            <button className="btn-primary" type="submit" style={{ width: '100%', padding: '10px' }} disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
          <div style={{ marginTop: 16, color: 'var(--text3)', fontSize: 11, textAlign: 'center' }}>
            analyst / demo1234 &nbsp;·&nbsp; admin / admin1234
          </div>
        </div>
      </div>
    </div>
  );
}
