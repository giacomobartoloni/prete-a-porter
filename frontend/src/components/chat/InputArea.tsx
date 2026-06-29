'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { Send, Paperclip, Mic, Square } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';

interface InputAreaProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isDisabled?: boolean;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
  maxLength?: number;
  showAttachments?: boolean;
  showVoice?: boolean;
}

/**
 * Message input component with auto-resize and modern styling.
 * Inspired by LangGraph Agent Chat UI's input design.
 */
export function InputArea({
  value,
  onChange,
  onSend,
  isDisabled = false,
  isLoading = false,
  placeholder = 'Scrivi il tuo messaggio...',
  className,
  maxLength = 4000,
  showAttachments = false,
  showVoice = false,
}: InputAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const t = useTranslations('chat');
  const [isFocused, setIsFocused] = useState(false);

  // Auto-resize textarea based on content
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto';
    
    // Calculate new height (min 44px, max 200px)
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 44), 200);
    textarea.style.height = `${newHeight}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isDisabled && !isLoading && value.trim()) {
        onSend();
      }
    }
  };

  // Handle send button click
  const handleSend = () => {
    if (!isDisabled && !isLoading && value.trim()) {
      onSend();
      // Reset textarea height after sending
      if (textareaRef.current) {
        textareaRef.current.style.height = '44px';
      }
    }
  };

  const canSend = !isDisabled && !isLoading && value.trim().length > 0;
  const characterCount = value.length;
  const isNearLimit = characterCount > maxLength * 0.9;

  return (
    <div 
      className={cn(
        'relative',
        className
      )}
    >
      <div 
        className={cn(
          'flex items-end gap-2',
          'bg-bg-card',
          'border border-border',
          'rounded-2xl',
          'transition-all duration-200',
          isFocused && 'ring-2 ring-blue-500/20 border-blue-500/50',
          isDisabled && 'opacity-60 cursor-not-allowed'
        )}
      >
        {/* Attachment button */}
        {showAttachments && (
          <button
            type="button"
            disabled={isDisabled}
            className={cn(
              'flex-shrink-0 p-2.5 ml-1 mb-1',
              'text-text-tertiary hover:text-text-secondary',
              'hover:bg-bg-overlay',
              'rounded-lg',
              'transition-colors duration-150',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
            title={t('attach_file')}
          >
            <Paperclip className="w-5 h-5" />
          </button>
        )}

        {/* Textarea */}
        <div className="flex-1 relative py-2">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value.slice(0, maxLength))}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            disabled={isDisabled}
            placeholder={placeholder}
            rows={1}
            className={cn(
              'w-full resize-none',
              'bg-transparent',
              'text-text-primary',
              'placeholder:text-text-tertiary',
              'focus:outline-none',
              'text-sm leading-relaxed',
              'px-3',
              'disabled:cursor-not-allowed'
            )}
            style={{ minHeight: '44px', maxHeight: '200px' }}
          />
        </div>

        {/* Character count */}
        {characterCount > 0 && (
          <span 
            className={cn(
              'flex-shrink-0 text-xs pb-3 pr-2',
              isNearLimit 
                ? 'text-warning' 
                : 'text-text-tertiary'
            )}
          >
            {characterCount}/{maxLength}
          </span>
        )}

        {/* Voice button */}
        {showVoice && (
          <button
            type="button"
            disabled={isDisabled}
            className={cn(
              'flex-shrink-0 p-2.5 mr-1 mb-1',
              'text-text-tertiary hover:text-text-secondary',
              'hover:bg-bg-overlay',
              'rounded-lg',
              'transition-colors duration-150',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
            title={t('record_voice')}
          >
            <Mic className="w-5 h-5" />
          </button>
        )}

        {/* Send/Stop button */}
        <button
          type="button"
          onClick={isLoading ? undefined : handleSend}
          disabled={!canSend && !isLoading}
          className={cn(
            'flex-shrink-0 p-2.5 mr-1 mb-1',
            'rounded-lg',
            'transition-all duration-200',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            isLoading
              ? 'bg-rose-500 text-white hover:bg-rose-600'
              : canSend
                ? 'bg-accent-blue text-white hover:bg-accent-blue/90'
                : 'bg-bg-overlay text-text-tertiary'
          )}
          title={isLoading ? t('stop') : t('send_message')}
        >
          {isLoading ? (
            <Square className="w-5 h-5" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Keyboard shortcut hint */}
      <div className="mt-1.5 flex justify-between px-1">
        <span className="text-xs text-text-tertiary">
          <kbd className="px-1.5 py-0.5 text-xs bg-bg-overlay rounded border border-border">
            Invio
          </kbd>
          {' '}per inviare,{' '}
          <kbd className="px-1.5 py-0.5 text-xs bg-bg-overlay rounded border border-border">
            Shift+Invio
          </kbd>
          {' '}per nuova riga
        </span>
      </div>
    </div>
  );
}

/**
 * Compact input area for inline replies.
 */
export function CompactInputArea({
  value,
  onChange,
  onSend,
  isDisabled = false,
  isLoading = false,
  placeholder = 'Rispondi...',
  className,
}: InputAreaProps) {
  return (
    <div 
      className={cn(
        'flex items-center gap-2',
        'bg-bg-overlay',
        'border border-border',
        'rounded-lg px-3 py-2',
        className
      )}
    >
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!isDisabled && !isLoading && value.trim()) {
              onSend();
            }
          }
        }}
        disabled={isDisabled}
        placeholder={placeholder}
        className={cn(
          'flex-1 bg-transparent',
          'text-sm text-text-primary',
          'placeholder:text-text-tertiary',
          'focus:outline-none',
          'disabled:cursor-not-allowed'
        )}
      />
      <button
        type="button"
        onClick={onSend}
        disabled={!value.trim() || isDisabled || isLoading}
        className={cn(
          'p-1.5 rounded-md',
          'text-text-tertiary hover:text-blue-500',
          'hover:bg-bg-overlay',
          'transition-colors duration-150',
          'disabled:opacity-50 disabled:cursor-not-allowed'
        )}
      >
        <Send className="w-4 h-4" />
      </button>
    </div>
  );
}