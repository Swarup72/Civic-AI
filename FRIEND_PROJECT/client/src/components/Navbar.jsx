import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ROLE_LABELS } from '../lib/roles'

export function Navbar() {
  const { isAuthenticated, role, signOut } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await signOut()
    navigate('/')
  }

  return (
    <header className="navbar">
      <Link to="/" className="navbar-brand">
        CivicAI
      </Link>

      <nav className="navbar-links">
        {isAuthenticated ? (
          <>
            <span className="navbar-role">{ROLE_LABELS[role] ?? role}</span>
            <button type="button" onClick={handleSignOut}>
              Sign out
            </button>
          </>
        ) : (
          <>
            <Link to="/login">Log in</Link>
            <Link to="/signup">Sign up</Link>
          </>
        )}
      </nav>
    </header>
  )
}
