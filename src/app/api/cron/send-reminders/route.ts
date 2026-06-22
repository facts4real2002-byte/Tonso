import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  const cron_secret = request.headers.get('authorization')?.replace('Bearer ', '');

  if (cron_secret !== process.env.CRON_SECRET) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    console.log('[Cron] send-reminders triggered');
    
    // In production, this would:
    // 1. Find bookings starting in next ~2h with reminded = false
    // 2. For each: send WhatsApp via Twilio, set reminded = true
    // For now, just log
    
    return NextResponse.json({ success: true, message: 'Reminders sent' });
  } catch (error) {
    console.error('[Cron] Error:', error);
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}
