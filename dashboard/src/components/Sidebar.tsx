import { NavLink } from 'react-router-dom';
import { MessageSquare, Database, Shield, Zap } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div style={{ padding: '32px 24px', borderBottom: '1px solid var(--border-glass)' }}>
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}
        >
          <div style={{ 
            width: 32, height: 32, borderRadius: 8, 
            background: 'var(--accent-gradient)', 
            display: 'flex', alignItems: 'center', justifyContent: 'center' 
          }}>
            <Shield size={18} color="white" />
          </div>
          <h2 style={{ fontSize: '1.25rem', margin: 0 }} className="text-gradient">PGM</h2>
        </motion.div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Progressive Generalization Memory
        </p>
      </div>

      <nav style={{ padding: '24px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <NavLink 
          to="/" 
          style={({ isActive }) => ({
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '12px 16px', borderRadius: '12px',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
            textDecoration: 'none',
            fontWeight: 500,
            transition: 'all 0.2s ease'
          })}
        >
          <MessageSquare size={18} />
          Chat Agent
        </NavLink>
        
        <NavLink 
          to="/memories" 
          style={({ isActive }) => ({
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '12px 16px', borderRadius: '12px',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
            textDecoration: 'none',
            fontWeight: 500,
            transition: 'all 0.2s ease'
          })}
        >
          <Database size={18} />
          Memory Vault
        </NavLink>

        <NavLink 
          to="/risk" 
          style={({ isActive }) => ({
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '12px 16px', borderRadius: '12px',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
            textDecoration: 'none',
            fontWeight: 500,
            transition: 'all 0.2s ease'
          })}
        >
          <Zap size={18} />
          Risk Metrics
        </NavLink>
      </nav>

      <div style={{ marginTop: 'auto', padding: '24px' }}>
        <div className="glass-panel" style={{ padding: '16px', border: '1px solid rgba(99, 102, 241, 0.2)', background: 'rgba(99, 102, 241, 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Zap size={16} color="var(--accent-primary)" />
            <h4 style={{ fontSize: '0.9rem', margin: 0, color: 'var(--accent-primary)' }}>System Status</h4>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
            Risk Engine Active. Generalization ladders online.
          </p>
        </div>
      </div>
    </aside>
  );
}
