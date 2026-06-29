import { SignJWT } from 'jose'

export async function createWsToken(userId: string): Promise<string> {
  const raw = process.env.WS_JWT_SECRET
  if (!raw) {
    throw new Error('WS_JWT_SECRET environment variable is required')
  }
  const secret = new TextEncoder().encode(raw)
  return new SignJWT({ sub: userId, type: 'ws_ticket' })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('30s')
    .sign(secret)
}
