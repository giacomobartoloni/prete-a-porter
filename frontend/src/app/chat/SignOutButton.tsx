"use client"

import { useTranslations } from "next-intl"
import { signOut } from "next-auth/react"
import { LogOut } from "lucide-react"

interface SignOutButtonProps {
  showLabel?: boolean
}

export function SignOutButton({ showLabel = false }: SignOutButtonProps) {
  const t = useTranslations("auth.logout")
  return (
    <button
      onClick={async () => {
        await signOut({ redirect: false })
        window.location.href = "/auth/login"
      }}
      aria-label={t("button")}
      className="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-text-tertiary hover:text-danger bg-transparent rounded-lg hover:bg-danger/10 transition-all w-full"
    >
      <LogOut size={20} className="shrink-0" />
      {showLabel && (
        <span className="whitespace-nowrap">{t("button")}</span>
      )}
    </button>
  )
}