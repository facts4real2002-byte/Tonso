import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // Delete existing data
  await prisma.booking.deleteMany({});
  await prisma.service.deleteMany({});
  await prisma.shop.deleteMany({});

  // Create demo barber (using a fake UUID for ownerId)
  const demoOwnerId = '00000000-0000-0000-0000-000000000001';

  const shop = await prisma.shop.create({
    data: {
      ownerId: demoOwnerId,
      slug: 'barberia-elite',
      name: 'Barberia Elite',
      barberName: 'Mario Rossi',
      location: 'Via Roma 123, Milano',
      openHour: 9,
      closeHour: 18,
      workingDays: ['MO', 'TU', 'WE', 'TH', 'FR'],
      timezone: 'Europe/Rome',
      subscriptionStatus: 'active',
      trialEndsAt: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000),
    },
  });

  // Create services
  const haircut = await prisma.service.create({
    data: {
      shopId: shop.id,
      name: 'Taglio capelli',
      priceCents: 1500,
      durationMin: 30,
    },
  });

  const beard = await prisma.service.create({
    data: {
      shopId: shop.id,
      name: 'Barba',
      priceCents: 1000,
      durationMin: 20,
    },
  });

  const combo = await prisma.service.create({
    data: {
      shopId: shop.id,
      name: 'Taglio + Barba',
      priceCents: 2200,
      durationMin: 45,
    },
  });

  // Create demo bookings
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(10, 0, 0, 0);

  await prisma.booking.create({
    data: {
      shopId: shop.id,
      serviceId: haircut.id,
      startTime: tomorrow,
      customerName: 'Giuseppe Verdi',
      customerPhone: '+393331234567',
      status: 'CONFIRMED',
      reminded: false,
    },
  });

  const tomorrow2 = new Date(tomorrow);
  tomorrow2.setHours(11, 0, 0, 0);

  await prisma.booking.create({
    data: {
      shopId: shop.id,
      serviceId: combo.id,
      startTime: tomorrow2,
      customerName: 'Sofia Bianchi',
      customerPhone: '+393339876543',
      status: 'PENDING',
      reminded: false,
    },
  });

  console.log('✅ Seed completed');
  console.log('Demo shop slug: barberia-elite');
  console.log('Demo services created: Taglio, Barba, Combo');
  console.log('Demo bookings added for tomorrow');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
