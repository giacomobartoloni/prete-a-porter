/**
 * Chat UI Components - Modern chat interface inspired by LangGraph Agent Chat UI
 * 
 * This module exports all chat-related components for building
 * conversational interfaces with rich message support.
 */

// Container components
export { 
  ChatContainer, 
  ChatHeader, 
  ChatMain, 
  ChatFooter 
} from './ChatContainer';

// Message display components
export { MessageList } from './MessageList';
export { 
  MessageBubble, 
  CompactMessageBubble, 
  SystemMessageBubble 
} from './MessageBubble';

// Tool call visualization
export { ToolCall, ToolCallList } from './ToolCall';
export type { ToolCallData } from './ToolCall';

// Input components
export { InputArea, CompactInputArea } from './InputArea';