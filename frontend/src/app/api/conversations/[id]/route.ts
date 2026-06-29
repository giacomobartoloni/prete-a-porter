import { NextResponse } from "next/server"
import { auth } from "@/lib/auth"
import { prisma } from "@/lib/prisma"

export async function GET(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const conv = await prisma.conversation.findFirst({
    where: { id: params.id, userId: session.user.id },
  })
  if (!conv) {
    return NextResponse.json({ error: "Not found" }, { status: 404 })
  }

  let messages: unknown
  try { messages = JSON.parse(conv.messages) } catch { messages = [] }

  return NextResponse.json({
    ...conv,
    messages,
  })
}

export async function PATCH(
  req: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const body = await req.json()
  const conv = await prisma.conversation.findFirst({
    where: { id: params.id, userId: session.user.id },
  })
  if (!conv) {
    return NextResponse.json({ error: "Not found" }, { status: 404 })
  }

  const updateData: Record<string, string> = {}
  if (body.title !== undefined) {
    updateData.title = body.title
  }
  if (body.messages !== undefined) {
    updateData.messages = JSON.stringify(body.messages)
  }

  if (Object.keys(updateData).length === 0) {
    return NextResponse.json({ error: "No fields to update" }, { status: 400 })
  }

  const updated = await prisma.conversation.update({
    where: { id: params.id },
    data: updateData,
  })

  let messages: unknown
  try { messages = JSON.parse(updated.messages) } catch { messages = [] }

  return NextResponse.json({
    ...updated,
    messages,
  })
}

export async function DELETE(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth()
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const conv = await prisma.conversation.findFirst({
    where: { id: params.id, userId: session.user.id },
  })
  if (!conv) {
    return NextResponse.json({ error: "Not found" }, { status: 404 })
  }

  await prisma.conversation.delete({ where: { id: params.id } })

  // Notify orchestrator to delete checkpoint (fire & forget)
  const orchestratorUrl = process.env.ORCHESTRATOR_URL || "http://localhost:8000"
  fetch(`${orchestratorUrl}/checkpoints/${conv.sessionId}`, { method: "DELETE" }).catch((e) => {
    console.error("Failed to notify orchestrator:", e)
  })

  return NextResponse.json({ success: true })
}
