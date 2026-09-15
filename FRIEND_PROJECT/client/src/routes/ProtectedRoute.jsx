import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ROLE_HOME_PATH } from '../lib/roles'

/**
 * Wrap any route element that requires auth (and optionally a specific role).
 *
 * Usage:
 *   <Route path="/citizen" element={
 *     <ProtectedRoute allowedRoles={[ROLES.CITIZEN]}>
 *       <CitizenDashboard />
 *     </ProtectedRoute>
 *   } />
 */
export function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, role, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="route-loading">Loading…</div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  const roleIsAllowed =
    !allowedRoles || allowedRoles.length === 0 || allowedRoles.includes(role)

  if (!roleIsAllowed) {
    // Logged in, but visiting a dashboard that isn't theirs — send them home.
    const fallback = ROLE_HOME_PATH[role] ?? '/'
    return <Navigate to={fallback} replace />
  }

  return children
}
