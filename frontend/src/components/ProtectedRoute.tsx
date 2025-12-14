// Auth protection disabled for MVP - re-enable later
interface ProtectedRouteProps {
  children: React.ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  // TODO: Re-enable auth protection after fixing Firebase auth issues
  return <>{children}</>
}
