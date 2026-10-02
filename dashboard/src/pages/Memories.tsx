import { useState, useEffect } from 'react';
import { Database, ShieldAlert, ArrowUpRight, Clock, Box } from 'lucide-react';
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

export default function Memories() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchMemories = async () => {
    setIsLoading(true);
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
    // Poll every 5 seconds to show real-time generalizations
    const interval = setInterval(fetchMemories, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <header className="content-header">
        <div>
          <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Memory Vault</h2>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>Live view of user memory states and generalization levels.</p>
        </div>
        <button className="btn btn-ghost" onClick={fetchMemories}>
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
        
        {isLoading && memories.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '64px' }}>
            <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
              <Database size={32} color="var(--text-muted)" />
            </motion.div>
          </div>
        ) : memories.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '64px', color: 'var(--text-muted)' }}>
            <Box size={48} style={{ opacity: 0.5, marginBottom: '16px' }} />
            <p>No memories found. Chat with the agent to store facts.</p>
          </div>
        ) : (
          <div className="grid-3">
            <AnimatePresence>
              {memories.map((mem) => (
                <motion.div
                  key={mem.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="glass-panel memory-card"
                >
                  <div className="memory-card-header">
                    <span className="badge badge-info">{mem.category} / {mem.slot_key}</span>
                    <span className={`badge ${mem.current_level > 0 ? 'badge-danger' : ''}`} style={{ background: mem.current_level > 0 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255,255,255,0.05)', color: mem.current_level > 0 ? 'var(--warning)' : 'var(--text-secondary)' }}>
                      L{mem.current_level}
                    </span>
                  </div>
                  
                  <div className="memory-card-body text-gradient" style={{ fontSize: '1.25rem', fontWeight: 600 }}>
                    {mem.current_text}
                  </div>
                  
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
                        {/* Connecting line */}
                        <div style={{ position: 'absolute', left: '11px', top: '10px', bottom: '10px', width: '2px', background: 'rgba(255,255,255,0.05)' }} />
                        
                        {mem.ladders.sort((a, b) => a.level - b.level).map((ladder, idx) => {
                          const isActive = ladder.level === mem.current_level;
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
                                opacity: isActive ? 1 : 0.5,
                                background: isActive ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
                                padding: '8px',
                                borderRadius: '8px',
                                border: isActive ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid transparent'
                              }}
                            >
                              <div style={{ 
                                width: '24px', height: '24px', borderRadius: '12px', 
                                background: isActive ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: '0.7rem', fontWeight: 'bold', zIndex: 1,
                                border: isActive ? 'none' : '1px solid rgba(255,255,255,0.1)'
                              }}>
                                L{ladder.level}
                              </div>
                              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                                <span style={{ fontSize: '0.85rem', color: isActive ? 'white' : 'var(--text-secondary)' }}>
                                  {ladder.text}
                                </span>
                              </div>
                            </motion.div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </>
  );
}
