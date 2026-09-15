import { Link, Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <div className="auth-layout">
      <Link to="/" className="auth-brand">
        CivicAI
      </Link>
      <div className="auth-card">
        <Outlet />
      </div>
    </div>
  )
}
