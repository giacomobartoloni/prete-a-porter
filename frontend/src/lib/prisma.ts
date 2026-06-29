import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

const prismaClient = globalForPrisma.prisma ?? new PrismaClient()

if (!globalForPrisma.prisma) {
  globalForPrisma.prisma = prismaClient
  prismaClient.$executeRawUnsafe('PRAGMA journal_mode = WAL')
  prismaClient.$executeRawUnsafe('PRAGMA synchronous = NORMAL')
  prismaClient.$executeRawUnsafe('PRAGMA busy_timeout = 5000')
  prismaClient.$executeRawUnsafe('PRAGMA cache_size = -20000')
  prismaClient.$executeRawUnsafe('PRAGMA foreign_keys = ON')
}

export const prisma = prismaClient
