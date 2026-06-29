import { NextResponse } from "next/server"
import { auth } from "@/lib/auth"
import { createWsToken } from "@/lib/session"

export async function POST() {
  const session = await auth()

  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const token = await createWsToken(session.user.id)

  return NextResponse.json({ token })
}
