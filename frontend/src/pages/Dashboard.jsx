import { useState, useEffect } from 'react';
import axios from 'axios';
import { Play, FileText, AlertTriangle, CheckCircle, Package } from 'lucide-react';

export default function Dashboard() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  useEffect(() => {
    // Set axios auth header from localstorage just in case
    const token = localStorage.getItem('token');
    if (token) axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    
    fetchReport();
  }, []);

  const fetchReport = async () => {
    try {
      const res = await axios.get('/api/report');
      setReport(res.data);
    } catch (err) {
      console.log('No report found yet.');
    }
  };

  const runPipeline = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.post('/api/run');
      setReport(res.data.report);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to run pipeline');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Executive Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>AI-Powered Supply Chain Intelligence</p>
        </div>
        <button 
          className="btn btn-primary" 
          onClick={runPipeline} 
          disabled={loading}
        >
          {loading ? 'Running ML Pipeline...' : <><Play size={18} /> Run ML Pipeline</>}
        </button>
      </div>

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', padding: '1rem', borderRadius: '8px', marginBottom: '2rem' }}>
          {error}
        </div>
      )}

      {!report && !loading && (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <FileText size={48} color="var(--text-secondary)" style={{ margin: '0 auto 1rem' }} />
          <h3>No Report Available</h3>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>Run the ML pipeline to generate predictions.</p>
        </div>
      )}

      {report && (
        <>
          {/* KPI Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                <AlertTriangle color="var(--danger)" />
                <h3 style={{ fontSize: '1.1rem' }}>Critical Risks</h3>
              </div>
              <p style={{ fontSize: '2.5rem', fontWeight: '700', fontFamily: 'Outfit' }}>
                {report.risk_trend_7d.levels.filter(l => l === 'High' || l === 'Critical').length}
              </p>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>High risk days detected</p>
            </div>
            
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                <Package color="var(--warning)" />
                <h3 style={{ fontSize: '1.1rem' }}>Inventory Status</h3>
              </div>
              <p style={{ fontSize: '2.5rem', fontWeight: '700', fontFamily: 'Outfit' }}>
                {report.inventory.critical_items}
              </p>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Critical items requiring reorder</p>
            </div>

            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                <CheckCircle color="var(--success)" />
                <h3 style={{ fontSize: '1.1rem' }}>Overall Risk</h3>
              </div>
              <p style={{ fontSize: '2.5rem', fontWeight: '700', fontFamily: 'Outfit' }}>
                {report.risk_snapshot.composite_risk_score.toFixed(1)}
              </p>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Composite Risk Score (out of 100)</p>
            </div>
          </div>

          {/* Executive Summary */}
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <h2 style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>Executive Summary</h2>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.8', color: 'var(--text-primary)' }}>
              {report.executive_summary}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
