/**
 * Chat page — main Q&A interface.
 *
 * Features:
 *   - Message history with user/assistant bubbles
 *   - Source citations with similarity scores
 *   - Performance metadata (latency, tokens)
 *   - Loading animation during queries
 *   - Welcome screen when no messages
 */

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { queryApi } from '../api/client';
import toast from 'react-hot-toast';
import { Send, Sparkles, BookOpen, Clock, Cpu } from 'lucide-react';

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const { user } = useAuth();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    setInput('');
    setLoading(true);

    try {
      const response = await queryApi.ask(question);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          metadata: response.metadata,
        },
      ]);
    } catch (err) {
      const msg = err.message || 'Query failed';
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${msg}`,
          isError: true,
        },
      ]);
      toast.error(msg);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || '?';

  return (
    <div className="chat-container">
      {/* Messages area */}
      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">
              <Sparkles size={32} color="white" />
            </div>
            <h2>What would you like to know?</h2>
            <p>
              Ask any question about your documents. I'll search through your
              authorized document corpus and provide citation-backed answers.
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-message ${msg.role}`}>
            <div className="chat-avatar">
              {msg.role === 'user' ? initials : <Sparkles size={16} />}
            </div>
            <div>
              <div
                className="chat-bubble"
                style={msg.isError ? { borderColor: 'rgba(239,68,68,0.3)' } : {}}
              >
                {msg.content}

                {/* Source citations */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="chat-sources">
                    <div className="chat-sources-title">
                      <BookOpen size={12} style={{ display: 'inline', marginRight: 4 }} />
                      Sources
                    </div>
                    {msg.sources.map((src, i) => (
                      <div key={i} className="chat-source-item">
                        <span className="chat-source-score">
                          {(src.similarity_score * 100).toFixed(0)}%
                        </span>
                        <span>{src.document_title}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Metadata */}
              {msg.metadata && (
                <div className="chat-metadata">
                  <span>
                    <Clock size={11} style={{ display: 'inline', marginRight: 3 }} />
                    {msg.metadata.latency_ms}ms
                  </span>
                  <span>
                    <Cpu size={11} style={{ display: 'inline', marginRight: 3 }} />
                    {msg.metadata.tokens_used} tokens
                  </span>
                  <span>
                    <BookOpen size={11} style={{ display: 'inline', marginRight: 3 }} />
                    {msg.metadata.chunks_retrieved} chunks
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="chat-message assistant">
            <div className="chat-avatar">
              <Sparkles size={16} />
            </div>
            <div className="chat-loading">
              <div className="chat-loading-dots">
                <span></span><span></span><span></span>
              </div>
              Searching documents…
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <form onSubmit={handleSubmit}>
          <div className="chat-input-wrapper">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder="Ask a question about your documents…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={loading}
            />
            <button
              type="submit"
              className="chat-send-btn"
              disabled={!input.trim() || loading}
              title="Send"
            >
              <Send size={16} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
