'use client';

import { UserPreferences } from '@/types';
import { useTranslations } from 'next-intl';
import { Users, MessageCircle, Clock, Heart, Lightbulb, BookOpen } from 'lucide-react';

interface PreferencePickerProps {
  preferences: UserPreferences;
}

export default function PreferencePicker({ preferences }: PreferencePickerProps) {
  const t = useTranslations('homily');
  return (
    <div className="bg-bg-card rounded-lg border border-border p-4 max-w-md">
      <div className="flex items-center gap-2 mb-4">
        <Users className="w-5 h-5 text-text-secondary" />
        <span className="font-semibold text-text-primary">{t('preferences')}</span>
      </div>

      <div className="space-y-3">
        {preferences.target_audience && (
          <PreferenceRow
            icon={<Users className="w-4 h-4" />}
            label={t("target_audience")}
            value={t('audience.' + preferences.target_audience)}
          />
        )}

        {preferences.tone && (
          <PreferenceRow
            icon={<MessageCircle className="w-4 h-4" />}
            label={t("tone")}
            value={t('tone_options.' + preferences.tone)}
          />
        )}

        {preferences.length && (
          <PreferenceRow
            icon={<Clock className="w-4 h-4" />}
            label={t("length")}
            value={t('length_options.' + preferences.length)}
          />
        )}

        {preferences.themes && preferences.themes.length > 0 && (
          <div className="pt-2 border-t border-border">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="w-4 h-4 text-warning" />
              <span className="text-sm font-medium text-text-secondary">{t("themes")}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {preferences.themes.map((theme, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-warning/10 text-warning text-xs rounded-full"
                >
                  {theme}
                </span>
              ))}
            </div>
          </div>
        )}

        {preferences.metaphors && preferences.metaphors.length > 0 && (
          <div className="pt-2 border-t border-border">
            <div className="flex items-center gap-2 mb-2">
              <Heart className="w-4 h-4 text-danger" />
              <span className="text-sm font-medium text-text-secondary">{t("metaphors")}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {preferences.metaphors.map((metaphor, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-danger/10 text-danger text-xs rounded-full"
                >
                  {metaphor}
                </span>
              ))}
            </div>
          </div>
        )}

        {preferences.parables && preferences.parables.length > 0 && (
          <div className="pt-2 border-t border-border">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4 text-accent-blue" />
              <span className="text-sm font-medium text-text-secondary">{t("parables")}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {preferences.parables.map((parable, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-accent-blue/10 text-accent-blue text-xs rounded-full"
                >
                  {parable}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface PreferenceRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
}

function PreferenceRow({ icon, label, value }: PreferenceRowProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-text-secondary">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <span className="text-sm font-medium text-text-primary">{value}</span>
    </div>
  );
}





