'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Wrench, CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';

export interface ToolCallData {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'success' | 'error';
  input?: Record<string, unknown>;
  output?: unknown;
  error?: string;
  duration?: number;
}

interface ToolCallProps {
  tool: ToolCallData;
  className?: string;
  defaultExpanded?: boolean;
}

/**
 * Tool call visualization component inspired by LangGraph Agent Chat UI.
 * Displays tool invocations with expandable input/output details.
 */
export function ToolCall({ 
  tool, 
  className,
  defaultExpanded = false 
}: ToolCallProps) {
  const t = useTranslations('tool_call');
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const statusConfig = {
    pending: {
      icon: Clock,
      color: 'text-text-tertiary',
      bg: 'bg-bg-overlay',
      border: 'border-border',
      label: t('pending')
    },
    running: {
      icon: Loader2,
      color: 'text-warning',
      bg: 'bg-bg-overlay',
      border: 'border-border',
      label: t('running')
    },
    success: {
      icon: CheckCircle,
      color: 'text-success',
      bg: 'bg-bg-overlay',
      border: 'border-border',
      label: t('completed')
    },
    error: {
      icon: XCircle,
      color: 'text-danger',
      bg: 'bg-bg-overlay',
      border: 'border-border',
      label: t('error')
    }
  };

  const config = statusConfig[tool.status];
  const StatusIcon = config.icon;

  return (
    <div 
      className={cn(
        'rounded-lg border',
        config.bg,
        config.border,
        'overflow-hidden',
        className
      )}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          'w-full flex items-center gap-3',
          'px-3 py-2',
          'hover:bg-bg-overlay',
          'transition-colors duration-150',
          'text-left'
        )}
      >
        {/* Expand icon */}
        <span className="flex-shrink-0 text-text-tertiary">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </span>

        {/* Tool icon */}
        <div className={cn(
          'flex-shrink-0 w-6 h-6 rounded-md',
          'flex items-center justify-center',
          'bg-bg-card',
          'border border-border',
        )}>
          <Wrench className="w-3 h-3 text-text-secondary" />
        </div>

        {/* Tool name */}
        <span className="flex-1 text-sm font-medium text-text-primary">
          {tool.name}
        </span>

        {/* Status */}
        <div className={cn(
          'flex items-center gap-1.5',
          config.color
        )}>
          <StatusIcon className={cn(
            'w-4 h-4',
            tool.status === 'running' && 'animate-spin'
          )} />
          <span className="text-xs font-medium">
            {config.label}
          </span>
        </div>

        {/* Duration */}
        {tool.duration !== undefined && (
          <span className="text-xs text-text-tertiary">
            {tool.duration}ms
          </span>
        )}
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-border">
          {/* Input */}
          {tool.input && Object.keys(tool.input).length > 0 && (
            <div className="px-3 py-2 border-b border-border">
              <div className="text-xs font-medium text-text-secondary mb-1">
                Input
              </div>
              <pre className="text-xs text-text-primary overflow-x-auto">
                {JSON.stringify(tool.input, null, 2)}
              </pre>
            </div>
          )}

          {/* Output */}
          {tool.output !== undefined && tool.status === 'success' && (
            <div className="px-3 py-2">
              <div className="text-xs font-medium text-text-secondary mb-1">
                Output
              </div>
              <pre className="text-xs text-text-primary overflow-x-auto">
                {typeof tool.output === 'string' 
                  ? tool.output 
                  : JSON.stringify(tool.output, null, 2)
                }
              </pre>
            </div>
          )}

          {/* Error */}
          {tool.error && (
            <div className="px-3 py-2 bg-danger/10">
              <div className="text-xs font-medium text-danger mb-1">
                Errore
              </div>
              <pre className="text-xs text-danger overflow-x-auto whitespace-pre-wrap">
                {tool.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ToolCallListProps {
  tools: ToolCallData[];
  className?: string;
}

/**
 * List of tool calls with grouped display.
 */
export function ToolCallList({ tools, className }: ToolCallListProps) {
  if (tools.length === 0) return null;

  return (
    <div className={cn('space-y-2', className)}>
      {tools.map((tool) => (
        <ToolCall key={tool.id} tool={tool} />
      ))}
    </div>
  );
}