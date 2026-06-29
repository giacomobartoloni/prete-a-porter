'use client';

import { useTranslations } from 'next-intl';
import { BookOpen, Calendar, Church } from 'lucide-react';
import { LiturgicalData } from '@/types';

interface LiturgicalCardProps {
  data: LiturgicalData;
}





const colorMap: Record<string, string> = {
  White: 'border-border',
  Green: 'border-success/50',
  Red: 'border-danger/50',
  Purple: 'border-accent-violet/50',
  Violet: 'border-accent-violet/50',
  Pink: 'border-accent-violet/30',
};

export default function LiturgicalCard({ data }: LiturgicalCardProps) {
  const t = useTranslations('liturgy');
  const colorClass = colorMap[data.metadata.color] || 'border-border';

  const getOccasionEmoji = () => {
    switch (data.metadata.occasion) {
      case 'mass':
        return <Church className="w-5 h-5" />;
      case 'marriage':
        return '💒';
      case 'baptism':
        return '🕊️';
      case 'funeral':
        return '🕯️';
      default:
        return <BookOpen className="w-5 h-5" />;
    }
  };

  return (
    <div className={`rounded-lg border bg-bg-card ${colorClass} p-4 max-w-2xl`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">{getOccasionEmoji()}</span>
          <span className="font-semibold text-text-primary">
            {t('occasion.' + data.metadata.occasion) || data.metadata.occasion}
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Calendar className="w-4 h-4" />
          <span>{data.metadata.date}</span>
          <span className="text-text-tertiary">|</span>
          <span>{t('season.' + data.metadata.season) || data.metadata.season}</span>
          <span className="text-text-tertiary">|</span>
          <span>{t('year')} {data.metadata.year_cycle}</span>
        </div>
      </div>

      {/* Readings */}
      <div className="space-y-3">
        {data.first_reading && (
          <ReadingItem
            label={t('first_reading')}
            reading={data.first_reading}
          />
        )}

        {data.psalm && (
          <ReadingItem
            label={t('psalm')}
            reading={data.psalm}
          />
        )}

        {data.second_reading && (
          <ReadingItem
            label={t('second_reading')}
            reading={data.second_reading}
          />
        )}

        {data.gospel && (
          <ReadingItem
            label={t('gospel')}
            reading={data.gospel}
            isGospel
          />
        )}
      </div>
    </div>
  );
}

interface ReadingItemProps {
  label: string;
  reading: { reference: string; text: string };
  isGospel?: boolean;
}

function ReadingItem({ label, reading, isGospel }: ReadingItemProps) {
  return (
    <div className={isGospel ? 'bg-warning/10 -mx-4 px-4 py-2 -my-2 border-l-4 border-warning/50' : ''}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs font-medium uppercase ${isGospel ? 'text-warning' : 'text-text-tertiary'}`}>
          {label}
        </span>
        <span className={`text-sm font-semibold ${isGospel ? 'text-warning' : 'text-text-secondary'}`}>
          {reading.reference}
        </span>
      </div>
      <p className={`text-sm ${isGospel ? 'text-text-primary italic' : 'text-text-secondary'}`}>
        {reading.text.length > 200 ? `${reading.text.substring(0, 200)}...` : reading.text}
      </p>
    </div>
  );
}