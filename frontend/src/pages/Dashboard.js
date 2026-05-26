import React, { useState, useEffect } from 'react';
import { getDashboard } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts';

const SCOPE_COLORS = { scope_1: '#f97316', scope_2: '#3b82f6', scope_3: '#a855f7' };

function StatCard({ label, value, sub, color }) {
  return (
    <div className="card" style={{ flex: 1 }}>
      <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1.5, marginBottom: 8 }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-head)', fontSize: 28, fontWeight: 800,
        color: color || 'var(--text)', lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboard().then(r => { setData(r.data); setLoading(false); });
  }, []);

  if (loading) return (
    <div style={{ padding: 40, color: 'var(--text3)' }}>Loading dashboard...</div>
  );
  if (!data) return null;

  const scopeData = [
    { name: 'Scope 1\nFuel', value: data.by_scope.scope_1 / 1000, color: SCOPE_COLORS.scope_1 },
    { name: 'Scope 2\nElectricity', value: data.by_scope.scope_2 / 1000, color: SCOPE_COLORS.scope_2 },
    { name: 'Scope 3\nTravel', value: data.by_scope.scope_3 / 1000, color: SCOPE_COLORS.scope_3 },
  ];

  const monthlyEntries = Object.entries(data.monthly_trend || {}).sort();
  const monthlyData = monthlyEntries.map(([month, vals]) => ({
    month: month.slice(5),
    s1: +(vals.scope_1 / 1000).toFixed(2),
    s2: +(vals.scope_2 / 1000).toFixed(2),
    s3: +(vals.scope_3 / 1000).toFixed(2),
  }));

  const statusData = Object.entries(data.by_status).map(([k, v]) => ({ name: k, value: v }))
    .filter(d => d.value > 0);

  const STATUS_COLORS = {
    pending: '#6a706a', approved: '#4ade80', rejected: '#f87171',
    flagged: '#fbbf24', locked: '#60a5fa'
  };

  const needsAttention = data.pending_count + data.flagged_count;

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>Emissions Overview</h1>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>Q1 2024 · Acme Manufacturing Ltd</div>
        </div>
        {needsAttention > 0 && (
          <div style={{ background: 'var(--amber-dim)', border: '1px solid #5a4a1a',
            color: 'var(--amber)', padding: '8px 14px', borderRadius: 6, fontSize: 12 }}>
            ⚠ {needsAttention} records need review
          </div>
        )}
      </div>

      {/* KPI row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <StatCard label="TOTAL EMISSIONS"
          value={`${(data.total_co2e_tonnes).toFixed(1)}t`}
          sub="CO₂e · Q1 2024" color="var(--green)" />
        <StatCard label="SCOPE 1 · FUEL"
          value={`${(data.by_scope.scope_1/1000).toFixed(1)}t`}
          sub="Direct combustion" color="var(--scope1)" />
        <StatCard label="SCOPE 2 · ELECTRICITY"
          value={`${(data.by_scope.scope_2/1000).toFixed(1)}t`}
          sub="Purchased power" color="var(--scope2)" />
        <StatCard label="SCOPE 3 · TRAVEL"
          value={`${(data.by_scope.scope_3/1000).toFixed(1)}t`}
          sub="Business travel" color="var(--scope3)" />
        <StatCard label="FLAGGED"
          value={data.anomaly_count}
          sub="Anomalies detected" color="var(--amber)" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 24 }}>
        <div className="card">
          <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1.5, marginBottom: 16 }}>
            MONTHLY BREAKDOWN (tCO₂e)
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={monthlyData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="month" tick={{ fill: 'var(--text3)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text3)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--border)',
                borderRadius: 6, fontSize: 12 }} labelStyle={{ color: 'var(--text)' }} />
              <Bar dataKey="s1" stackId="a" fill={SCOPE_COLORS.scope_1} name="Scope 1" radius={[0,0,0,0]} />
              <Bar dataKey="s2" stackId="a" fill={SCOPE_COLORS.scope_2} name="Scope 2" />
              <Bar dataKey="s3" stackId="a" fill={SCOPE_COLORS.scope_3} name="Scope 3" radius={[2,2,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1.5, marginBottom: 8 }}>
            REVIEW STATUS
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={statusData} cx="50%" cy="50%" innerRadius={50} outerRadius={75}
                dataKey="value" paddingAngle={2}>
                {statusData.map((entry, i) => (
                  <Cell key={i} fill={STATUS_COLORS[entry.name] || '#6a706a'} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--border)',
                borderRadius: 6, fontSize: 12 }} />
              <Legend iconType="circle" iconSize={8}
                formatter={v => <span style={{ color: 'var(--text2)', fontSize: 11, textTransform: 'capitalize' }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Scope breakdown bar */}
      <div className="card">
        <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1.5, marginBottom: 12 }}>
          EMISSION BREAKDOWN BY SCOPE
        </div>
        <div style={{ display: 'flex', height: 24, borderRadius: 4, overflow: 'hidden', gap: 2 }}>
          {scopeData.map(s => {
            const pct = (s.value / (data.total_co2e_tonnes || 1)) * 100;
            return (
              <div key={s.name} style={{ width: `${pct}%`, background: s.color, minWidth: 40,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, color: '#fff', fontWeight: 600 }}>
                {pct.toFixed(0)}%
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 24, marginTop: 10 }}>
          {scopeData.map(s => (
            <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} />
              <span style={{ color: 'var(--text2)', fontSize: 11 }}>
                {s.name.replace('\n', ' ')} · {s.value.toFixed(1)}t
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
