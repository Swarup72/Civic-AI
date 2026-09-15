import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabaseClient'
import { ROLE_LABELS, ROLE_LIST } from '../../lib/roles'

export function AdminDashboard() {
  const [stats, setStats] = useState({
    total: 0,
    resolved: 0,
    pending: 0,
    escalated: 0,
    govResolved: 0,
    ngoResolved: 0,
  })
  const [deptPerformance, setDeptPerformance] = useState([])
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [organizations, setOrganizations] = useState([])
  const [newDept, setNewDept] = useState('')
  const [newOrg, setNewOrg] = useState({ name: '', email: '' })
  const [loading, setLoading] = useState(true)

  async function loadAdminData() {
    setLoading(true)

    const [compRes, profRes, deptRes, orgRes, updatesRes] = await Promise.all([
      supabase.from('complaints').select('*'),
      supabase.from('profiles').select('id, first_name, last_name, username, role, department_id, organization_id'),
      supabase.from('departments').select('*').order('name'),
      supabase.from('organizations').select('*').order('name'),
      supabase.from('complaint_updates').select('complaint_id, status, author_id, profiles:author_id(role)'),
    ])

    const allComplaints = compRes.data || []
    const allProfiles = profRes.data || []
    const allDepts = deptRes.data || []
    const allOrgs = orgRes.data || []
    const allUpdates = updatesRes.data || []

    setUsers(allProfiles)
    setDepartments(allDepts)
    setOrganizations(allOrgs)

    // Calculate Gov vs NGO resolution metrics
    const resolvedIds = new Set(allComplaints.filter((c) => c.status === 'resolved').map((c) => c.id))
    let govCount = 0
    let ngoCount = 0

    allUpdates.forEach((up) => {
      if (resolvedIds.has(up.complaint_id) && up.status === 'proof_submitted') {
        if (up.profiles?.role === 'government') govCount++
        if (up.profiles?.role === 'ngo') ngoCount++
      }
    })

    setStats({
      total: allComplaints.length,
      resolved: allComplaints.filter((c) => c.status === 'resolved').length,
      pending: allComplaints.filter((c) => ['submitted', 'ai_analyzed', 'acknowledged', 'in_progress'].includes(c.status)).length,
      escalated: allComplaints.filter((c) => c.status === 'escalated').length,
      govResolved: govCount,
      ngoResolved: ngoCount,
    })

    // Department Resolution Performance Breakdown
    const perf = allDepts.map((d) => {
      const deptComplaints = allComplaints.filter((c) => c.department_id === d.id)
      const solved = deptComplaints.filter((c) => c.status === 'resolved').length
      return {
        id: d.id,
        name: d.name,
        assigned: deptComplaints.length,
        solved,
        resolutionRate: deptComplaints.length > 0 ? Math.round((solved / deptComplaints.length) * 100) : 0,
      }
    })
    setDeptPerformance(perf)

    setLoading(false)
  }

  useEffect(() => {
    loadAdminData()
  }, [])

  async function handleRoleChange(userId, newRole) {
    const { error } = await supabase.from('profiles').update({ role: newRole }).eq('id', userId)
    if (!error) loadAdminData()
    else alert(error.message)
  }

  async function handleAddDepartment(e) {
    e.preventDefault()
    if (!newDept.trim()) return
    const { error } = await supabase.from('departments').insert({ name: newDept.trim() })
    if (!error) {
      setNewDept('')
      loadAdminData()
    } else alert(error.message)
  }

  async function handleAddOrganization(e) {
    e.preventDefault()
    if (!newOrg.name.trim()) return
    const { error } = await supabase.from('organizations').insert({
      name: newOrg.name.trim(),
      contact_email: newOrg.email.trim() || null,
    })
    if (!error) {
      setNewOrg({ name: '', email: '' })
      loadAdminData()
    } else alert(error.message)
  }

  return (
    <section className="dashboard-page" style={{ textAlign: 'left', padding: '1.5rem' }}>
      <h1>Analytics & Control Center</h1>

      {/* KPI Overview */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>Total Complaints</span>
          <h2 style={{ margin: '0.5rem 0 0' }}>{stats.total}</h2>
        </div>
        <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>Pending</span>
          <h2 style={{ margin: '0.5rem 0 0', color: '#f59e0b' }}>{stats.pending}</h2>
        </div>
        <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>Escalated</span>
          <h2 style={{ margin: '0.5rem 0 0', color: '#ef4444' }}>{stats.escalated}</h2>
        </div>
        <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>Resolved</span>
          <h2 style={{ margin: '0.5rem 0 0', color: '#10b981' }}>{stats.resolved}</h2>
        </div>
        <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>Gov Solved</span>
          <h2 style={{ margin: '0.5rem 0 0' }}>{stats.govResolved}</h2>
        </div>
        <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>NGO Solved</span>
          <h2 style={{ margin: '0.5rem 0 0' }}>{stats.ngoResolved}</h2>
        </div>
      </div>

      {loading ? (
        <p>Calculating platform metrics...</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '2rem' }}>
          {/* Department Performance Table */}
          <div>
            <h3>Department Performance & SLAs</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={{ padding: '8px' }}>Department</th>
                  <th style={{ padding: '8px' }}>Total Issues</th>
                  <th style={{ padding: '8px' }}>Resolved</th>
                  <th style={{ padding: '8px' }}>Efficiency</th>
                </tr>
              </thead>
              <tbody>
                {deptPerformance.map((d) => (
                  <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px', fontWeight: 600 }}>{d.name}</td>
                    <td style={{ padding: '8px' }}>{d.assigned}</td>
                    <td style={{ padding: '8px' }}>{d.solved}</td>
                    <td style={{ padding: '8px', fontWeight: 700, color: d.resolutionRate >= 70 ? '#10b981' : '#f59e0b' }}>
                      {d.resolutionRate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ marginTop: '2.5rem' }}>
              <h3>User Role Permissions</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                {users.map((u) => (
                  <div
                    key={u.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      border: '1px solid var(--border)',
                      padding: '0.6rem 1rem',
                      borderRadius: 6,
                    }}
                  >
                    <div>
                      <strong>{u.username || 'User'}</strong>
                      <span style={{ fontSize: 12, color: 'var(--text)', marginLeft: 8 }}>({u.id.slice(0, 8)})</span>
                    </div>
                    <select value={u.role} onChange={(e) => handleRoleChange(u.id, e.target.value)} style={{ padding: '4px 8px' }}>
                      {ROLE_LIST.map((r) => (
                        <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Management Tools */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
              <h3>Add Department</h3>
              <form onSubmit={handleAddDepartment} style={{ display: 'flex', gap: '8px', marginTop: '0.5rem' }}>
                <input
                  type="text"
                  placeholder="e.g. Traffic Management"
                  value={newDept}
                  onChange={(e) => setNewDept(e.target.value)}
                  style={{ flex: 1, padding: '6px' }}
                  required
                />
                <button type="submit" style={{ padding: '6px 12px' }}>Add</button>
              </form>
              <ul style={{ paddingLeft: '1.2rem', marginTop: '0.8rem', fontSize: 14 }}>
                {departments.map((d) => (
                  <li key={d.id}>{d.name}</li>
                ))}
              </ul>
            </div>

            <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 8 }}>
              <h3>Add NGO Organization</h3>
              <form onSubmit={handleAddOrganization} style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '0.5rem' }}>
                <input
                  type="text"
                  placeholder="NGO Name"
                  value={newOrg.name}
                  onChange={(e) => setNewOrg((prev) => ({ ...prev, name: e.target.value }))}
                  style={{ padding: '6px' }}
                  required
                />
                <input
                  type="email"
                  placeholder="Contact Email"
                  value={newOrg.email}
                  onChange={(e) => setNewOrg((prev) => ({ ...prev, email: e.target.value }))}
                  style={{ padding: '6px' }}
                />
                <button type="submit" style={{ padding: '6px 12px' }}>Register NGO</button>
              </form>
              <ul style={{ paddingLeft: '1.2rem', marginTop: '0.8rem', fontSize: 14 }}>
                {organizations.map((o) => (
                  <li key={o.id}>{o.name} {o.contact_email ? `(${o.contact_email})` : ''}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}