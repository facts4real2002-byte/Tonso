import { prisma } from '@/lib/db';
import { notFound } from 'next/navigation';
import BookingPageClient from './client';

export default async function BookingPage({
  params,
}: {
  params: { slug: string };
}) {
  const shop = await prisma.shop.findUnique({
    where: { slug: params.slug },
    include: {
      services: {
        orderBy: { createdAt: 'asc' },
      },
    },
  });

  if (!shop) {
    notFound();
  }

  return <BookingPageClient shop={shop} services={shop.services} />;
}
