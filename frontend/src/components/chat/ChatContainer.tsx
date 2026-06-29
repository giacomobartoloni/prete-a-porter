'use client';

import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface ChatContainerProps {
  children: ReactNode;
  className?: string;
}

/**
 * Main chat wrapper component inspired by LangGraph Agent Chat UI.
 * Provides a clean, minimal container with proper layout structure.
 */
export function ChatContainer({ children, className }: ChatContainerProps) {
  return (
    <div 
      className={cn(
        'flex flex-col h-screen max-w-4xl mx-auto',
        'bg-bg-canvas',
        className
      )}
    >
      {children}
    </div>
  );
}

interface ChatHeaderProps {
  title: string;
  isConnected: boolean;
  className?: string;
}

export function ChatHeader({ title, isConnected, className }: ChatHeaderProps) {
  return (
    <header 
      className={cn(
        'bg-bg-raised/80 backdrop-blur-sm',
        'border-b border-border',
        'px-6 py-4',
        className
      )}
    >
      <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-text-primary">
          {title}
        </h1>
        <div className="flex items-center gap-2">
          <div 
            className={cn(
              'w-2 h-2 rounded-full transition-colors duration-300',
              isConnected 
                ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' 
                : 'bg-rose-500 shadow-sm shadow-rose-500/50'
            )} 
          />
          <span className={cn(
            'text-sm font-medium',
            isConnected ? 'text-text-secondary' : 'text-danger'
          )}>
            {isConnected ? 'Connesso' : 'Disconnesso'}
          </span>
        </div>
      </div>
    </header>
  );
}

interface ChatMainProps {
  children: ReactNode;
  className?: string;
}

export function ChatMain({ children, className }: ChatMainProps) {
  return (
    <main 
      className={cn(
        'flex-1 overflow-hidden',
        className
      )}
    >
      {children}
    </main>
  );
}

interface ChatFooterProps {
  children: ReactNode;
  className?: string;
}

export function ChatFooter({ children, className }: ChatFooterProps) {
  return (
    <footer 
      className={cn(
        'bg-bg-raised/80 backdrop-blur-sm',
        'border-t border-border',
        'px-6 py-4',
        className
      )}
    >
      {children}
    </footer>
  );
}