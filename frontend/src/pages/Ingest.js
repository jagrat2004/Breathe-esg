import React, { useState, useEffect } from 'react';
import { ingestFile, getBatches } from '../services/api';

const SOURCES = [
  {
    id: 'sap',
    label: 'SAP Fuel & Procurement',
    scope: 'Scope 1',
    format: 'CSV (flat-file export MB51/ME2M)',
    description: 'SAP ECC/S4HANA flat-file CSV export. Handles German headers (Buchungsdatum, Menge, Einheit), DD.MM.YYYY dates, and unit codes (L, KG, M3, KWH). Movement type filtering removes non-consumption rows.',
    accepts: '.csv',
    color: 'var(--scope1)',
    sampleHint: 'Download sample_sap.csv',
  },
  {
    id: 'utility',
    label: 'Utility / Electricity',
    scope: 'Scope 2',
    format: 'CSV (portal export — EDF, Octopus, etc.)',
    description: 'Portal CSV export from UK/EU utility providers. Handles billing periods that cross month boundaries, multiple meter IDs per site, MWh/GJ→kWh normalization, and location-specific grid emission factors.',
    accepts: '.csv',
    color: 'var(--scope2)',
    sampleHint: 'Download sample_utility.csv',
    extraField: { name: 'country', label: 'Grid country', options: ['UK', 'DE', 'FR', 'US', 'IN'] },
  },
  {
    id: 'travel',
    label: 'Corporate Travel',
    scope: 'Scope 3',
    format: 'JSON (Concur/Navan API export)',
    description: 'JSON trip export from Concur or Navan. Handles flight/hotel/ground segments. Computes flight distances via haversine from IATA codes when distance_km is not provided. Cabin class multipliers applied.',
    accepts: '.json',
    color: 'var(--scope3)',
    sampleHint: 'Download sample_travel.json',
  },
];

function DropZone({ source, onFile, file }) {
  const [dragging, setDragging] = useState(false);

  const onDrop = e => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  };

  return (
    <div
      onDrop={onDrop}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onClick={() => document.getElementById(`file-${source.id}`).click()}
      style={{
        border: `2px dashed ${dragging ? source.color : 'var(--border2)'}`,
        borderRadius: 8, padding: 24, textAlign: 'center', cursor: 'pointer',
        background: dragging ? `rgba(${source.id === 'sap' ? '249,115,22' : source.id === 'utility' ? '59,130,246' : '168,85,247'},0.05)` : 'var(--bg3)',
        transition: 'all 0.15s',
      }}>
      <input type="file" id={`file-${source.id}`} accept={source.accepts}
        style={{ display: 'none' }} onChange={e => onFile(e.target.files[0])} />
      {file ? (
        <div>
          <div style={{ fontSize: 20, marginBottom: 6 }}>📄</div>
          <div style={{ color: 'var(--text)', fontSize: 13, fontWeight: 500 }}>{file.name}</div>
          <div style={{ color: 'var(--text3)', fontSize: 11 }}>
            {(file.size / 1024).toFixed(1)} KB · Click to change
          </div>
        </div>
      ) : (
        <div>
          <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.4 }}>↑</div>
          <div style={{ color: 'var(--text2)', fontSize: 13 }}>Drop {source.accepts} file or click to browse</div>
          <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 4 }}>{source.format}</div>
        </div>
      )}
    </div>
  );
}

function ResultBanner({ result }) {
  if (!result) return null;
  const success = result.created > 0;
  return (
    <div style={{
      background: success ? 'var(--green-dim)' : 'var(--red-dim)',
      border: `1px solid ${success ? '#2a5a3a' : '#5a2a2a'}`,
      borderRadius: 8, padding: '14px 18px', marginBottom: 16,
    }}>
      <div style={{ color: success ? 'var(--green)' : 'var(--red)', fontWeight: 600, marginBottom: 4 }}>
        {success ? `✓ ${result.created} records ingested` : '✗ Ingestion failed'}
        {result.errors > 0 && ` · ${result.errors} rows had errors`}
      </div>
      {result.error_detail?.length > 0 && (
        <div style={{ color: 'var(--text3)', fontSize: 11 }}>
          {result.error_detail.slice(0, 5).map((e, i) => <div key={i}>· {e}</div>)}
        </div>
      )}
    </div>
  );
}

export default function Ingest() {
  const [files, setFiles] = useState({});
  const [country, setCountry] = useState('UK');
  const [loading, setLoading] = useState({});
  const [results, setResults] = useState({});
  const [batches, setBatches] = useState([]);

  useEffect(() => {
    getBatches().then(r => setBatches(r.data.results || r.data));
  }, [results]);

  const handleUpload = async (sourceId) => {
    const file = files[sourceId];
    if (!file) return;
    setLoading(p => ({ ...p, [sourceId]: true }));
    try {
      const res = await ingestFile(file, sourceId, country);
      setResults(p => ({ ...p, [sourceId]: res.data }));
      setFiles(p => ({ ...p, [sourceId]: null }));
    } catch (err) {
      setResults(p => ({ ...p, [sourceId]: { error: err.message, created: 0, errors: 1 } }));
    } finally {
      setLoading(p => ({ ...p, [sourceId]: false }));
    }
  };

  const STATUS_COLORS = {
    done: 'var(--green)', failed: 'var(--red)', processing: 'var(--amber)', pending: 'var(--text3)'
  };

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>Data Ingestion</h1>
        <div style={{ color: 'var(--text3)', fontSize: 12 }}>
          Upload emissions data from SAP, utility portals, or corporate travel platforms
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 }}>
        {SOURCES.map(source => (
          <div key={source.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <span className={`tag ${source.scope === 'Scope 1' ? 'tag-scope1' : source.scope === 'Scope 2' ? 'tag-scope2' : 'tag-scope3'}`}>
                  {source.scope}
                </span>
              </div>
              <h3 style={{ fontSize: 15, marginBottom: 6 }}>{source.label}</h3>
              <p style={{ color: 'var(--text3)', fontSize: 11, lineHeight: 1.6 }}>{source.description}</p>
            </div>

            {source.extraField && (
              <div>
                <label style={{ color: 'var(--text3)', fontSize: 10, letterSpacing: 1, display: 'block', marginBottom: 4 }}>
                  {source.extraField.label.toUpperCase()}
                </label>
                <select value={country} onChange={e => setCountry(e.target.value)} style={{ width: '100%', fontSize: 12 }}>
                  {source.extraField.options.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
            )}

            <DropZone source={source} file={files[source.id]}
              onFile={f => setFiles(p => ({ ...p, [source.id]: f }))} />

            <ResultBanner result={results[source.id]} />

            <button
              className="btn-primary"
              onClick={() => handleUpload(source.id)}
              disabled={!files[source.id] || loading[source.id]}
              style={{ opacity: !files[source.id] ? 0.4 : 1 }}>
              {loading[source.id] ? 'Processing...' : 'Upload & Process'}
            </button>
          </div>
        ))}
      </div>

      {/* Batch history */}
      <div>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 14 }}>Ingestion History</h2>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg3)' }}>
                {['File', 'Source', 'Records', 'Errors', 'Status', 'Uploaded'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left',
                    color: 'var(--text3)', fontSize: 10, letterSpacing: 1, fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr><td colSpan={6} style={{ padding: 24, color: 'var(--text3)', textAlign: 'center', fontSize: 12 }}>
                  No ingestion history yet
                </td></tr>
              ) : batches.map(b => (
                <tr key={b.id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 16px', fontSize: 12 }}>{b.filename}</td>
                  <td style={{ padding: '10px 16px', color: 'var(--text3)', fontSize: 11,
                    textTransform: 'uppercase' }}>{b.source_type_display}</td>
                  <td style={{ padding: '10px 16px' }}>{b.row_count}</td>
                  <td style={{ padding: '10px 16px', color: b.error_count > 0 ? 'var(--red)' : 'var(--text3)' }}>
                    {b.error_count}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ color: STATUS_COLORS[b.status] || 'var(--text3)', fontSize: 11, textTransform: 'uppercase' }}>
                      {b.status}
                    </span>
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--text3)', fontSize: 11 }}>
                    {new Date(b.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
