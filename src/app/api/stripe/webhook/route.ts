import { NextRequest, NextResponse } from 'next/server';
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(request: NextRequest) {
  const sig = request.headers.get('stripe-signature');
  if (!sig) {
    return NextResponse.json({ error: 'No signature' }, { status: 400 });
  }

  let event;
  try {
    const body = await request.text();
    event = stripe.webhooks.constructEvent(
      body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch (error: any) {
    console.error('Webhook error:', error);
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  // Handle events
  if (event.type === 'customer.subscription.updated') {
    // Update shop subscription status
    console.log('[Stripe] Subscription updated:', event.data.object);
  }

  if (event.type === 'customer.subscription.deleted') {
    // Mark subscription as canceled
    console.log('[Stripe] Subscription deleted:', event.data.object);
  }

  return NextResponse.json({ received: true });
}
