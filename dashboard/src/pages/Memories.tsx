import { useState, useEffect } from 'react';
import { Database, ShieldAlert, ArrowUpRight, Clock, Box, Trash2 } from 'lucide-react';
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
  const [expandedMemories, setExpandedMemories] = useState<Record<string, boolean>>({});
  const [error, setError] = useState('');
  const [toast, setToast] = useState<{message: string, type: 'success' | 'error'} | null>(null);
  const [memoryToDelete, setMemoryToDelete] = useState<string | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };
  
  // Filtering and Sorting State
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');

  const toggleExpand = (id: string) => {
    setExpandedMemories(prev => ({ ...prev, [id]: !prev[id] }));
  };

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

  const executeDelete = async (memoryId: string) => {
    try {
      const res = await fetch(`${API_URL}/memories/${memoryId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to delete memory');
      setMemories(prev => prev.filter(m => m.id !== memoryId));
      showToast('Memory successfully deleted', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to delete memory', 'error');
    } finally {
      setMemoryToDelete(null);
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
        
        {/* Filters and Controls */}
        <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <input 
            type="text" 
            className="input" 
            placeholder="Search memories..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ flex: '1 1 200px', minWidth: '200px' }}
          />
          <select 
            className="input" 
            value={levelFilter} 
            onChange={(e) => setLevelFilter(e.target.value)}
            style={{ width: 'auto', appearance: 'auto', paddingRight: '12px' }}
          >
            <option value="all">All Levels</option>
            <option value="0">Level 0</option>
            <option value="1">Level 1</option>
            <option value="2">Level 2</option>
            <option value="3">Level 3</option>
          </select>
          <select 
            className="input" 
            value={sortBy} 
            onChange={(e) => setSortBy(e.target.value)}
            style={{ width: 'auto', appearance: 'auto', paddingRight: '12px' }}
          >
            <option value="newest">Newest Accessed</option>
            <option value="oldest">Oldest Accessed</option>
            <option value="most_accessed">Most Accessed</option>
          </select>
        </div>
        
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
              {memories
                .filter(mem => {
                  // Level filter
                  if (levelFilter !== 'all' && mem.current_level !== parseInt(levelFilter)) return false;
                  // Search filter
                  if (searchQuery) {
                    const q = searchQuery.toLowerCase();
                    return mem.current_text.toLowerCase().includes(q) || 
                           mem.category.toLowerCase().includes(q) || 
                           mem.slot_key.toLowerCase().includes(q);
                  }
                  return true;
                })
                .sort((a, b) => {
                  if (sortBy === 'newest') return new Date(b.last_accessed_at).getTime() - new Date(a.last_accessed_at).getTime();
                  if (sortBy === 'oldest') return new Date(a.last_accessed_at).getTime() - new Date(b.last_accessed_at).getTime();
                  if (sortBy === 'most_accessed') return b.access_count - a.access_count;
                  return 0;
                })
                .map((mem) => (
                <motion.div
                  key={mem.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="glass-panel memory-card"
                >
                  <div className="memory-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span className="badge badge-info">{mem.category} / {mem.slot_key}</span>
                      <span className={`badge ${mem.current_level > 0 ? 'badge-danger' : ''}`} style={{ background: mem.current_level > 0 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255,255,255,0.05)', color: mem.current_level > 0 ? 'var(--warning)' : 'var(--text-secondary)' }}>
                        L{mem.current_level}
                      </span>
                    </div>
                    <button 
                      className="btn btn-ghost btn-sm" 
                      onClick={() => setMemoryToDelete(mem.id)}
                      style={{ padding: '4px', color: 'var(--danger)', opacity: 0.7 }}
                      title="Delete Memory"
                      onMouseOver={(e) => e.currentTarget.style.opacity = '1'}
                      onMouseOut={(e) => e.currentTarget.style.opacity = '0.7'}
                    >
                      <Trash2 size={16} />
                    </button>
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
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                        <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>Generalization Ladder</h4>
                        {mem.ladders.length > 1 && (
                          <button 
                            className="btn btn-ghost btn-sm" 
                            style={{ fontSize: '0.75rem', padding: '2px 8px' }}
                            onClick={() => toggleExpand(mem.id)}
                          >
                            {expandedMemories[mem.id] ? 'Hide Levels' : 'Show All Levels'}
                          </button>
                        )}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', position: 'relative' }}>
                        {/* Connecting line */}
                        {expandedMemories[mem.id] && (
                          <div style={{ position: 'absolute', left: '11px', top: '10px', bottom: '10px', width: '2px', background: 'rgba(255,255,255,0.05)' }} />
                        )}
                        
                        {mem.ladders
                          .sort((a, b) => a.level - b.level)
                          .filter(ladder => expandedMemories[mem.id] || ladder.level === mem.current_level)
                          .map((ladder, idx) => {
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

      {/* Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            style={{
              position: 'fixed',
              bottom: '24px',
              right: '24px',
              padding: '12px 24px',
              borderRadius: '8px',
              background: toast.type === 'success' ? 'var(--bg-card)' : 'rgba(239, 68, 68, 0.9)',
              color: toast.type === 'success' ? 'var(--accent-primary)' : 'white',
              border: toast.type === 'success' ? '1px solid var(--accent-primary)' : 'none',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)',
              zIndex: 1000,
              display: 'flex',
              alignItems: 'center',
              fontWeight: 500,
            }}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Delete Confirmation Toast */}
      <AnimatePresence>
        {memoryToDelete && (
          <motion.div
            initial={{ opacity: 0, y: 50, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: 50, x: '-50%' }}
            style={{
              position: 'fixed',
              bottom: '32px',
              left: '50%',
              padding: '16px 24px',
              borderRadius: '12px',
              background: 'var(--bg-card)',
              border: '1px solid var(--danger)',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
              zIndex: 1100,
              display: 'flex',
              alignItems: 'center',
              gap: '24px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <ShieldAlert size={20} color="var(--danger)" />
              <span style={{ fontWeight: 500 }}>Permanently delete this memory?</span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                className="btn btn-ghost btn-sm" 
                onClick={() => setMemoryToDelete(null)}
                style={{ padding: '6px 16px' }}
              >
                Cancel
              </button>
              <button 
                className="btn btn-sm" 
                onClick={() => executeDelete(memoryToDelete)}
                style={{ padding: '6px 16px', background: 'var(--danger)', color: 'white', border: 'none' }}
              >
                Delete
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
