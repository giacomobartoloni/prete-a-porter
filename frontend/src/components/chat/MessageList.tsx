'use client';

import { useRef, useEffect, useCallback, useMemo } from 'react';
import { RichMessage } from '@/types';
import { MessageBubble } from './MessageBubble';
import { Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';

interface MessageListProps {
  messages: RichMessage[];
  isLoading?: boolean;
  className?: string;
  emptyMessage?: string;
}

/**
 * Virtualized message list component with smooth scrolling.
 * Inspired by LangGraph Agent Chat UI's message display.
 */
export function MessageList({ 
  messages, 
  isLoading = false,
  className,
  emptyMessage
}: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const t = useTranslations('chat');
  const containerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(0);

  // Memoize messages to prevent unnecessary re-renders
  const memoizedMessages = useMemo(() => messages, [messages]);

  // Smooth scroll to bottom when new messages arrive
  useEffect(() => {
    if (memoizedMessages.length > prevMessagesLengthRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevMessagesLengthRef.current = memoizedMessages.length;
  }, [memoizedMessages]);

  // Handle scroll position for virtualization optimization
  const handleScroll = useCallback(() => {
    // Future: Implement virtualization for large message lists
  }, []);

  if (memoizedMessages.length === 0 && !isLoading) {
    return (
      <div 
        className={cn(
          'flex items-center justify-center h-full',
          'text-text-tertiary',
          className
        )}
      >
        <div className="text-center space-y-2">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-bg-overlay flex items-center justify-center">
            <svg 
              className="w-8 h-8 text-text-tertiary" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={1.5} 
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" 
              />
            </svg>
          </div>
          <p className="text-sm font-medium">{emptyMessage}</p>
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      onScroll={handleScroll}
      className={cn(
        'flex-1 overflow-y-auto',
        'px-4 md:px-6 py-4',
        'scroll-smooth',
        className
      )}
    >
      <div className="space-y-4 max-w-3xl mx-auto">
        {memoizedMessages.map((message, index) => (
          <MessageBubble 
            key={`${message.timestamp}-${index}`} 
            message={message} 
          />
        ))}
        
        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div 
              className={cn(
                'flex items-center gap-2.5',
                'px-4 py-3 rounded-2xl rounded-bl-md',
                'bg-bg-card border border-border'
              )}
            >
              <Loader2 className="w-4 h-4 animate-spin text-text-tertiary" />
              <span className="text-sm text-text-secondary">
                Sto generando...
              </span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} className="h-1" />
      </div>
    </div>
  );
}