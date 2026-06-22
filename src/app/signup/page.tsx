'use client';

import { useState } from 'react';
import { i18n } from '@/lib/i18n';
import { registerBarber } from '@/app/actions/auth';
import { toast } from 'sonner';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [shopName, setShopName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await registerBarber(email, password, shopName);
      toast.success('Registrazione completata! Benvenuto.');
      router.push('/onboarding');
    } catch (error: any) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="card p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold mb-2">{i18n.signup}</h1>
        <p className="text-gray-600 mb-6">Crea il tuo account barberia</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 border border-border rounded-lg"
              placeholder="barbiere@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-border rounded-lg"
              minLength={6}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Nome della barberia</label>
            <input
              type="text"
              required
              value={shopName}
              onChange={(e) => setShopName(e.target.value)}
              className="w-full px-4 py-2 border border-border rounded-lg"
              placeholder="Barberia Elite"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary disabled:opacity-50"
          >
            {loading ? i18n.loading : i18n.signup}
          </button>
        </form>

        <p className="text-sm text-gray-600 text-center mt-6">
          Hai già un account?{' '}
          <Link href="/login" className="text-black font-medium hover:underline">
            {i18n.login}
          </Link>
        </p>
      </div>
    </div>
  );
}
