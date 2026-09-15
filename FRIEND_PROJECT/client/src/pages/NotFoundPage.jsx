import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="not-found-page">
      <h1>Page not found</h1>
      <p>The page you're looking for doesn't exist.</p>
      <Link to="/">Back to home</Link>
    </section>
  )
}
