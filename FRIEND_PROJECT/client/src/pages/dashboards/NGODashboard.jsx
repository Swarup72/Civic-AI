import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { supabase } from '../../lib/supabaseClient'

export function NGODashboard() {
  const { user, profile } = useAuth()
  const [cases, setCases] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)
  const [proofFile, setProofFile] = useState(null)
  const [updateNote, setUpdateNote] = useState('')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  async function fetchCases() {
    setLoading(true)
    
    // Fetch escalated complaints or complaints under progress
    const { data, error } = await supabase
      .from('complaints')
      .select('*')
      .in('status', ['escalated', 'in_progress', 'proof_submitted'])
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error loading NGO cases:', error)
    } else if (data) {
      setCases(data)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchCases()
  }, [profile])

  async function handleAcceptCase(complaintId) {
    setActionLoading(true)

    const { data, error } = await supabase.rpc('claim_complaint', {
      p_complaint_id: complaintId,
      p_user_id: user.id,
      p_role: 'ngo',
      p_org_or_dept_id: profile?.organization_id || null,
    })

    if (error || !data?.success) {
      alert(data?.message || error?.message || 'Failed to claim case.')
    } else {
      await fetchCases()
      setSelectedCase((prev) => (prev ? { ...prev, status: 'in_progress', assigned_ngo_id: profile?.organization_id } : null))
    }
    setActionLoading(false)
  }

  async function handleResolveCase(e) {
    e.preventDefault()
    if (!selectedCase) return
    setActionLoading(true)

    try {
      let proofUrl = null

      if (proofFile) {
        const fileExt = proofFile.name.split('.').pop()
        const fileName = `proofs/${selectedCase.id}/${Date.now()}.${fileExt}`
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
        .eq('id', selectedCase.id)

      if (complaintError) throw complaintError

      await supabase.from('complaint_updates').insert({
        complaint_id: selectedCase.id,
        author_id: user.id,
        status: nextStatus,
        comment: updateNote || 'Resolution completed by NGO.',
        proof_url: proofUrl,
      })

      setProofFile(null)
      setUpdateNote('')
      setSelectedCase(null)
      await fetchCases()
    } catch (err) {
      alert(err.message || 'Failed to submit NGO resolution.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <section className="dashboard-page" style={{ textAlign: 'left', padding: '1.5rem' }}>
      <h1>NGO Dashboard</h1>
      <p style={{ color: 'var(--text)', marginBottom: '1.5rem' }}>
        Organization Portal: Intervene on escalated issues and deliver community resolutions.
      </p>

      {loading ? (
        <p>Loading escalated cases...</p>
      ) : cases.length === 0 ? (
        <p>No escalated or active cases available right now.</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem' }}>
          {/* Case List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {cases.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelectedCase(item)}
                style={{
                  border: selectedCase?.id === item.id ? '2px solid var(--accent)' : '1px solid var(--border)',
                  padding: '1rem',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: 'var(--social-bg)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <h3 style={{ margin: 0 }}>{item.title}</h3>
                  <span style={{ fontSize: 12, fontWeight: 'bold', textTransform: 'uppercase', color: item.status === 'escalated' ? 'red' : 'inherit' }}>
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
            {selectedCase ? (
              <div>
                <h2>{selectedCase.title}</h2>
                <p><strong>Status:</strong> {selectedCase.status.toUpperCase()}</p>
                <p><strong>Description:</strong> {selectedCase.description}</p>
                {selectedCase.image_url && (
                  <div style={{ margin: '1rem 0' }}>
                    <p><strong>Citizen Evidence:</strong></p>
                    <img
                      src={selectedCase.image_url}
                      alt="Citizen evidence"
                      style={{ maxWidth: '100%', maxHeight: 200, objectFit: 'cover', borderRadius: 6 }}
                    />
                  </div>
                )}

                <hr style={{ margin: '1.5rem 0', borderColor: 'var(--border)' }} />

                {/* Actions */}
                {selectedCase.status === 'escalated' && (
                  <button
                    type="button"
                    onClick={() => handleAcceptCase(selectedCase.id)}
                    disabled={actionLoading}
                    style={{ padding: '8px 16px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 4, fontWeight: 'bold' }}
                  >
                    {actionLoading ? 'Accepting...' : 'Accept Case'}
                  </button>
                )}

                {selectedCase.status === 'in_progress' && (
                  <form onSubmit={handleResolveCase} style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                    <h4>Submit NGO Resolution Proof</h4>
                    <textarea
                      placeholder="Describe the action taken by your NGO..."
                      value={updateNote}
                      onChange={(e) => setUpdateNote(e.target.value)}
                      rows={3}
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
                      style={{ padding: '8px 16px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 4, fontWeight: 'bold' }}
                    >
                      {actionLoading ? 'Submitting...' : 'Submit Proof & Complete'}
                    </button>
                  </form>
                )}

                {selectedCase.status === 'proof_submitted' && (
                  <p style={{ color: 'green', fontWeight: 600 }}>
                    Resolution proof submitted. Awaiting AI/Citizen verification.
                  </p>
                )}
              </div>
            ) : (
              <p style={{ color: 'var(--text)' }}>Select an escalated case from the left to view details and take action.</p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}