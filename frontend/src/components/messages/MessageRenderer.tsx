'use client';

import { RichMessage, isLiturgicalMessage, isPreferenceMessage, isHomilyMessage, isTextMessage } from '@/types';
import LiturgicalCard from './LiturgicalCard';
import PreferencePicker from './PreferencePicker';
import HomilyDisplay from './HomilyDisplay';
import { useTranslations } from 'next-intl';
import ReactMarkdown from 'react-markdown';

interface MessageRendererProps {
  message: RichMessage;
}

export default function MessageRenderer({ message }: MessageRendererProps) {
  const t = useTranslations('messages');
  if (isLiturgicalMessage(message)) {
    return <LiturgicalCard data={message.data} />;
  }

  if (isPreferenceMessage(message)) {
    return <PreferencePicker preferences={message.preferences} />;
  }

  if (isHomilyMessage(message)) {
    return <HomilyDisplay homily={message.homily} sources={message.sources} />;
  }

  if (isTextMessage(message)) {
    if (message.type === 'user') {
      return <p className="whitespace-pre-wrap">{message.content}</p>;
    }
    return (
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown>{message.content}</ReactMarkdown>
      </div>
    );
  }

  // Fallback for unknown message types
  return <p className="text-text-tertiary">{t("unknown_type")}</p>;
}