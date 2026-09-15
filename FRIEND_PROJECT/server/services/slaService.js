import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
)

export async function checkAndEscalateComplaints() {
  const now = new Date().toISOString()

  const { data: overdueComplaints, error } = await supabase
    .from('complaints')
    .select('id, title, citizen_id, department_id, acknowledgment_deadline')
    .in('status', ['submitted', 'ai_analyzed'])
    .lt('acknowledgment_deadline', now)

  if (error) {
    console.error('[SLA Checker Error]:', error.message)
    return { escalatedCount: 0, errors: [error.message] }
  }

  if (!overdueComplaints || overdueComplaints.length === 0) {
    return { escalatedCount: 0, message: 'No overdue complaints found.' }
  }

  console.log(`[SLA Checker] Found ${overdueComplaints.length} overdue complaint(s). Escalating...`)

  const adminId = await getSystemAdminId()
  const escalatedIds = []

  for (const item of overdueComplaints) {
    const { error: updateErr } = await supabase
      .from('complaints')
      .update({
        status: 'escalated',
        escalated_at: now,
        escalation_reason: 'Authority SLA breached: No acknowledgment within required timeframe.',
      })
      .eq('id', item.id)

    if (!updateErr) {
      escalatedIds.push(item.id)

      await supabase.from('complaint_updates').insert({
        complaint_id: item.id,
        author_id: adminId || item.citizen_id,
        status: 'escalated',
        comment: 'Automatic Escalation: Government department missed acknowledgment SLA deadline. Case forwarded to NGOs.',
      })
    }
  }

  return { escalatedCount: escalatedIds.length, escalatedIds }
}

async function getSystemAdminId() {
  const { data } = await supabase
    .from('profiles')
    .select('id')
    .eq('role', 'admin')
    .limit(1)
    .maybeSingle()

  return data?.id || null
}