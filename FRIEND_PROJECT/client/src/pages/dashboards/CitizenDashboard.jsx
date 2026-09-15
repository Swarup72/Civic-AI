import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { supabase } from '../../lib/supabaseClient'

export function CitizenDashboard() {
  const { user } = useAuth()
  const [complaints, setComplaints] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  async function fetchComplaints() {
    if (!user) return
    setLoading(true)
    const { data, error } = await supabase
      .from('complaints')
      .select('*')
      .eq('citizen_id', user.id)
      .order('created_at', { ascending: false })

    if (!error && data) {
      setComplaints(data)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchComplaints()
  }, [user])

  async function handleCloseComplaint(complaintId, confirmed) {
    setActionLoading(true)
    const nextStatus = confirmed ? 'resolved' : 'escalated'

    const { error } = await supabase
      .from('complaints')
      .update({ status: nextStatus })
      .eq('id', complaintId)

    if (!error) {
      await supabase.from('complaint_updates').insert({
        complaint_id: complaintId,
        author_id: user.id,
        status: nextStatus,
        comment: confirmed
          ? 'Citizen confirmed satisfactory resolution. Case closed.'
          : 'Citizen rejected resolution proof. Case escalated.',
      })
      await fetchComplaints()
    } else {
      alert(error.message)
    }
    setActionLoading(false)
  }

  return (
    <section className="dashboard-page" style={{ textAlign: 'left', padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Citizen Dashboard</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Link
            to="/citizen/community"
            style={{ padding: '8px 16px', border: '1px solid var(--accent)', color: 'inherit', textDecoration: 'none', borderRadius: 4 }}
          >
            Community Feed
          </Link>
          <Link
            to="/citizen/report"
            style={{ padding: '8px 16px', background: 'var(--accent)', color: '#fff', textDecoration: 'none', borderRadius: 4 }}
          >
            + Report New Issue
          </Link>
        </div>
      </div>

      {loading ? (
        <p>Loading complaints...</p>
      ) : complaints.length === 0 ? (
        <p>No complaints reported yet. Click above to report your first issue.</p>
      ) : (
        <div style={{ display: 'grid', gap: '1rem', marginTop: '1.5rem' }}>
          {complaints.map((item) => (
            <div
              key={item.id}
              style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <h3 style={{ margin: 0 }}>{item.title}</h3>
                <span style={{ textTransform: 'uppercase', fontSize: 12, fontWeight: 700 }}>
                  {item.status}
                </span>
              </div>
              <p style={{ marginTop: '0.5rem', color: 'var(--text)' }}>{item.description}</p>
              {item.address && <p style={{ fontSize: 13 }}>📍 {item.address}</p>}
              {item.image_url && (
                <img
                  src={item.image_url}
                  alt="Proof"
                  style={{ width: 140, height: 90, objectFit: 'cover', borderRadius: 4, marginTop: '0.5rem' }}
                />
              )}

              {/* Citizen Confirmation Actions */}
              {item.status === 'proof_submitted' && (
                <div style={{ marginTop: '1rem', padding: '0.8rem', background: 'var(--social-bg)', borderRadius: 6 }}>
                  <p style={{ margin: '0 0 0.5rem 0', fontWeight: 600 }}>
                    Authority uploaded resolution proof. Does this solve your problem?
                  </p>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      disabled={actionLoading}
                      onClick={() => handleCloseComplaint(item.id, true)}
                      style={{ padding: '6px 14px', background: '#10b981', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                    >
                      ✔ Accept & Close Issue
                    </button>
                    <button
                      type="button"
                      disabled={actionLoading}
                      onClick={() => handleCloseComplaint(item.id, false)}
                      style={{ padding: '6px 14px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                    >
                      ✖ Reject & Escalate
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}