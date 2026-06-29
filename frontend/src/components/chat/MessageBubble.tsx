'use client';

import { RichMessage, isLiturgicalMessage, isPreferenceMessage, isHomilyMessage, isTextMessage } from '@/types';
import { MessageRenderer } from '../messages';
import { User, Bot, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MessageBubbleProps {
  message: RichMessage;
  className?: string;
  showAvatar?: boolean;
}

/**
 * Individual message bubble component with variants for user/assistant.
 * Inspired by LangGraph Agent Chat UI's message styling.
 */
export function MessageBubble({ 
  message, 
  className,
  showAvatar = true 
}: MessageBubbleProps) {
  const isUser = message.type === 'user';
  const isRichContent = message.contentType !== 'text';

  return (
    <div 
      className={cn(
        'flex gap-3',
        isUser ? 'flex-row-reverse' : 'flex-row',
        className
      )}
    >
      {/* Avatar */}
      {showAvatar && (
        <div 
          className={cn(
            'flex-shrink-0 w-8 h-8 rounded-full',
            'flex items-center justify-center',
            'transition-transform duration-200 hover:scale-110',
            isUser 
              ? 'bg-blue-500 text-white shadow-sm shadow-blue-500/30' 
              : 'bg-gradient-to-br from-violet-500 to-purple-600 text-white shadow-sm shadow-violet-500/30'
          )}
        >
          {isUser ? (
            <User className="w-4 h-4" />
          ) : (
            <Bot className="w-4 h-4" />
          )}
        </div>
      )}

      {/* Message content */}
      <div 
        className={cn(
          'flex flex-col gap-1',
          'max-w-[85%] md:max-w-[75%]',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        {/* Timestamp */}
        {message.timestamp && (
          <span 
            className={cn(
              'text-xs text-text-tertiary',
              isUser ? 'text-right' : 'text-left',
              'px-1'
            )}
          >
            {formatTime(message.timestamp)}
          </span>
        )}

        {/* Bubble */}
        <div 
          className={cn(
            'relative',
            'rounded-2xl',
            isUser 
              ? 'rounded-br-md bg-blue-500 text-white' 
              : isRichContent
                ? 'bg-transparent p-0'
                : 'rounded-bl-md bg-bg-card border border-border text-text-primary',
            !isRichContent && !isUser && 'px-4 py-3',
            !isRichContent && isUser && 'px-4 py-3 shadow-sm shadow-blue-500/20'
          )}
        >
          {isRichContent ? (
            <MessageRenderer message={message} />
          ) : isTextMessage(message) ? (
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
              {message.content}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/**
 * Compact message bubble for tool calls and system messages.
 */
export function CompactMessageBubble({ 
  message, 
  className 
}: { 
  message: { type: string; content: string };
  className?: string;
}) {
  return (
    <div 
      className={cn(
        'flex items-center gap-2',
        'px-3 py-2 rounded-lg',
        'bg-bg-overlay',
        'text-xs text-text-secondary',
        className
      )}
    >
      <Sparkles className="w-3 h-3" />
      <span>{message.content}</span>
    </div>
  );
}

/**
 * System message bubble for notifications and status updates.
 */
export function SystemMessageBubble({ 
  children, 
  className 
}: { 
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div 
      className={cn(
        'flex justify-center',
        'py-2',
        className
      )}
    >
      <div 
        className={cn(
          'px-4 py-1.5 rounded-full',
          'bg-bg-overlay',
          'text-xs text-text-secondary',
          'border border-border'
        )}
      >
        {children}
      </div>
    </div>
  );
}

// Helper function to format timestamp
function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('it-IT', { 
    hour: '2-digit', 
    minute: '2-digit' 
  });
}