import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Activity, Shield } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const USER_ID = "00000000-0000-0000-0000-000000000777";
const API_URL = "http://localhost:8000";

type Message = {
  id: string;
  role: 'user' | 'ai';
  content: string;
  metadata?: {
    maintenanceOps?: number;
    suggestedActions?: string[];
    confidenceScore?: number;
  }
};

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', role: 'ai', content: "Hello! I am your PGM Agent. I will remember what you tell me, but protect your privacy by generalizing facts if they make you too identifiable. What's on your mind?" }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: USER_ID, message: userMsg.content })
      });
      
      if (!res.ok) throw new Error('API Error');
      
      const data = await res.json();
      
      const aiMsg: Message = { 
        id: (Date.now() + 1).toString(), 
        role: 'ai', 
        content: data.answer,
        metadata: { 
          maintenanceOps: data.maintenance_ops_run,
          suggestedActions: data.suggested_actions,
          confidenceScore: data.confidence_score
        }
      };
      setMessages(prev => [...prev, aiMsg]);
      
    } catch (err) {
      const errorMsg: Message = { id: Date.now().toString(), role: 'ai', content: "Sorry, I encountered an error connecting to the PGM backend." };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <header className="content-header">
        <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Agent Interaction</h2>
        <div className="badge badge-info" style={{ display: 'flex', gap: '6px' }}>
          <Activity size={14} /> Live
        </div>
      </header>
      
      <div className="chat-container">
        <div className="chat-messages">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div 
                key={msg.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className={`message ${msg.role}`}
              >
                <div className="message-avatar">
                  {msg.role === 'ai' ? <Bot size={20} color="white" /> : <User size={20} color="var(--text-secondary)" />}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '100%' }}>
                  <div className="message-content">
                    {msg.content}
                  </div>
                  
                  {msg.metadata?.suggestedActions && msg.metadata.suggestedActions.length > 0 && (
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                      {msg.metadata.suggestedActions.map((action, idx) => (
                        <button 
                          key={idx} 
                          onClick={() => setInput(action)}
                          style={{ 
                            padding: '6px 12px', 
                            fontSize: '0.8rem', 
                            backgroundColor: 'var(--bg-card)', 
                            border: '1px solid var(--border)',
                            borderRadius: '16px',
                            cursor: 'pointer',
                            color: 'var(--text-primary)',
                            transition: 'background-color 0.2s'
                          }}
                          onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--border)'}
                          onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-card)'}
                        >
                          {action}
                        </button>
                      ))}
                    </div>
                  )}
                  
                  {msg.metadata?.confidenceScore !== undefined && msg.role === 'ai' && (
                     <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>
                        Confidence: {(msg.metadata.confidenceScore * 100).toFixed(0)}%
                     </div>
                  )}
                  {msg.metadata?.maintenanceOps !== undefined && msg.metadata.maintenanceOps > 0 && (
                    <motion.div 
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                      style={{ alignSelf: 'flex-start', fontSize: '0.75rem', color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      <Shield size={12} />
                      Privacy Budget Exceeded: Ran {msg.metadata.maintenanceOps} generalization operations in the background.
                    </motion.div>
                  )}
                </div>
              </motion.div>
            ))}
            
            {isLoading && (
              <motion.div 
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="message ai"
              >
                <div className="message-avatar">
                  <Bot size={20} color="white" />
                </div>
                <div className="message-content" style={{ display: 'flex', gap: '4px', alignItems: 'center', height: '24px' }}>
                  <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0 }} style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--text-secondary)' }} />
                  <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.2 }} style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--text-secondary)' }} />
                  <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.4 }} style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--text-secondary)' }} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
        
        <div className="chat-input-area">
          <div className="input-wrapper" style={{ display: 'flex', gap: '12px' }}>
            <input 
              type="text" 
              className="input" 
              placeholder="Tell me something about yourself..." 
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              disabled={isLoading}
            />
            <button className="btn btn-primary" onClick={handleSend} disabled={isLoading || !input.trim()} style={{ padding: '0 24px' }}>
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
