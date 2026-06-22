'use client';

import { useEffect, useState } from 'react';
import { i18n } from '@/lib/i18n';
import { formatPrice } from '@/lib/utils';
import { getCurrentBarber } from '@/app/actions/auth';
import { confirmBooking, cancelBooking } from '@/app/actions/bookings';
import { createClient } from '@/lib/supabase-client';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Booking {
  id: string;
  customerName: string;
  customerPhone: string;
  startTime: string;
  status: string;
  reminded: boolean;
  service: {
    name: string;
    priceCents: number;
    durationMin: number;
  };
}

export default function DashboardPage() {
  const router = useRouter();
  const [barber, setBarber] = useState<any>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      const current = await getCurrentBarber();
      if (!current || !current.shop) {
        router.push('/login');
        return;
      }
      setBarber(current);

      // Load bookings
      const supabase = createClient();
      const { data, error } = await supabase
        .from('bookings')
        .select('*')
        .eq('shopId', current.shop.id);

      if (!error && data) {
        setBookings(data as Booking[]);
      }

      setLoading(false);

      // Subscribe to real-time updates
      const subscription = supabase
        .channel(`bookings:${current.shop.id}`)
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'Booking',
            filter: `shopId=eq.${current.shop.id}`,
          },
          (payload) => {
            setBookings((prev) => {
              if (payload.eventType === 'INSERT') {
                return [...prev, payload.new as Booking];
              } else if (payload.eventType === 'UPDATE') {
                return prev.map((b) =>
                  b.id === payload.new.id ? (payload.new as Booking) : b
                );
              } else if (payload.eventType === 'DELETE') {
                return prev.filter((b) => b.id !== payload.old.id);
              }
              return prev;
            });
          }
        )
        .subscribe();

      return () => {
        subscription.unsubscribe();
      };
    };

    loadData();
  }, [router]);

  const handleConfirm = async (bookingId: string) => {
    try {
      await confirmBooking(bookingId);
      toast.success('Prenotazione confermata!');
    } catch (error) {
      toast.error(i18n.error);
    }
  };

  const handleCancel = async (bookingId: string) => {
    try {
      await cancelBooking(bookingId);
      toast.success('Prenotazione annullata!');
    } catch (error) {
      toast.error(i18n.error);
    }
  };

  if (loading || !barber) {
    return <div className="p-4 text-center">{i18n.loading}</div>;
  }

  const todayBookings = bookings.filter((b) => {
    const bookingDate = new Date(b.startTime).toDateString();
    return bookingDate === new Date().toDateString();
  });

  const confirmedRevenue = bookings
    .filter((b) => b.status === 'CONFIRMED')
    .reduce((sum, b) => sum + b.service.priceCents, 0);

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">{i18n.dashboard}</h1>
          <button
            onClick={() => router.push('/login')}
            className="btn-secondary"
          >
            {i18n.logout}
          </button>
        </div>

        {/* Stats */}
        <div className="grid md:grid-cols-3 gap-4 mb-8">
          <div className="card p-6">
            <div className="text-sm text-gray-600 mb-2">📅 {i18n.bookingsToday}</div>
            <p className="text-3xl font-bold">{todayBookings.length}</p>
          </div>
          <div className="card p-6">
            <div className="text-sm text-gray-600 mb-2">💰 {i18n.confirmedRevenue}</div>
            <p className="text-3xl font-bold">{formatPrice(confirmedRevenue)}</p>
          </div>
          <div className="card p-6">
            <div className="text-sm text-gray-600 mb-2">👥 {i18n.clients}</div>
            <p className="text-3xl font-bold">{new Set(bookings.map((b) => b.customerPhone)).size}</p>
          </div>
        </div>

        {/* Shop Info */}
        <div className="card p-6 mb-8">
          <h2 className="text-xl font-bold mb-4">{i18n.yourBookingPage}</h2>
          <div className="bg-gray-50 p-4 rounded-lg mb-4">
            <p className="text-sm text-gray-600 mb-2">Link condivisibile:</p>
            <p className="font-mono font-bold break-all">tonso.it/{barber.shop.slug}</p>
          </div>
          <button
            onClick={() => {
              navigator.clipboard.writeText(`tonso.it/${barber.shop.slug}`);
              toast.success('Link copiato!');
            }}
            className="btn-primary"
          >
            {i18n.copyLink}
          </button>
        </div>

        {/* Bookings */}
        <div className="card p-6">
          <h2 className="text-xl font-bold mb-4">{i18n.recentBookings}</h2>
          {bookings.length === 0 ? (
            <p className="text-gray-600">Nessuna prenotazione ancora</p>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {bookings
                .sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())
                .map((booking) => (
                  <div
                    key={booking.id}
                    className="p-4 border border-border rounded-lg hover:bg-gray-50 transition"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <p className="font-bold">{booking.customerName}</p>
                        <p className="text-sm text-gray-600">{booking.customerPhone}</p>
                        <p className="text-sm text-gray-600 mt-1">
                          {booking.service.name} • {new Date(booking.startTime).toLocaleString('it-IT')}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className={`inline-block px-3 py-1 rounded-full text-xs font-medium mb-2 ${
                          booking.status === 'CONFIRMED'
                            ? 'bg-green-100 text-green-800'
                            : booking.status === 'CANCELLED'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {booking.status === 'CONFIRMED' ? i18n.confirmed : booking.status === 'CANCELLED' ? i18n.cancelled : i18n.pending}
                        </div>
                        <p className="font-bold">{formatPrice(booking.service.priceCents)}</p>
                      </div>
                    </div>
                    {booking.status === 'PENDING' && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleConfirm(booking.id)}
                          className="flex-1 btn-primary text-sm py-1"
                        >
                          {i18n.confirm}
                        </button>
                        <button
                          onClick={() => handleCancel(booking.id)}
                          className="flex-1 btn-secondary text-sm py-1"
                        >
                          {i18n.cancel}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
