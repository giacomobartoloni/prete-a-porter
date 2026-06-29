import Image from "next/image"
import Link from "next/link"

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-canvas py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <Image src="/logo.png" alt="Prete-a-porter" width={512} height={512} className="w-28 h-28 mx-auto mb-4 logo-glow" />
          <Link href="/" className="text-3xl font-bold text-text-primary">
            Prete-a-porter
          </Link>
          <p className="mt-2 text-sm text-text-secondary font-medium">
            Il ghostwriter per un&apos;omelia perfetta
          </p>
        </div>
        {children}
      </div>
    </div>
  )
}
