import { auth } from "@/lib/auth"
import type { NextAuthRequest } from "next-auth"
import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'
import { NextResponse } from 'next/server'
import type { NextFetchEvent, NextMiddleware } from 'next/server'

const handleI18n = createMiddleware(routing)

/**
 * Set by the auth gate when the session is valid. The i18n rewrite is deliberately issued
 * *outside* the next-auth wrapper: the wrapper rewraps the response in a plain Response,
 * which turns next-intl's internal rewrite into an absolute URL that Next.js proxies as an
 * external request — the router then bounces between /chat and itself (ERR_TOO_MANY_REDIRECTS).
 */
const AUTHENTICATED_HEADER = 'x-mw-authenticated'

function handlePublicPaths(req: NextAuthRequest) {
  const { pathname } = req.nextUrl

  if (pathname.startsWith('/api/')) {
    return NextResponse.next()
  }

  if (pathname === '/') {
    return NextResponse.redirect(new URL('/auth/login', req.url))
  }

  if (pathname.startsWith('/auth/')) {
    return handleI18n(req)
  }

  return null
}

const requireAuth: NextMiddleware = auth((req: NextAuthRequest, _event: NextFetchEvent) => {
  if (!req.auth) {
    const loginUrl = new URL('/auth/login', req.url)
    loginUrl.searchParams.set('callbackUrl', req.nextUrl.pathname)
    return NextResponse.redirect(loginUrl)
  }
  const response = NextResponse.next()
  response.headers.set(AUTHENTICATED_HEADER, '1')
  return response
})

export default async function middleware(req: NextAuthRequest, event: NextFetchEvent) {
  const publicResponse = handlePublicPaths(req)
  if (publicResponse) return publicResponse

  const gateResponse = await requireAuth(req, event)

  if (!(gateResponse instanceof Response) || gateResponse.headers.get(AUTHENTICATED_HEADER) !== '1') {
    // Unauthenticated: carry the redirect (and any refreshed session cookie) through as-is.
    return gateResponse
  }

  const response = handleI18n(req)
  for (const cookie of gateResponse.headers.getSetCookie()) {
    response.headers.append('set-cookie', cookie)
  }
  return response
}

export const config = {
  matcher: '/((?!api|trpc|_next|_vercel|.*\\..*).*)',
}
