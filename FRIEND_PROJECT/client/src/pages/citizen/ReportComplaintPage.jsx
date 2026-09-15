import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { supabase } from '../../lib/supabaseClient'

export function ReportComplaintPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [address, setAddress] = useState('')
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      let imageUrl = null

      // 1. Upload image if selected
      if (file) {
        const fileExt = file.name.split('.').pop()
        const fileName = `${user.id}/${Date.now()}.${fileExt}`
        const { error: uploadError } = await supabase.storage
          .from('complaints')
          .upload(fileName, file)

        if (uploadError) throw uploadError

        const { data: publicUrlData } = supabase.storage
          .from('complaints')
          .getPublicUrl(fileName)

        imageUrl = publicUrlData.publicUrl
      }

      // 2. Insert complaint row
      const { data: newComplaint, error: insertError } = await supabase
        .from('complaints')
        .insert({
          citizen_id: user.id,
          title,
          description,
          address: address || null,
          image_url: imageUrl,
          status: 'submitted',
        })
        .select()
        .single()

      if (insertError) throw insertError

      // 3. Trigger Express AI Analysis in background
      fetch(`http://localhost:5000/api/complaints/${newComplaint.id}/analyze`, {
        method: 'POST',
      }).catch((err) => console.error('Background AI trigger failed:', err))

      navigate('/citizen')

    } catch (err) {
      setError(err.message || 'Failed to submit complaint.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 600, margin: '2rem auto', textAlign: 'left', padding: '0 1rem' }}>
      <h2>Report a Civic Issue</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', fontWeight: 600 }}>Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Dangerous pothole on Main Street"
            required
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontWeight: 600 }}>Location / Address</label>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="e.g. Near City Hospital, Market Road"
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontWeight: 600 }}>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            placeholder="Describe the problem, duration, or hazards..."
            required
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontWeight: 600 }}>Evidence Image</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files[0])}
          />
        </div>

        <button type="submit" disabled={submitting} style={{ padding: '10px 16px', fontWeight: 'bold' }}>
          {submitting ? 'Uploading & Submitting...' : 'Submit Complaint'}
        </button>
      </form>
    </div>
  )
}