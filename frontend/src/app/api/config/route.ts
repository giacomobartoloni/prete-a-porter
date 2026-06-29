import { NextResponse } from "next/server"
import pkg from "@/../package.json"

export async function GET() {
  return NextResponse.json({
    wsUrl: process.env.WS_URL || "ws://localhost:8000/ws/chat",
    version: pkg.version,
  })
}
