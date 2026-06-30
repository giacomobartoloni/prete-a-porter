'use client';

import { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { Send } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  RichMessage,
  TextMessage,
  LiturgicalMessage,
  PreferenceMessage,
  HomilyMessage,
  HistoryMessage,
} from '@/types';
import { MessageRenderer } from './messages';
import { getConversation, createConversation, updateConversation } from '@/lib/conversations';
import { generateId } from '@/lib/id';

function getHistoryFromMessages(msgs: RichMessage[]): HistoryMessage[] {
  return msgs.map(m => {
    let content = '';
    if (m.contentType === 'text') {
      content = (m as TextMessage).content;
    } else if (m.contentType === 'liturgical') {
      content = JSON.stringify((m as LiturgicalMessage).data);
    } else if (m.contentType === 'homily') {
      content = JSON.stringify((m as HomilyMessage).homily);
    } else if (m.contentType === 'preferences') {
      content = JSON.stringify((m as PreferenceMessage).preferences);
    }
    return { role: m.type, content, contentType: m.contentType };
  });
}

function parseAssistantMessage(content: string): RichMessage {
  try {
    const parsed = JSON.parse(content);

    if (parsed.readings || (parsed.metadata && parsed.first_reading)) {
      return {
        type: 'assistant',
        contentType: 'liturgical',
        id: generateId(),
        data: parsed.readings || parsed,
        timestamp: Date.now(),
      } as LiturgicalMessage;
    }

    if (parsed.homily || (parsed.introduction && parsed.reading_reflection)) {
      return {
        type: 'assistant',
        contentType: 'homily',
        id: generateId(),
        homily: parsed.homily || parsed,
        sources: parsed.sources,
        timestamp: Date.now(),
      } as HomilyMessage;
    }

    if (parsed.preferences || parsed.target_audience || parsed.tone) {
      return {
        type: 'assistant',
        contentType: 'preferences',
        id: generateId(),
        preferences: parsed.preferences || parsed,
        timestamp: Date.now(),
      } as PreferenceMessage;
    }

    if (Array.isArray(parsed)) {
      const text = parsed
        .filter((b: Record<string, unknown>) => b.type === 'text')
        .map((b: Record<string, unknown>) => b.text)
        .join('\n');
      if (text) {
        return {
          type: 'assistant',
          contentType: 'text',
          id: generateId(),
          content: text,
          timestamp: Date.now(),
        } as TextMessage;
      }
    }
  } catch {
    // Not JSON, treat as plain text
  }

  return {
    type: 'assistant',
    contentType: 'text',
    id: generateId(),
    content: content,
    timestamp: Date.now(),
  } as TextMessage;
}

function loadMessagesFromHistory(history: HistoryMessage[]): RichMessage[] {
  return history.map((m, i) => {
    if (m.role === 'user') {
      return {
        type: 'user',
        contentType: (m.contentType as RichMessage['contentType']) || 'text',
        id: `history-${i}`,
        content: m.content,
        timestamp: Date.now(),
      } as TextMessage;
    }
    return parseAssistantMessage(m.content);
  });
}

export default function Chat({ conversationId }: { conversationId: string | null }) {
  const [messages, setMessages] = useState<RichMessage[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [version, setVersion] = useState('');
  const t = useTranslations('chat');
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>('');
  const convIdRef = useRef<string | null>(null);
  const titleSetRef = useRef(false);
  const messagesRef = useRef<RichMessage[]>([]);
  const cancelledRef = useRef(false);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    cancelledRef.current = false;
    convIdRef.current = null;
    titleSetRef.current = false;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const init = async () => {
      try {
        let sessionId: string;
        let convMessages: HistoryMessage[] = [];

        if (conversationId) {
          const conv = await getConversation(conversationId);
          if (cancelledRef.current) return;
          convMessages = conv.messages;
          sessionId = conv.sessionId;
          convIdRef.current = conversationId;
          titleSetRef.current = conv.title !== 'Nuova conversazione';
        } else {
          const conv = await createConversation();
          if (cancelledRef.current) return;
          sessionId = conv.sessionId;
          convIdRef.current = conv.id;
          titleSetRef.current = false;
          window.history.replaceState(null, '', `/chat?convId=${conv.id}`);
          window.dispatchEvent(new Event('conversation-created'));
        }

        if (cancelledRef.current) return;

        const loadedMessages = loadMessagesFromHistory(convMessages);
        setMessages(loadedMessages);

        sessionIdRef.current = sessionId;

        const res = await fetch('/api/auth/ws-token', { method: 'POST' });
        if (cancelledRef.current) return;
        if (!res.ok) {
          setAuthError(t('auth_error'));
          return;
        }
        const { token } = await res.json();
        if (cancelledRef.current) return;

        const configRes = await fetch('/api/config');
        const { wsUrl, version: ver } = await configRes.json();
        if (cancelledRef.current) return;
        setVersion(`v${ver}`);

        const ws = new WebSocket(`${wsUrl}/${sessionId}`, [token]);
        if (cancelledRef.current) { ws.close(); return; }
        wsRef.current = ws;

        ws.onopen = () => {
          if (cancelledRef.current) { ws.close(); return; }
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          if (cancelledRef.current) return;
          try {
            const data = JSON.parse(event.data);

            if (data.type === 'message') {
              const content = typeof data.content === 'string' ? data.content : JSON.stringify(data.content);
              const richMessage = parseAssistantMessage(content);
              const currentMsgs = messagesRef.current;
              const updated = [...currentMsgs, richMessage];
              messagesRef.current = updated;
              setMessages(updated);
              setIsLoading(false);

              if (convIdRef.current) {
                const history = getHistoryFromMessages(updated);
                updateConversation(convIdRef.current, { messages: history }).catch(console.error);
              }
            } else if (data.type === 'loading') {
              setIsLoading(data.content);
            }
          } catch (error) {
            console.error('Failed to parse message:', error);
          }
        };

        ws.onclose = (event) => {
          if (cancelledRef.current) return;
          if (event.code === 4001) {
            setAuthError(t('session_expired'));
            return;
          }
          setIsConnected(false);
        };

        ws.onerror = () => {
          setIsConnected(false);
        };

      } catch (e) {
        if (!cancelledRef.current) {
          console.error('Failed to initialize chat:', e);
        }
      }
    };

    init();

    return () => {
      cancelledRef.current = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
    };
  }, [conversationId]);

  const sendMessage = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || !input.trim()) return;

    const text = input.trim();

    const historyBefore = getHistoryFromMessages(messagesRef.current);

    const userMessage: TextMessage = {
      type: 'user',
      contentType: 'text',
      id: generateId(),
      content: text,
      timestamp: Date.now(),
    };

    const updated = [...messagesRef.current, userMessage];
    messagesRef.current = updated;
    setMessages(updated);

    if (convIdRef.current) {
      const history = getHistoryFromMessages(updated);
      updateConversation(convIdRef.current, { messages: history }).catch(console.error);

      if (!titleSetRef.current) {
        updateConversation(convIdRef.current, { title: text.slice(0, 50) }).catch(console.error);
        titleSetRef.current = true;
        window.dispatchEvent(new Event('conversation-created'));
      }
    }

    wsRef.current.send(JSON.stringify({ text, history: historyBefore }));
    setInput('');
    setIsLoading(true);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const isRichMessage = (msg: RichMessage): boolean => {
    return msg.contentType !== 'text';
  };

  const suggestions = [
    { label: t('today_readings'), desc: t('today_readings_desc') },
    { label: t('sunday_homily'), desc: t('sunday_homily_desc') },
    { label: t('wedding_readings'), desc: t('wedding_readings_desc') },
  ];

  const inputSection = (showIndicator: boolean) => (
    <div className={showIndicator ? "px-4 sm:px-6 py-4" : ""}>
      <div className={showIndicator ? "max-w-4xl mx-auto" : ""}>
        <div className="flex items-end gap-3 bg-bg-card rounded-2xl border border-border px-4 py-2 focus-within:border-accent-blue focus-within:ring-2 focus-within:ring-accent-blue/20 transition-all shadow-sm">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={t('input_placeholder')}
            className="flex-1 resize-none border-0 bg-transparent px-2 py-2 focus:outline-none focus:ring-0 placeholder:text-text-tertiary text-sm text-text-primary leading-relaxed disabled:opacity-50"
            rows={1}
            disabled={!isConnected}
            onInput={(e) => {
              const ta = e.target as HTMLTextAreaElement;
              ta.style.height = 'auto';
              ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!isConnected || !input.trim() || isLoading}
            className="flex items-center justify-center w-10 h-10 bg-accent-violet text-white rounded-xl hover:bg-accent-violet/90 disabled:bg-bg-overlay disabled:text-text-tertiary disabled:cursor-not-allowed transition-all shrink-0 shadow-sm"
          >
            <Send size={18} />
          </button>
        </div>
        {showIndicator && (
          <div className="flex items-center justify-between mt-2 px-1">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-success' : 'bg-danger'}`} />
              <span className="text-xs text-text-tertiary">
                {isConnected ? t('connected') : t('disconnected')}
              </span>
            </div>
            <span className="text-xs text-text-tertiary">
              Prete-a-porter {version}
            </span>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      {messages.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-lg w-full mx-auto px-4 flex flex-col items-center text-center">
            <Image src="/logo.png" alt="Prete-a-porter" width={512} height={512} className="w-48 h-48 mb-4 logo-glow" />
            <h2 className="text-xl font-serif font-semibold text-text-primary mb-2">
              Prete-a-porter
            </h2>
            <p className="text-text-tertiary max-w-md text-sm">
              {t('empty_state_description')}
            </p>
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-lg w-full">
              {suggestions.map((s) => (
                <button
                  key={s.label}
                  onClick={() => {
                    const ta = document.querySelector('textarea');
                    if (ta) { ta.value = s.label; setInput(s.label); }
                  }}
                  className="p-3 rounded-xl border border-border bg-bg-card hover:bg-bg-overlay transition-all text-left"
                >
                  <div className="text-sm font-medium text-text-primary">{s.label}</div>
                  <div className="text-xs text-text-tertiary mt-0.5">{s.desc}</div>
                </button>
              ))}
            </div>

            {authError && (
              <div className="mt-6 w-full bg-danger/10 border border-danger/30 text-danger px-4 py-3 rounded-xl flex items-center justify-between">
                <span className="text-sm">{authError}</span>
                <button onClick={() => window.location.reload()} className="text-sm font-bold text-danger hover:text-danger/80 ml-3 whitespace-nowrap">
                  {t('reload')}
                </button>
              </div>
            )}

            <div className="mt-6 w-full max-w-lg">
              {inputSection(false)}
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-4xl mx-auto px-[12px] py-6 space-y-4 min-h-full">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] sm:max-w-[70%] ${
                      message.type === 'user'
                        ? 'bg-gradient-to-br from-liturgy-600 to-violet-600 text-white rounded-2xl rounded-br-md px-[12px] py-3'
                        : isRichMessage(message)
                        ? 'bg-transparent'
                        : 'bg-bg-card border border-border text-text-primary rounded-2xl rounded-bl-md px-[12px] py-3'
                    }`}
                  >
                    <MessageRenderer message={message} />
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-bg-card border border-border rounded-2xl rounded-bl-md px-[12px] py-3">
                    <div className="flex gap-1.5 pl-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-text-tertiary animate-bounce" style={{animationDelay: '0ms'}} />
                      <span className="w-2.5 h-2.5 rounded-full bg-text-tertiary animate-bounce" style={{animationDelay: '150ms'}} />
                      <span className="w-2.5 h-2.5 rounded-full bg-text-tertiary animate-bounce" style={{animationDelay: '300ms'}} />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {authError && (
            <div className="mx-4 sm:mx-6 mb-4 bg-danger/10 border border-danger/30 text-danger px-4 py-3 rounded-xl flex items-center justify-between">
              <span className="text-sm">{authError}</span>
              <button onClick={() => window.location.reload()} className="text-sm font-bold text-danger hover:text-danger/80 ml-3 whitespace-nowrap">
                {t('reload')}
              </button>
            </div>
          )}

          {inputSection(true)}
        </>
      )}
    </div>
  );
}
