import { NextResponse } from "next/server"
import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import crypto from "crypto"

export async function GET() {
  const session = await auth()
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const conversations = await prisma.conversation.findMany({
    where: { userId: session.user.id },
    orderBy: { updatedAt: "desc" },
    select: { id: true, title: true, updatedAt: true, createdAt: true, sessionId: true },
  })

  return NextResponse.json(conversations)
}

export async function POST() {
  const session = await auth()
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const userExists = await prisma.user.findUnique({ where: { id: session.user.id } })
  if (!userExists) {
    console.error("User not found in database", {
      userId: session.user.id,
      email: session.user.email,
      dbPath: process.env.DATABASE_URL,
    })
    return NextResponse.json({ error: "User not found in database" }, { status: 500 })
  }

  const conversation = await prisma.conversation.create({
    data: {
      userId: session.user.id,
      sessionId: crypto.randomUUID(),
    },
  })

  let messages: unknown
  try { messages = JSON.parse(conversation.messages) } catch { messages = [] }

  return NextResponse.json({
    ...conversation,
    messages,
  })
}
