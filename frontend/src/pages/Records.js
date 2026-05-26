import React, { useState, useEffect, useCallback } from 'react';
import { getRecords, approveRecord, rejectRecord, bulkApprove, lockApproved } from '../services/api';

const SCOPE_LABELS = { 1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3' };
const STATUS_CLASSES = {
  pending: 'tag-pending', approved: 'tag-approved', rejected: 'tag-rejected',
  flagged: 'tag-flagged', locked: 'tag-locked'
};
const SCOPE_CLASSES = { 1: 'tag-scope1', 2: 'tag-scope2', 3: 'tag-scope3' };

function Modal({ record, onClose, onAction }) {
  const [note, setNote] = useState('');
  if (!record) return null;
  const m = record.metadata || {};

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}
      onClick={onClose}>
      <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10,
        width: 560, maxHeight: '80vh', overflow: 'auto', padding: 28 }}
        onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: 16, marginBottom: 4 }}>{record.category_display}</h3>
            <div style={{ color: 'var(--text3)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              {record.id.slice(0, 8)}...
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', color: 'var(--text3)',
            fontSize: 18, padding: 4 }}>✕</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
          {[
            ['Date', record.activity_date],
            ['Scope', `${SCOPE_LABELS[record.scope]} · ${record.category_display}`],
            ['CO₂e', record.co2e_kg ? `${(+record.co2e_kg).toLocaleString()} kg` : '—'],
            ['EF Source', record.emission_factor_source],
            ['EF Value', record.emission_factor ? `${record.emission_factor} ${record.emission_factor_unit}` : '—'],
            ['Original', record.original_quantity ? `${record.original_quantity} ${record.original_unit}` : '—'],
          ].map(([k, v]) => (
            <div key={k} style={{ background: 'var(--bg3)', borderRadius: 6, padding: '10px 12px' }}>
              <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1, marginBottom: 3 }}>{k.toUpperCase()}</div>
              <div style={{ fontSize: 13 }}>{v || '—'}</div>
            </div>
          ))}
        </div>

        {Object.keys(m).length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1, marginBottom: 8 }}>METADATA</div>
            <div style={{ background: 'var(--bg3)', borderRadius: 6, padding: 12 }}>
              {Object.entries(m).filter(([, v]) => v && !Array.isArray(v)).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', gap: 12, marginBottom: 4, fontSize: 12 }}>
                  <span style={{ color: 'var(--text3)', minWidth: 140 }}>{k.replace(/_/g, ' ')}</span>
                  <span>{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {record.is_anomaly && (
          <div style={{ background: 'var(--amber-dim)', border: '1px solid #5a4a1a',
            borderRadius: 6, padding: 12, marginBottom: 20 }}>
            <div style={{ color: 'var(--amber)', fontSize: 11, fontWeight: 600, marginBottom: 4 }}>⚠ ANOMALY FLAGS</div>
            {record.anomaly_reasons.map((r, i) => (
              <div key={i} style={{ color: 'var(--amber)', fontSize: 12 }}>· {r}</div>
            ))}
          </div>
        )}

        {record.status !== 'locked' && (
          <div>
            <div style={{ marginBottom: 8 }}>
              <label style={{ color: 'var(--text3)', fontSize: 11, display: 'block', marginBottom: 4 }}>
                REVIEW NOTE (optional)
              </label>
              <textarea value={note} onChange={e => setNote(e.target.value)}
                style={{ width: '100%', height: 60, resize: 'none' }}
                placeholder="Add context for the audit trail..." />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-approve" onClick={() => onAction('approve', record.id, note)}>
                ✓ Approve
              </button>
              <button className="btn-reject" onClick={() => onAction('reject', record.id, note)}>
                ✗ Reject
              </button>
            </div>
          </div>
        )}

        {record.is_edited && record.edit_history?.length > 0 && (
          <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <div style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1, marginBottom: 8 }}>EDIT HISTORY</div>
            {record.edit_history.map((e, i) => (
              <div key={i} style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>
                {e.edited_at?.slice(0, 16)} · {e.edited_by} changed {e.field}: {e.old_value} → {e.new_value}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Records() {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [detail, setDetail] = useState(null);
  const [filters, setFilters] = useState({ status: '', scope: '', source_type: '', anomaly: '' });
  const [page, setPage] = useState(1);
  const [locking, setLocking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([,v]) => v)) };
    try {
      const r = await getRecords(params);
      setRecords(r.data.results || r.data);
      setTotal(r.data.count || (r.data.results || r.data).length);
    } finally { setLoading(false); }
  }, [filters, page]);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (action, id, note) => {
    if (action === 'approve') await approveRecord(id, note);
    else await rejectRecord(id, note);
    setDetail(null);
    load();
  };

  const handleBulkApprove = async () => {
    await bulkApprove([...selected]);
    setSelected(new Set());
    load();
  };

  const handleLock = async () => {
    setLocking(true);
    await lockApproved();
    setLocking(false);
    load();
  };

  const toggleSelect = (id) => {
    setSelected(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const setFilter = (k, v) => { setFilters(p => ({ ...p, [k]: v })); setPage(1); };

  const pendingCount = records.filter(r => r.status === 'pending' || r.status === 'flagged').length;

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>Emission Records</h1>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>{total} records · Q1 2024</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {selected.size > 0 && (
            <button className="btn-approve" onClick={handleBulkApprove}>
              ✓ Approve {selected.size} selected
            </button>
          )}
          <button className="btn-ghost" onClick={handleLock} disabled={locking}>
            🔒 Lock Approved for Audit
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {[
          { key: 'status', label: 'Status', opts: ['', 'pending', 'flagged', 'approved', 'rejected', 'locked'] },
          { key: 'scope', label: 'Scope', opts: ['', '1', '2', '3'] },
          { key: 'source_type', label: 'Source', opts: ['', 'sap', 'utility', 'travel'] },
          { key: 'anomaly', label: 'Anomaly', opts: ['', 'true'] },
        ].map(f => (
          <select key={f.key} value={filters[f.key]} onChange={e => setFilter(f.key, e.target.value)}
            style={{ fontSize: 12, padding: '5px 8px' }}>
            <option value="">{f.label}: All</option>
            {f.opts.filter(Boolean).map(o => (
              <option key={o} value={o}>{o === 'true' ? 'Flagged only' : o.charAt(0).toUpperCase() + o.slice(1)}</option>
            ))}
          </select>
        ))}
        {Object.values(filters).some(Boolean) && (
          <button className="btn-ghost" onClick={() => setFilters({ status: '', scope: '', source_type: '', anomaly: '' })}>
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg3)' }}>
              <th style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text3)',
                fontSize: 10, letterSpacing: 1, fontWeight: 500, width: 32 }}>
                <input type="checkbox"
                  onChange={e => setSelected(e.target.checked ? new Set(records.map(r => r.id)) : new Set())}
                  checked={selected.size === records.length && records.length > 0} />
              </th>
              {['Scope/Category', 'Date', 'CO₂e', 'Source', 'Status', 'Flags', ''].map(h => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left',
                  color: 'var(--text3)', fontSize: 10, letterSpacing: 1, fontWeight: 500 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ padding: 40, textAlign: 'center', color: 'var(--text3)' }}>
                Loading...
              </td></tr>
            ) : records.map(r => (
              <tr key={r.id} style={{
                borderTop: '1px solid var(--border)',
                background: selected.has(r.id) ? 'rgba(74,222,128,0.04)' : 'transparent',
                cursor: 'pointer',
                transition: 'background 0.1s',
              }}
                onMouseEnter={e => e.currentTarget.style.background = selected.has(r.id)
                  ? 'rgba(74,222,128,0.06)' : 'var(--bg3)'}
                onMouseLeave={e => e.currentTarget.style.background = selected.has(r.id)
                  ? 'rgba(74,222,128,0.04)' : 'transparent'}>
                <td style={{ padding: '10px 14px' }} onClick={e => { e.stopPropagation(); toggleSelect(r.id); }}>
                  <input type="checkbox" checked={selected.has(r.id)} readOnly />
                </td>
                <td style={{ padding: '10px 14px' }} onClick={() => setDetail(r)}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span className={`tag ${SCOPE_CLASSES[r.scope]}`} style={{ fontSize: 10 }}>
                      {SCOPE_LABELS[r.scope]}
                    </span>
                    <span style={{ color: 'var(--text2)', fontSize: 11 }}>{r.category_display}</span>
                  </div>
                </td>
                <td style={{ padding: '10px 14px', color: 'var(--text2)' }} onClick={() => setDetail(r)}>
                  {r.activity_date}
                </td>
                <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)' }} onClick={() => setDetail(r)}>
                  {r.co2e_kg ? `${(+r.co2e_kg).toLocaleString()} kg` : '—'}
                </td>
                <td style={{ padding: '10px 14px', color: 'var(--text3)', textTransform: 'uppercase',
                  fontSize: 11 }} onClick={() => setDetail(r)}>
                  {r.source_type}
                </td>
                <td style={{ padding: '10px 14px' }} onClick={() => setDetail(r)}>
                  <span className={`tag ${STATUS_CLASSES[r.status] || 'tag-pending'}`} style={{ fontSize: 10 }}>
                    {r.status_display}
                  </span>
                </td>
                <td style={{ padding: '10px 14px' }} onClick={() => setDetail(r)}>
                  {r.is_anomaly && (
                    <span title={r.anomaly_reasons?.join('\n')}
                      style={{ color: 'var(--amber)', fontSize: 14 }}>⚠</span>
                  )}
                  {r.is_edited && (
                    <span title="Manually edited" style={{ color: 'var(--blue)', fontSize: 14, marginLeft: 4 }}>✎</span>
                  )}
                </td>
                <td style={{ padding: '10px 14px' }}>
                  {(r.status === 'pending' || r.status === 'flagged') && (
                    <div style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
                      <button className="btn-approve" style={{ fontSize: 11, padding: '3px 8px' }}
                        onClick={() => handleAction('approve', r.id, '')}>✓</button>
                      <button className="btn-reject" style={{ fontSize: 11, padding: '3px 8px' }}
                        onClick={() => handleAction('reject', r.id, '')}>✗</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button className="btn-ghost" onClick={() => setPage(p => Math.max(1, p-1))} disabled={page === 1}>← Prev</button>
          <span style={{ color: 'var(--text3)', padding: '6px 12px', fontSize: 12 }}>Page {page}</span>
          <button className="btn-ghost" onClick={() => setPage(p => p+1)} disabled={page * 50 >= total}>Next →</button>
        </div>
      )}

      <Modal record={detail} onClose={() => setDetail(null)} onAction={handleAction} />
    </div>
  );
}
