import { useState, useEffect } from 'react';
import { Database, ShieldAlert, ArrowUpRight, Clock, Box, Sliders } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const USER_ID = "00000000-0000-0000-0000-000000000777";
const API_URL = "http://localhost:8000";

type Memory = {
  id: string;
  category: string;
  slot_key: string;
  current_text: string;
  current_level: number;
  sensitivity_tier: number;
  last_accessed_at: string;
  access_count: number;
  ladders?: {
    level: number;
    text: string;
    population_fraction: number;
    info_bits: number;
  }[];
};

export default function ParetoDemo() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [alpha, setAlpha] = useState(0.5); // 0.0 = Max Privacy, 1.0 = Max Utility

  const fetchMemories = async () => {
    try {
      const res = await fetch(`${API_URL}/memories/${USER_ID}`);
      if (!res.ok) throw new Error('Failed to fetch memories');
      const data = await res.json();
      setMemories(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories();
    const interval = setInterval(fetchMemories, 10000);
    return () => clearInterval(interval);
  }, []);

  // Calculate total risk based on simulated levels
  let totalBits = 0;

  return (
    <>
      <header className="content-header">
        <div>
          <h2 style={{ fontSize: '1.25rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sliders size={20} color="var(--accent-primary)" />
            Pareto-Frontier Engine
          </h2>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Interactive visualization of the Risk (Privacy) vs. Utility trade-off.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={fetchMemories}>
          Refresh
        </button>
      </header>


      
      <div className="content-body" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* The Slider Engine */}
        <div className="glass-panel" style={{ width: '100%', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 600 }}>
            <span style={{ color: 'var(--success)' }}>Maximum Privacy</span>
            <span style={{ color: 'var(--text-primary)' }}>Utility Weight (Alpha): {alpha.toFixed(2)}</span>
            <span style={{ color: 'var(--danger)' }}>Maximum Utility</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.01" 
            value={alpha} 
            onChange={(e) => setAlpha(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent-primary)' }}
          />
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', textAlign: 'center' }}>
            Slide to mathematically recalculate the optimal generalization level for all memories in real-time.
          </p>
        </div>

        {error && (
          <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', borderRadius: '8px', marginBottom: '24px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
            <ShieldAlert size={18} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'middle' }} />
            {error}
          </div>
        )}
        
        {isLoading && memories.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '64px' }}>
            <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
              <Database size={32} color="var(--text-muted)" />
            </motion.div>
          </div>
        ) : memories.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '64px', color: 'var(--text-muted)' }}>
            <Box size={48} style={{ opacity: 0.5, marginBottom: '16px' }} />
            <p>No memories found. Chat with the agent to generate data.</p>
          </div>
        ) : (
          <div className="grid-3">
            <AnimatePresence>
              {memories.map((mem) => {
                // Calculate simulated level
                const maxLevel = mem.ladders && mem.ladders.length > 0 
                  ? Math.max(...mem.ladders.map(l => l.level)) 
                  : 0;
                
                // alpha = 1 -> level 0. alpha = 0 -> level maxLevel.
                const simulatedLevel = Math.round((1 - alpha) * maxLevel);
                const activeLadder = mem.ladders?.find(l => l.level === simulatedLevel);
                const simulatedText = activeLadder ? activeLadder.text : mem.current_text;
                
                if (activeLadder) totalBits += activeLadder.info_bits;

                return (
                  <motion.div
                    key={mem.id}
                    layout
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="glass-panel memory-card"
                    style={{
                      border: simulatedLevel > 0 ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(255,255,255,0.05)',
                      boxShadow: simulatedLevel > 0 ? '0 4px 20px rgba(245, 158, 11, 0.1)' : 'none'
                    }}
                  >
                    <div className="memory-card-header">
                      <span className="badge badge-info">{mem.category} / {mem.slot_key}</span>
                      <motion.span 
                        key={simulatedLevel}
                        initial={{ scale: 1.5, color: '#fff' }}
                        animate={{ scale: 1, color: simulatedLevel > 0 ? 'var(--warning)' : 'var(--text-secondary)' }}
                        className={`badge ${simulatedLevel > 0 ? 'badge-danger' : ''}`} 
                        style={{ background: simulatedLevel > 0 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255,255,255,0.05)' }}
                      >
                        L{simulatedLevel}
                      </motion.span>
                    </div>
                    
                    <motion.div 
                      key={simulatedText}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="memory-card-body text-gradient" 
                      style={{ fontSize: '1.25rem', fontWeight: 600, minHeight: '40px' }}
                    >
                      {simulatedText}
                    </motion.div>
                    
                    <div className="memory-card-footer">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={14} />
                        {new Date(mem.last_accessed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <ArrowUpRight size={14} />
                        {mem.access_count} uses
                      </div>
                    </div>
                    
                    {mem.ladders && mem.ladders.length > 0 && (
                      <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                        <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>Generalization Ladder</h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', position: 'relative' }}>
                          <div style={{ position: 'absolute', left: '11px', top: '10px', bottom: '10px', width: '2px', background: 'rgba(255,255,255,0.05)' }} />
                          
                          {mem.ladders.sort((a, b) => a.level - b.level).map((ladder, idx) => {
                            const isActive = ladder.level === simulatedLevel;
                            return (
                              <motion.div 
                                key={ladder.level}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: idx * 0.1 }}
                                style={{ 
                                  display: 'flex', 
                                  alignItems: 'center', 
                                  gap: '12px',
                                  position: 'relative',
                                  opacity: isActive ? 1 : 0.4,
                                  background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                                  padding: '8px',
                                  borderRadius: '8px',
                                  border: isActive ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                                  transform: isActive ? 'scale(1.02)' : 'scale(1)',
                                  transition: 'all 0.3s ease'
                                }}
                              >
                                <div style={{ 
                                  width: '24px', height: '24px', borderRadius: '12px', 
                                  background: isActive ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                                  fontSize: '0.7rem', fontWeight: 'bold', zIndex: 1,
                                  border: isActive ? 'none' : '1px solid rgba(255,255,255,0.1)',
                                  color: isActive ? 'white' : 'var(--text-secondary)'
                                }}>
                                  L{ladder.level}
                                </div>
                                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                                  <span style={{ fontSize: '0.85rem', color: isActive ? 'white' : 'var(--text-secondary)', fontWeight: isActive ? 600 : 400 }}>
                                    {ladder.text}
                                  </span>
                                  {isActive && (
                                    <span style={{ fontSize: '0.7rem', color: 'var(--accent-primary)', marginTop: '2px' }}>
                                      Risk: {ladder.info_bits.toFixed(2)} bits
                                    </span>
                                  )}
                                </div>
                              </motion.div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </>
  );
}
