import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"
import Chat from "@/components/Chat"
import { Sidebar } from "@/components/Sidebar"

export default async function ChatPage({
  searchParams,
}: {
  searchParams?: { convId?: string }
}) {
  const session = await auth()
  const user = session?.user

  if (!user) {
    redirect("/auth/login")
  }

  return (
    <main className="flex h-screen bg-bg-canvas">
      <Sidebar email={user.email ?? null} conversationId={searchParams?.convId ?? null} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Chat conversationId={searchParams?.convId ?? null} />
      </div>
    </main>
  )
}
