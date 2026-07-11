import { auth } from "@/lib/auth"
import type { NextAuthRequest } from "next-auth"
import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'
import { NextResponse } from 'next/server'

const handleI18n = createMiddleware(routing)

export default auth((req: NextAuthRequest) => {
  const { pathname } = req.nextUrl
  const isLoggedIn = !!req.auth

  if (pathname.startsWith('/api/')) {
    return NextResponse.next()
  }

  if (pathname === '/') {
    if (isLoggedIn) {
      return NextResponse.redirect(new URL('/chat', req.url))
    }
    return NextResponse.redirect(new URL('/auth/login', req.url))
  }

  if (pathname.startsWith('/auth/')) {
    return handleI18n(req)
  }

  if (!isLoggedIn) {
    const loginUrl = new URL('/auth/login', req.url)
    loginUrl.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return handleI18n(req)
})

export const config = {
  matcher: '/((?!api|trpc|_next|_vercel|.*\\..*).*)',
}