'use server';

import { createServerSupabaseClient } from '@/lib/supabase-server';
import { prisma } from '@/lib/db';

export async function registerBarber(
  email: string,
  password: string,
  shopName: string
) {
  const supabase = createServerSupabaseClient();

  // Sign up with Supabase Auth
  const { data, error: authError } = await supabase.auth.signUp({
    email,
    password,
  });

  if (authError || !data.user) {
    throw new Error(authError?.message || 'Auth error');
  }

  // Create shop record
  const slug = shopName
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');

  try {
    const shop = await prisma.shop.create({
      data: {
        ownerId: data.user.id,
        slug: `${slug}-${data.user.id.slice(0, 6)}`,
        name: shopName,
        barberName: '',
        location: '',
      },
    });

    return {
      userId: data.user.id,
      shopId: shop.id,
      slug: shop.slug,
    };
  } catch (error) {
    // Clean up auth user if shop creation fails
    await supabase.auth.signOut();
    throw error;
  }
}

export async function loginBarber(email: string, password: string) {
  const supabase = createServerSupabaseClient();

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error || !data.user) {
    throw new Error(error?.message || 'Login failed');
  }

  return { userId: data.user.id };
}

export async function logoutBarber() {
  const supabase = createServerSupabaseClient();
  await supabase.auth.signOut();
}

export async function getCurrentBarber() {
  const supabase = createServerSupabaseClient();
  const { data, error } = await supabase.auth.getUser();

  if (error || !data.user) {
    return null;
  }

  const shop = await prisma.shop.findFirst({
    where: { ownerId: data.user.id },
  });

  return {
    userId: data.user.id,
    email: data.user.email,
    shop,
  };
}
