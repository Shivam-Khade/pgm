import { useState, useEffect } from 'react';
import { Activity, ShieldAlert, Lock, AlertTriangle, TrendingDown } from 'lucide-react';
import { motion } from 'framer-motion';

const USER_ID = "00000000-0000-0000-0000-000000000777";
const API_URL = "http://localhost:8000";

type RiskSnapshot = {
  id: string;
  created_at: string;
  k_hat: number;
  r_agg_bits: number;
  quasi_identifiers: Record<string, string>;
};

type RiskData = {
  budget_bits: number;
  history: RiskSnapshot[];
};

export default function RiskMetrics() {
  const [data, setData] = useState<RiskData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchRisk = async () => {
    try {
      const res = await fetch(`${API_URL}/risk/${USER_ID}`);
      if (!res.ok) throw new Error('Failed to fetch risk metrics');
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRisk();
    const interval = setInterval(fetchRisk, 5000);
    return () => clearInterval(interval);
  }, []);

  const latest = data?.history[0];
  const budget = data?.budget_bits || 20;
  const currentRisk = latest?.r_agg_bits || 0;
  const riskPercentage = Math.min((currentRisk / budget) * 100, 100);
  
  const isDanger = riskPercentage > 90;
  const isWarning = riskPercentage > 70 && !isDanger;
  
  const statusColor = isDanger ? 'var(--danger)' : isWarning ? 'var(--warning)' : 'var(--success)';
  const glowColor = isDanger ? 'rgba(239, 68, 68, 0.4)' : isWarning ? 'rgba(245, 158, 11, 0.4)' : 'rgba(16, 185, 129, 0.4)';

  return (
    <>
      <header className="content-header">
        <div>
          <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Risk Dashboard</h2>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>Real-time Re-identification Risk Metrics.</p>
        </div>
        <button className="btn btn-ghost" onClick={fetchRisk}>
          Refresh
        </button>
      </header>

      <div className="content-body">
        {error && (
          <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', borderRadius: '8px', marginBottom: '24px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
            <ShieldAlert size={18} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'middle' }} />
            {error}
          </div>
        )}

        {!isLoading && !latest ? (
          <div style={{ textAlign: 'center', padding: '64px', color: 'var(--text-muted)' }}>
            <Activity size={48} style={{ opacity: 0.5, marginBottom: '16px' }} />
            <p>No risk data available yet. Chat with the agent to generate data.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            
            {/* Main Gauge / Meter */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-panel" 
              style={{ padding: '32px', border: `1px solid ${glowColor}`, boxShadow: `0 8px 32px ${glowColor}` }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Activity color={statusColor} size={28} />
                  <h3 style={{ margin: 0, fontSize: '1.5rem' }}>Aggregate Re-identification Risk</h3>
                </div>
                <div className={`badge ${isDanger ? 'badge-danger' : 'badge-info'}`} style={{ fontSize: '1rem', padding: '6px 16px' }}>
                  {currentRisk.toFixed(2)} / {budget.toFixed(2)} bits
                </div>
              </div>
              
              {/* Progress Bar */}
              <div style={{ width: '100%', height: '16px', background: 'rgba(255,255,255,0.1)', borderRadius: '8px', overflow: 'hidden' }}>
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${riskPercentage}%` }}
                  transition={{ type: 'spring', stiffness: 50 }}
                  style={{ height: '100%', background: statusColor, borderRadius: '8px' }}
                />
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                <span>0 bits (Safe)</span>
                <span>Budget Max ({budget} bits)</span>
              </div>
            </motion.div>

            {/* Metrics Grid */}
            <div className="grid-2">

              
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }} className="glass-panel" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                  <AlertTriangle size={18} /> Extracted QIs
                </div>
                <div style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {latest?.quasi_identifiers ? Object.keys(latest.quasi_identifiers).length : 0} Facts
                </div>
                <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {latest?.quasi_identifiers && Object.keys(latest.quasi_identifiers).map(k => (
                    <span key={k} className="badge badge-info" style={{ fontSize: '0.7rem' }}>{k}</span>
                  ))}
                </div>
              </motion.div>
              
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.3 }} className="glass-panel" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                  <TrendingDown size={18} /> System Status
                </div>
                <div style={{ fontSize: '1.25rem', fontWeight: 500, color: isDanger ? 'var(--danger)' : 'var(--success)' }}>
                  {isDanger ? 'Budget Exceeded!' : isWarning ? 'Approaching Limit' : 'Operating Normally'}
                </div>
                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '8px' }}>
                  The maintenance loop will trigger generalizations if the budget is breached.
                </p>
              </motion.div>
            </div>
            
            {/* History Table (Optional) */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="glass-panel" style={{ padding: '24px', flex: 1 }}>
              <h4 style={{ margin: '0 0 16px 0', fontSize: '1.1rem' }}>Risk History (Last 5 snapshots)</h4>
              <div style={{ width: '100%', overflowX: 'auto' }}>
                <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)' }}>
                      <th style={{ padding: '12px 8px', color: 'var(--text-secondary)' }}>Time</th>
                      <th style={{ padding: '12px 8px', color: 'var(--text-secondary)' }}>Risk (bits)</th>
                      <th style={{ padding: '12px 8px', color: 'var(--text-secondary)' }}>k-hat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.history.slice(0, 5).map((snap) => (
                      <tr key={snap.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px 8px' }}>{new Date(snap.created_at).toLocaleTimeString()}</td>
                        <td style={{ padding: '12px 8px', color: snap.r_agg_bits > 18 ? 'var(--danger)' : 'var(--text-primary)' }}>{snap.r_agg_bits.toFixed(3)}</td>
                        <td style={{ padding: '12px 8px' }}>{Math.round(snap.k_hat).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>

          </div>
        )}
      </div>
    </>
  );
}
