import { auth } from "@/lib/auth"
import type { NextAuthRequest } from "next-auth"
import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'
import { NextResponse } from 'next/server'
import type { NextFetchEvent } from 'next/server'

const handleI18n = createMiddleware(routing)

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

const protectedHandler = auth((req: NextAuthRequest) => {
  if (!req.auth) {
    const loginUrl = new URL('/auth/login', req.url)
    loginUrl.searchParams.set('callbackUrl', req.nextUrl.pathname)
    return NextResponse.redirect(loginUrl)
  }
  return handleI18n(req)
})

export default function middleware(req: NextAuthRequest, event: NextFetchEvent) {
  const result = handlePublicPaths(req)
  if (result) return result
  return protectedHandler(req, event)
}

export const config = {
  matcher: '/((?!api|trpc|_next|_vercel|.*\\..*).*)',
}