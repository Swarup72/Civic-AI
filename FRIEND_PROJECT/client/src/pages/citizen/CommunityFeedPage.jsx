import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { supabase } from '../../lib/supabaseClient'

export function CommunityFeedPage() {
  const { user } = useAuth()
  const [complaints, setComplaints] = useState([])
  const [userSupports, setUserSupports] = useState(new Set())
  const [loading, setLoading] = useState(true)

  async function loadFeed() {
    setLoading(true)

    // Fetch complaints and the user's active supports in parallel
    const [feedRes, supportsRes] = await Promise.all([
      supabase
        .from('complaints')
        .select('*, profiles!citizen_id(username, first_name, last_name)')
        .order('support_count', { ascending: false }),
      supabase
        .from('complaint_supports')
        .select('complaint_id')
        .eq('user_id', user.id),
    ])

    if (!feedRes.error && feedRes.data) {
      setComplaints(feedRes.data)
    }

    if (!supportsRes.error && supportsRes.data) {
      setUserSupports(new Set(supportsRes.data.map((s) => s.complaint_id)))
    }

    setLoading(false)
  }

  useEffect(() => {
    if (user) loadFeed()
  }, [user])

  async function toggleSupport(complaintId) {
    const isSupported = userSupports.has(complaintId)

    if (isSupported) {
      // Remove upvote
      setUserSupports((prev) => {
        const next = new Set(prev)
        next.delete(complaintId)
        return next
      })
      setComplaints((prev) =>
        prev.map((c) =>
          c.id === complaintId ? { ...c, support_count: Math.max(c.support_count - 1, 0) } : c
        )
      )

      await supabase
        .from('complaint_supports')
        .delete()
        .match({ complaint_id: complaintId, user_id: user.id })
    } else {
      // Add upvote
      setUserSupports((prev) => new Set(prev).add(complaintId))
      setComplaints((prev) =>
        prev.map((c) =>
          c.id === complaintId ? { ...c, support_count: c.support_count + 1 } : c
        )
      )

      await supabase
        .from('complaint_supports')
        .insert({ complaint_id: complaintId, user_id: user.id })
    }
  }

  return (
    <section className="dashboard-page" style={{ textAlign: 'left', padding: '1.5rem' }}>
      <h1>Community Issues Feed</h1>
      <p style={{ color: 'var(--text)', marginBottom: '1.5rem' }}>
        Support local civic complaints to increase their urgency and notify municipal authorities.
      </p>

      {loading ? (
        <p>Loading community issues...</p>
      ) : complaints.length === 0 ? (
        <p>No civic issues reported yet.</p>
      ) : (
        <div style={{ display: 'grid', gap: '1.2rem', maxWidth: 800 }}>
          {complaints.map((item) => {
            const hasSupported = userSupports.has(item.id)
            return (
              <div
                key={item.id}
                style={{
                  border: '1px solid var(--border)',
                  padding: '1.2rem',
                  borderRadius: 8,
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: '1rem',
                  background: 'var(--social-bg)',
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--accent)' }}>
                      {item.category || 'General'}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text)' }}>•</span>
                    <span style={{ fontSize: 12, textTransform: 'uppercase', fontWeight: 600 }}>
                      {item.status}
                    </span>
                  </div>

                  <h3 style={{ margin: '0.4rem 0' }}>{item.title}</h3>
                  <p style={{ color: 'var(--text)', fontSize: 14 }}>{item.description}</p>
                  {item.address && <p style={{ fontSize: 13, marginTop: '0.4rem' }}>📍 {item.address}</p>}

                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt="Complaint proof"
                      style={{ width: 140, height: 90, objectFit: 'cover', borderRadius: 4, marginTop: '0.5rem' }}
                    />
                  )}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <button
                    type="button"
                    onClick={() => toggleSupport(item.id)}
                    style={{
                      padding: '8px 14px',
                      background: hasSupported ? 'var(--accent)' : 'transparent',
                      color: hasSupported ? '#fff' : 'inherit',
                      border: '1px solid var(--accent)',
                      borderRadius: 6,
                      cursor: 'pointer',
                      fontWeight: 'bold',
                    }}
                  >
                    ▲ Support ({item.support_count})
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}