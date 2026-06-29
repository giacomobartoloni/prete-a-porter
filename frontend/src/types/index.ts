export type MessageType = 'user' | 'assistant';

export interface BaseMessage {
  type: MessageType;
  id: string;
  timestamp?: number;
}

export interface TextMessage extends BaseMessage {
  contentType: 'text';
  content: string;
}

export interface Reading {
  reference: string;
  text: string;
  type: 'First' | 'Second' | 'Gospel' | 'Psalm' | 'Alleluia';
}

export interface LiturgicalMetadata {
  date: string;
  occasion: 'mass' | 'marriage' | 'baptism' | 'funeral';
  season: string;
  color: string;
  year_cycle: 'A' | 'B' | 'C';
  sunday_or_weekday: string;
}

export interface LiturgicalData {
  date: string;
  occasion: 'mass' | 'marriage' | 'baptism' | 'funeral';
  metadata: LiturgicalMetadata;
  first_reading: Reading;
  psalm: Reading;
  second_reading?: Reading;
  gospel: Reading;
  alleluia_verse?: Reading;
}

export interface LiturgicalMessage extends BaseMessage {
  contentType: 'liturgical';
  data: LiturgicalData;
}

export interface UserPreferences {
  target_audience?: 'adults' | 'youth' | 'children' | 'mixed';
  tone?: 'formal' | 'conversational' | 'poetic' | 'consolatory' | 'celebratory';
  length?: 'short' | 'medium' | 'long';
  themes?: string[];
  metaphors?: string[];
  analogies?: string[];
  parables?: string[];
}

export interface PreferenceMessage extends BaseMessage {
  contentType: 'preferences';
  preferences: UserPreferences;
}

export interface HomilySection {
  title: string;
  content: string;
}

export interface GeneratedHomily {
  introduction: HomilySection;
  reading_reflection: HomilySection;
  practical_application: HomilySection;
  conclusion: HomilySection;
  occasion: 'mass' | 'marriage' | 'baptism' | 'funeral';
  liturgical_date: string;
}

export interface HomilyMessage extends BaseMessage {
  contentType: 'homily';
  homily: GeneratedHomily;
  sources?: string[];
}

export type RichMessage = TextMessage | LiturgicalMessage | PreferenceMessage | HomilyMessage;

export function isLiturgicalMessage(message: RichMessage): message is LiturgicalMessage {
  return message.contentType === 'liturgical';
}

export function isPreferenceMessage(message: RichMessage): message is PreferenceMessage {
  return message.contentType === 'preferences';
}

export function isHomilyMessage(message: RichMessage): message is HomilyMessage {
  return message.contentType === 'homily';
}

export function isTextMessage(message: RichMessage): message is TextMessage {
  return message.contentType === 'text';
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  contentType?: string;
}

export interface Conversation {
  id: string;
  userId: string;
  sessionId: string;
  title: string;
  messages: HistoryMessage[];
  createdAt: string;
  updatedAt: string;
}