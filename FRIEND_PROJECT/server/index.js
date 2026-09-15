import 'dotenv/config'
import express from 'express'
import cors from 'cors'
import { createClient } from '@supabase/supabase-js'
import { analyzeComplaint } from './services/aiService.js'
import { checkAndEscalateComplaints } from './services/slaService.js'

const app = express()
app.use(cors())
app.use(express.json())

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

// Endpoint: AI analyzes a newly submitted complaint and assigns triage metadata
app.post('/api/complaints/:id/analyze', async (req, res) => {
  const { id } = req.params

  try {
    const { data: complaint, error: compErr } = await supabase
      .from('complaints')
      .select('*')
      .eq('id', id)
      .single()

    if (compErr || !complaint) {
      return res.status(404).json({ error: 'Complaint not found' })
    }

    const { data: departments } = await supabase
      .from('departments')
      .select('id, name')

    const aiResult = await analyzeComplaint({
      title: complaint.title,
      description: complaint.description,
      address: complaint.address,
      availableDepartments: departments || [],
    })

    const resolutionDeadline = new Date(
      Date.now() + (aiResult.estimated_resolution_days || 5) * 24 * 60 * 60 * 1000
    ).toISOString()

    const ackDeadline = new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString()

    const { data: updated, error: updateErr } = await supabase
      .from('complaints')
      .update({
        category: aiResult.category,
        subcategory: aiResult.subcategory,
        severity_score: Math.min(Math.max(aiResult.severity_score, 0), 100),
        priority: aiResult.priority,
        department_id: aiResult.recommended_department_id || complaint.department_id,
        status: 'ai_analyzed',
        acknowledgment_deadline: ackDeadline,
        resolution_deadline: resolutionDeadline,
      })
      .eq('id', id)
      .select()
      .single()

    if (updateErr) throw updateErr

    await supabase.from('complaint_updates').insert({
      complaint_id: id,
      author_id: complaint.citizen_id,
      status: 'ai_analyzed',
      comment: `AI Triage: ${aiResult.ai_summary} (Priority: ${aiResult.priority.toUpperCase()}, Severity: ${aiResult.severity_score}/100)`,
    })

    console.log(`[AI Analysis Completed] Complaint ${id} triaged:`, aiResult.ai_summary)
    res.json({ success: true, complaint: updated, ai: aiResult })
  } catch (err) {
    console.error('AI Analysis error:', err)
    res.status(500).json({ error: err.message || 'AI Triage processing failed' })
  }
})

// Endpoint: Manual or Webhook trigger to run SLA verification on demand
app.post('/api/sla/check', async (req, res) => {
  try {
    const result = await checkAndEscalateComplaints()
    res.json({ success: true, result })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// Periodic SLA background check (runs every 60 seconds)
setInterval(() => {
  checkAndEscalateComplaints().catch((err) =>
    console.error('[Periodic SLA Check Failed]:', err)
  )
}, 60 * 1000)

const PORT = process.env.PORT || 5000
app.listen(PORT, () => {
  console.log(`CivicAI Server running on port ${PORT}`)
  console.log(`[SLA Watchdog] Background worker running every 60 seconds.`)
})