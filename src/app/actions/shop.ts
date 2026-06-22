'use server';

import { prisma } from '@/lib/db';

export async function updateShop(shopId: string, data: any) {
  const shop = await prisma.shop.update({
    where: { id: shopId },
    data,
  });
  return shop;
}

export async function addService(
  shopId: string,
  name: string,
  priceCents: number,
  durationMin: number
) {
  const service = await prisma.service.create({
    data: {
      shopId,
      name,
      priceCents,
      durationMin,
    },
  });
  return service;
}

export async function updateService(
  serviceId: string,
  name: string,
  priceCents: number,
  durationMin: number
) {
  const service = await prisma.service.update({
    where: { id: serviceId },
    data: { name, priceCents, durationMin },
  });
  return service;
}

export async function deleteService(serviceId: string) {
  await prisma.service.delete({
    where: { id: serviceId },
  });
}

export async function getShop(shopId: string) {
  const shop = await prisma.shop.findUnique({
    where: { id: shopId },
    include: {
      services: { orderBy: { createdAt: 'asc' } },
    },
  });
  return shop;
}
