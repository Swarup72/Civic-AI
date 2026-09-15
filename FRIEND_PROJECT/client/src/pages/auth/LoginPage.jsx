import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { ROLE_HOME_PATH } from '../../lib/roles'
import { supabase } from '../../lib/supabaseClient'

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    const { data, error: signInError } = await signIn(email, password)
    if (signInError) {
      setError(signInError.message)
      setSubmitting(false)
      return
    }

    // Look up the verified role from the profiles table
    let userRole = 'citizen'
    if (data?.user?.id) {
      const { data: profile } = await supabase
        .from('profiles')
        .select('role')
        .eq('id', data.user.id)
        .single()

      if (profile?.role) {
        userRole = profile.role
      }
    }

    setSubmitting(false)

    const target = ROLE_HOME_PATH[userRole] || '/citizen'
    const redirectTo = location.state?.from?.pathname || target
    navigate(redirectTo, { replace: true })
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h1>Log in</h1>

      <label htmlFor="email">Email</label>
      <input
        id="email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />

      <label htmlFor="password">Password</label>
      <input
        id="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />

      {error && <p className="auth-error">{error}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Logging in…' : 'Log in'}
      </button>

      <p className="auth-switch">
        Don't have an account? <Link to="/signup">Sign up</Link>
      </p>
    </form>
  )
}