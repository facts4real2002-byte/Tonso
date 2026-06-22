'use server';

import { prisma } from '@/lib/db';
import { zonedTimeToUtc } from 'date-fns-tz';
import { addMinutes, startOfDay, endOfDay } from 'date-fns';
import { formatInTimeZone } from 'date-fns-tz';

const TIMEZONE = 'Europe/Rome';

export async function getAvailableSlots(
  shopId: string,
  dateISO: string
): Promise<string[]> {
  const shop = await prisma.shop.findUnique({
    where: { id: shopId },
    include: { bookings: true, services: true },
  });

  if (!shop) throw new Error('Shop not found');

  // Parse the date in the shop's timezone
  const [year, month, day] = dateISO.split('-').map(Number);
  const localDate = new Date(year, month - 1, day, 0, 0, 0);

  // Get day of week
  const dayOfWeek = localDate.getDay();
  const days = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'];
  const dayCode = days[dayOfWeek];

  // Check if shop is open
  if (!shop.workingDays.includes(dayCode)) {
    return [];
  }

  // Get all bookings for this day
  const dayStart = zonedTimeToUtc(startOfDay(localDate), TIMEZONE);
  const dayEnd = zonedTimeToUtc(endOfDay(localDate), TIMEZONE);

  const bookings = await prisma.booking.findMany({
    where: {
      shopId,
      startTime: {
        gte: dayStart,
        lte: dayEnd,
      },
    },
  });

  const bookedTimes = new Set(bookings.map((b) => b.startTime.getTime()));

  // Generate slots
  const slots: string[] = [];
  const serviceMinDuration = Math.min(...(shop.services.map((s) => s.durationMin) || [30]));
  const stepMinutes = serviceMinDuration || 30;

  let currentHour = shop.openHour;
  while (currentHour < shop.closeHour) {
    const slotDate = new Date(year, month - 1, day, currentHour, 0, 0);
    const slotTimeUTC = zonedTimeToUtc(slotDate, TIMEZONE);

    // Skip if booked or in the past
    if (!bookedTimes.has(slotTimeUTC.getTime()) && slotTimeUTC > new Date()) {
      const timeStr = formatInTimeZone(slotTimeUTC, TIMEZONE, 'HH:mm');
      slots.push(timeStr);
    }

    currentHour += 0.5; // 30 min slots
  }

  return slots;
}

export async function createBooking({
  shopId,
  serviceId,
  startTime,
  customerName,
  customerPhone,
}: {
  shopId: string;
  serviceId: string;
  startTime: Date;
  customerName: string;
  customerPhone: string;
}) {
  try {
    const booking = await prisma.booking.create({
      data: {
        shopId,
        serviceId,
        startTime,
        customerName,
        customerPhone,
        status: 'PENDING',
      },
    });

    return booking;
  } catch (error: any) {
    if (error.code === 'P2002') {
      throw new Error('P2002: Slot already taken');
    }
    throw error;
  }
}

export async function confirmBooking(bookingId: string) {
  const booking = await prisma.booking.update({
    where: { id: bookingId },
    data: { status: 'CONFIRMED' },
  });
  return booking;
}

export async function cancelBooking(bookingId: string) {
  const booking = await prisma.booking.update({
    where: { id: bookingId },
    data: { status: 'CANCELLED' },
  });
  return booking;
}
