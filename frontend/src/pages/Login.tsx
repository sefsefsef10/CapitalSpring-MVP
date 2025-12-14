// Auth disabled for MVP - this page just redirects to dashboard
export default function Login() {
  // Skip login for MVP - go straight to dashboard
  window.location.href = '/dashboard'
  return null
}
