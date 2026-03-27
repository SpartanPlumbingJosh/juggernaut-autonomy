import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

const NOTIFICATION_MEMBERS = [
  'U06N32PKK8U', 'U06MN0CHE3G', 'U06NHDPGRA4', 'U07U4RCJX9B',
  'U06NAXE0M3S', 'U06N3S2B4GW', 'U06NKNW6CDT', 'U06NT7YQR6X'
];

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ jobNumber: string }> }
) {
  const { jobNumber } = await params;
  if (!/^\d+$/.test(jobNumber)) return NextResponse.json({ error: 'Invalid job number' }, { status: 400 });

  const body = await request.json();
  const { action, userId, userName, stepNum, value } = body;

  if (!userId || !NOTIFICATION_MEMBERS.includes(userId)) {
    return NextResponse.json({ error: 'Not authorized' }, { status: 403 });
  }

  try {
    const packets = await query(`SELECT id, checked_steps, notes, status, general_notes FROM spartan_ops.permit_packets WHERE st_job_id = ${jobNumber} LIMIT 1`);
    if (packets.length === 0) return NextResponse.json({ error: 'No permit packet for this job' }, { status: 404 });

    const packet = packets[0] as Record<string, any>;
    const now = new Date().toISOString();

    if (action === 'toggleStep' && stepNum !== undefined) {
      const checkedSteps = (typeof packet.checked_steps === 'object' && packet.checked_steps) ? packet.checked_steps : {};
      const stepKey = String(stepNum);
      if (checkedSteps[stepKey]) {
        delete checkedSteps[stepKey];
      } else {
        checkedSteps[stepKey] = { user_id: userId, user_name: userName || userId, completed_at: now };
      }
      await query(`
        UPDATE spartan_ops.permit_packets
        SET checked_steps = '${JSON.stringify(checkedSteps).replace(/'/g, "''")}', updated_at = now()
        WHERE st_job_id = ${jobNumber}
      `);
    } else if (action === 'saveNote' && stepNum !== undefined && value !== undefined) {
      const notes = (typeof packet.notes === 'object' && packet.notes) ? packet.notes : {};
      const stepKey = String(stepNum);
      if (!notes[stepKey]) notes[stepKey] = [];
      notes[stepKey].push({ user_id: userId, user_name: userName || userId, text: value, created_at: now });
      await query(`
        UPDATE spartan_ops.permit_packets
        SET notes = '${JSON.stringify(notes).replace(/'/g, "''")}', updated_at = now()
        WHERE st_job_id = ${jobNumber}
      `);
    } else if (action === 'updateStatus' && value) {
      await query(`
        UPDATE spartan_ops.permit_packets
        SET status = '${value.replace(/'/g, "''")}', updated_at = now()
        WHERE st_job_id = ${jobNumber}
      `);
    } else if (action === 'addGeneralNote' && value) {
      const generalNotes = Array.isArray(packet.general_notes) ? packet.general_notes : [];
      generalNotes.push({ user_id: userId, user_name: userName || userId, text: value, created_at: now });
      await query(`
        UPDATE spartan_ops.permit_packets
        SET general_notes = '${JSON.stringify(generalNotes).replace(/'/g, "''")}', updated_at = now()
        WHERE st_job_id = ${jobNumber}
      `);
    } else {
      return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
    }

    const updated = await query(`SELECT * FROM spartan_ops.permit_packets WHERE st_job_id = ${jobNumber} LIMIT 1`);
    return NextResponse.json({ packet: updated[0] });
  } catch (err) {
    console.error('Permit action error:', err);
    return NextResponse.json({ error: 'Failed to process action', detail: String(err) }, { status: 500 });
  }
}
