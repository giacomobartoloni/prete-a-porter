'use client';

import { GeneratedHomily } from '@/types';
import { useTranslations } from 'next-intl';
import { FileText, BookOpen, Heart, Lightbulb, ArrowRight, ExternalLink } from 'lucide-react';

interface HomilyDisplayProps {
  homily: GeneratedHomily;
  sources?: string[];
}

const occasionLabels: Record<string, string> = {
  mass: 'Santa Messa',
  marriage: 'Matrimonio',
  baptism: 'Battesimo',
  funeral: 'Funerale',
};

export default function HomilyDisplay({ homily, sources }: HomilyDisplayProps) {
  const t = useTranslations('homily');
  return (
    <div className="bg-bg-card rounded-lg border border-border p-4 max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-text-secondary" />
          <span className="font-semibold text-text-primary">{t('title')}</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span>{occasionLabels[homily.occasion] || homily.occasion}</span>
          <span className="text-text-tertiary">|</span>
          <span>{homily.liturgical_date}</span>
        </div>
      </div>

      {/* Sections */}
      <div className="space-y-4">
        <Section
          icon={<FileText className="w-4 h-4" />}
          title={homily.introduction.title}
          content={homily.introduction.content}
          variant="intro"
        />

        <Section
          icon={<BookOpen className="w-4 h-4" />}
          title={homily.reading_reflection.title}
          content={homily.reading_reflection.content}
          variant="reflection"
        />

        <Section
          icon={<Lightbulb className="w-4 h-4" />}
          title={homily.practical_application.title}
          content={homily.practical_application.content}
          variant="application"
        />

        <Section
          icon={<Heart className="w-4 h-4" />}
          title={homily.conclusion.title}
          content={homily.conclusion.content}
          variant="conclusion"
        />
      </div>

      {/* Sources */}
      {sources && sources.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-text-tertiary mb-2">
            <ExternalLink className="w-3 h-3" />
            <span>{t('sources')}</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {sources.map((source, index) => (
              <span
                key={index}
                className="px-2 py-0.5 bg-bg-overlay text-text-secondary text-xs rounded"
              >
                {source}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface SectionProps {
  icon: React.ReactNode;
  title: string;
  content: string;
  variant: 'intro' | 'reflection' | 'application' | 'conclusion';
}

const variantStyles = {
  intro: {
    bg: 'bg-accent-blue/10',
    border: 'border-l-accent-blue',
    icon: 'text-accent-blue',
  },
  reflection: {
    bg: 'bg-warning/10',
    border: 'border-l-warning',
    icon: 'text-warning',
  },
  application: {
    bg: 'bg-success/10',
    border: 'border-l-success',
    icon: 'text-success',
  },
  conclusion: {
    bg: 'bg-danger/10',
    border: 'border-l-danger',
    icon: 'text-danger',
  },
};

function Section({ icon, title, content, variant }: SectionProps) {
  const style = variantStyles[variant];

  return (
    <div className={`${style.bg} border-l-4 ${style.border} p-3 rounded-r-lg`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={style.icon}>{icon}</span>
        <span className="font-medium text-text-primary text-sm">{title}</span>
      </div>
      <p className="text-sm text-text-secondary leading-relaxed">{content}</p>
      {variant !== 'conclusion' && (
        <div className="flex items-center mt-2 text-text-tertiary">
          <ArrowRight className="w-3 h-3" />
        </div>
      )}
    </div>
  );
}