"use client"

import { useState, useEffect, useCallback } from "react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { useTranslations, useLocale } from 'next-intl'
import {
  PanelLeftClose,
  PanelLeft,
  Plus,
  Trash2,
  MessageSquare,
} from "lucide-react"
import { ThemeToggle } from "@/components/ThemeToggle"
import { LocaleToggle } from "@/components/LocaleToggle"
import { SignOutButton } from "@/app/chat/SignOutButton"
import { cn } from "@/lib/utils"
import {
  listConversations,
  createConversation,
  deleteConversation,
} from "@/lib/conversations"
import { Conversation } from "@/types"
import { track } from "@/lib/analytics"

interface SidebarProps {
  email: string | null | undefined
  conversationId?: string | null
}

function formatDate(date: string, locale: string): string {
  const d = new Date(date)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) return "Oggi"
  if (diffDays === 1) return "Ieri"
  if (diffDays < 7) return `${diffDays} giorni fa`
  return d.toLocaleDateString(locale === 'it' ? 'it-IT' : 'en-US', { day: "numeric", month: "short" })
}

export function Sidebar({ email, conversationId }: SidebarProps) {
  const router = useRouter()
  const t = useTranslations('sidebar')
  const locale = useLocale()
  const [expanded, setExpanded] = useState(true)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const list = await listConversations()
      setConversations(list)
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false)
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [])

  useEffect(() => {
    const handleCreated = () => load()
    window.addEventListener('conversation-created', handleCreated)
    return () => window.removeEventListener('conversation-created', handleCreated)
  }, [load])

  const handleCreate = async () => {
    try {
      const conv = await createConversation()
      router.push(`/chat?convId=${conv.id}`)
    } catch {
      // silently fail
    }
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    try {
      await deleteConversation(id)
      track('conversation_deleted')
      if (id === conversationId) {
        router.push("/chat")
      } else {
        load()
      }
    } catch {
      // silently fail
    }
  }

  const handleSelect = (id: string) => {
    router.push(`/chat?convId=${id}`)
  }

  const daysAgo = (count: number) => {
    // Simple approach: just return the formatted string with locale-based formatting
    return count === 0 ? t('today') : count === 1 ? t('yesterday') : `${count} ${locale === 'it' ? 'giorni fa' : 'days ago'}`
  }

  return (
    <>
      {/* Backdrop (mobile only) */}
      {expanded && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setExpanded(false)}
        />
      )}

      <aside
        onClick={!expanded ? () => { setExpanded(true); track('sidebar_toggle', { expanded: true }); } : undefined}
        className={cn(
          "flex flex-col h-screen border-r border-border bg-bg-raised/80 backdrop-blur-sm transition-all duration-300 overflow-hidden shrink-0",
          "md:relative",
          "fixed inset-y-0 left-0 z-50",
          expanded ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          expanded ? "w-[280px]" : "md:w-[48px]",
          !expanded && "cursor-pointer group",
        )}
      >
        {/* Top section: logo + toggle */}
        <div
          className={cn(
            "flex items-center h-14 shrink-0",
            expanded ? "justify-between px-3" : "justify-center px-1",
          )}
        >
          <div className="flex items-center gap-3 overflow-hidden">
            {expanded ? (
              <Image
                src="/logo.png"
                alt="Prete-a-porter"
                width={512}
                height={512}
                className="w-10 h-10 logo-glow shrink-0"
              />
            ) : (
              <>
                <Image
                  src="/logo.png"
                  alt="Prete-a-porter"
                  width={512}
                  height={512}
                  className="w-10 h-10 logo-glow shrink-0 group-hover:hidden transition-opacity"
                />
                <PanelLeft
                  size={20}
                  className="hidden group-hover:block text-text-tertiary shrink-0 transition-opacity"
                />
              </>
            )}
            {expanded && (
              <span className="text-lg font-serif font-semibold text-text-primary whitespace-nowrap">
                Prete-a-porter
              </span>
            )}
          </div>
          {expanded && (
            <button
              onClick={() => { setExpanded(false); track('sidebar_toggle', { expanded: false }); }}
              className="shrink-0 p-1.5 rounded-lg hover:bg-bg-overlay transition-colors text-text-tertiary"
              aria-label={t('collapse')}
            >
              <PanelLeftClose size={18} />
            </button>
          )}
        </div>

        {/* Middle section: conversation list */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          {/* New conversation button */}
          {expanded && (
            <div className="px-3 pt-2 pb-1">
              <button
                onClick={handleCreate}
                className="flex items-center gap-2 w-full px-3 py-2 rounded-lg border border-dashed border-border text-sm text-text-secondary hover:text-text-primary hover:border-text-secondary transition-colors"
              >
                <Plus size={16} />
                <span>{t('new_conversation')}</span>
              </button>
            </div>
          )}

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
            {loading &&
              Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 rounded-lg bg-bg-overlay/50 animate-pulse"
                />
              ))}
            {!loading &&
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => handleSelect(conv.id)}
                  className={cn(
                    "group relative flex items-start gap-2 w-full px-2.5 py-2 rounded-lg text-left text-sm transition-colors",
                    conv.id === conversationId
                      ? "bg-bg-overlay text-text-primary"
                      : "text-text-secondary hover:bg-bg-overlay/50 hover:text-text-primary",
                  )}
                >
                  <MessageSquare
                    size={16}
                    className="mt-0.5 shrink-0 text-text-tertiary"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium">
                      {conv.title || t('default_title')}
                    </p>
                    <p className="text-xs text-text-tertiary">
                      {formatDate(conv.updatedAt, locale)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, conv.id)}
                    className="shrink-0 p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-500 transition-all"
                    aria-label={t('delete_conversation')}
                  >
                    <Trash2 size={14} />
                  </button>
                </button>
              ))}
            {!loading && conversations.length === 0 && (
              <p className="px-2.5 py-8 text-center text-sm text-text-tertiary">
                {t('no_conversations')}
              </p>
            )}
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Bottom section: email, theme, logout */}
        <div
          className={cn(
            "flex flex-col gap-1",
            expanded ? "p-3" : "p-1.5 items-center",
          )}
        >
          {expanded && (
            <span className="text-sm text-text-secondary truncate px-2 pb-1">
              {email ?? t('user_fallback')}
            </span>
          )}
          <ThemeToggle showLabel={expanded} />
          <LocaleToggle />
          <SignOutButton showLabel={expanded} />
        </div>
      </aside>
    </>
  )
}
