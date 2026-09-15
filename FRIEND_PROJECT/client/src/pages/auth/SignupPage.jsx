import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { ROLES } from '../../lib/roles'

export function SignupPage() {
  const { signUp } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirmationSent, setConfirmationSent] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    // Pass metadata as an object: { role: ROLES.CITIZEN }
    const { data, error: signUpError } = await signUp(email, password, {
      role: ROLES.CITIZEN,
    })
    setSubmitting(false)

    if (signUpError) {
      setError(signUpError.message)
      return
    }

    if (!data.session) {
      setConfirmationSent(true)
      return
    }

    navigate('/citizen', { replace: true })
  }

  if (confirmationSent) {
    return (
      <div className="auth-form">
        <h1>Check your inbox</h1>
        <p>We sent a confirmation link to {email}. Confirm it, then log in.</p>
        <Link to="/login">Back to login</Link>
      </div>
    )
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h1>Create Citizen Account</h1>

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
        minLength={6}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />

      {error && <p className="auth-error">{error}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Creating account…' : 'Sign up'}
      </button>

      <p className="auth-switch">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </form>
  )
}