import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { supabase } from '../../lib/supabaseClient'

export function GovernmentDashboard() {
  const { user, profile } = useAuth()
  const [complaints, setComplaints] = useState([])
  const [selectedComplaint, setSelectedComplaint] = useState(null)
  const [proofFile, setProofFile] = useState(null)
  const [updateNote, setUpdateNote] = useState('')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  async function fetchComplaints() {
    setLoading(true)

    // Fetch all complaints so officials can see incoming civic issues
    const { data, error } = await supabase
      .from('complaints')
      .select('*')
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error loading government complaints:', error)
    } else if (data) {
      setComplaints(data)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchComplaints()
  }, [profile])

  async function handleAcknowledge(complaintId) {
    setActionLoading(true)

    const { data, error } = await supabase.rpc('claim_complaint', {
      p_complaint_id: complaintId,
      p_user_id: user.id,
      p_role: 'government',
      p_org_or_dept_id: profile?.department_id || null,
    })

    if (error || !data?.success) {
      alert(data?.message || error?.message || 'Failed to claim complaint.')
    } else {
      await fetchComplaints()
      setSelectedComplaint((prev) => (prev ? { ...prev, status: 'acknowledged' } : null))
    }
    setActionLoading(false)
  }

  async function handleResolveWithProof(e) {
    e.preventDefault()
    if (!selectedComplaint) return
    setActionLoading(true)

    try {
      let proofUrl = null

      if (proofFile) {
        const fileExt = proofFile.name.split('.').pop()
        const fileName = `proofs/${selectedComplaint.id}/${Date.now()}.${fileExt}`
        const { error: uploadError } = await supabase.storage
          .from('complaints')
          .upload(fileName, proofFile)

        if (uploadError) throw uploadError

        const { data: publicUrlData } = supabase.storage
          .from('complaints')
          .getPublicUrl(fileName)

        proofUrl = publicUrlData.publicUrl
      }

      const nextStatus = 'proof_submitted'

      const { error: complaintError } = await supabase
        .from('complaints')
        .update({ status: nextStatus })
        .eq('id', selectedComplaint.id)

      if (complaintError) throw complaintError

      await supabase.from('complaint_updates').insert({
        complaint_id: selectedComplaint.id,
        author_id: user.id,
        status: nextStatus,
        comment: updateNote || 'Resolution proof submitted.',
        proof_url: proofUrl,
      })

      setProofFile(null)
      setUpdateNote('')
      setSelectedComplaint(null)
      await fetchComplaints()
    } catch (err) {
      alert(err.message || 'Failed to submit resolution proof.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <section className="dashboard-page" style={{ textAlign: 'left', padding: '1.5rem' }}>
      <h1>Government Dashboard</h1>
      <p style={{ color: 'var(--text)', marginBottom: '1.5rem' }}>
        Department Officer Portal: Review incoming civic issues and post resolution proofs.
      </p>

      {loading ? (
        <p>Loading assigned complaints...</p>
      ) : complaints.length === 0 ? (
        <p>No complaints assigned to your department right now.</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem' }}>
          {/* Complaints Table/List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {complaints.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelectedComplaint(item)}
                style={{
                  border: selectedComplaint?.id === item.id ? '2px solid var(--accent)' : '1px solid var(--border)',
                  padding: '1rem',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: 'var(--social-bg)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <h3 style={{ margin: 0 }}>{item.title}</h3>
                  <span style={{ fontSize: 12, fontWeight: 'bold', textTransform: 'uppercase' }}>
                    {item.status}
                  </span>
                </div>
                <p style={{ margin: '0.4rem 0', color: 'var(--text)' }}>{item.description}</p>
                {item.address && <p style={{ fontSize: 13, margin: 0 }}>📍 {item.address}</p>}
              </div>
            ))}
          </div>

          {/* Action & Detail Panel */}
          <div style={{ border: '1px solid var(--border)', padding: '1.5rem', borderRadius: 8, height: 'fit-content' }}>
            {selectedComplaint ? (
              <div>
                <h2>{selectedComplaint.title}</h2>
                <p><strong>Status:</strong> {selectedComplaint.status.toUpperCase()}</p>
                <p><strong>Description:</strong> {selectedComplaint.description}</p>
                {selectedComplaint.image_url && (
                  <div style={{ margin: '1rem 0' }}>
                    <p><strong>Citizen Evidence:</strong></p>
                    <img
                      src={selectedComplaint.image_url}
                      alt="Citizen evidence"
                      style={{ maxWidth: '100%', maxHeight: 200, objectFit: 'cover', borderRadius: 6 }}
                    />
                  </div>
                )}

                <hr style={{ margin: '1.5rem 0', borderColor: 'var(--border)' }} />

                {/* State Actions: Can claim if submitted, ai_analyzed, or escalated (as long as NGO hasn't claimed it) */}
                {['submitted', 'ai_analyzed', 'escalated'].includes(selectedComplaint.status) && !selectedComplaint.assigned_ngo_id && (
                  <div style={{ marginTop: '1rem' }}>
                    <button
                      type="button"
                      onClick={() => handleAcknowledge(selectedComplaint.id)}
                      disabled={actionLoading}
                      style={{
                        padding: '10px 20px',
                        background: 'var(--accent)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        fontWeight: 'bold',
                        cursor: 'pointer',
                      }}
                    >
                      {actionLoading ? 'Claiming...' : '✔ Acknowledge & Claim Issue'}
                    </button>
                  </div>
                )}

                {/* Locked indicator if NGO already took the escalated case */}
                {selectedComplaint.assigned_ngo_id && selectedComplaint.status !== 'resolved' && (
                  <p style={{ color: '#f59e0b', fontWeight: 600 }}>
                    Case claimed and being handled by partner NGO.
                  </p>
                )}

                {/* Resolution Form: available once acknowledged/in_progress */}
                {['acknowledged', 'in_progress'].includes(selectedComplaint.status) && (
                  <form onSubmit={handleResolveWithProof} style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                    <h4>Submit Resolution Proof</h4>
                    <textarea
                      placeholder="Enter work details or resolution notes..."
                      value={updateNote}
                      onChange={(e) => setUpdateNote(e.target.value)}
                      rows={3}
                      required
                      style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
                    />
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setProofFile(e.target.files[0])}
                    />
                    <button
                      type="submit"
                      disabled={actionLoading}
                      style={{
                        padding: '10px 16px',
                        background: '#10b981',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        fontWeight: 'bold',
                        cursor: 'pointer',
                      }}
                    >
                      {actionLoading ? 'Uploading...' : 'Submit Proof & Resolve'}
                    </button>
                  </form>
                )}

                {['proof_submitted', 'ai_verified', 'resolved'].includes(selectedComplaint.status) && (
                  <p style={{ color: '#10b981', fontWeight: 600, marginTop: '1rem' }}>
                    Resolution proof submitted. Awaiting verification or citizen closure.
                  </p>
                )}
              </div>
            ) : (
              <p style={{ color: 'var(--text)' }}>Select a complaint from the left to view details and take action.</p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}