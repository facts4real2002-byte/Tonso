'use client';

import { useEffect, useState } from 'react';
import { i18n } from '@/lib/i18n';
import { getCurrentBarber } from '@/app/actions/auth';
import { getShop, updateShop, addService } from '@/app/actions/shop';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [barber, setBarber] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Step 1: Account info
  const [barberName, setBarberName] = useState('');
  const [location, setLocation] = useState('');

  // Step 2: Services
  const [serviceName, setServiceName] = useState('');
  const [servicePrice, setServicePrice] = useState('');
  const [serviceDuration, setServiceDuration] = useState('30');
  const [services, setServices] = useState<any[]>([]);

  // Step 3: Schedule
  const [openHour, setOpenHour] = useState(9);
  const [closeHour, setCloseHour] = useState(18);
  const [workingDays, setWorkingDays] = useState(['MO', 'TU', 'WE', 'TH', 'FR']);

  useEffect(() => {
    const loadBarber = async () => {
      const current = await getCurrentBarber();
      if (!current || !current.shop) {
        router.push('/login');
        return;
      }
      setBarber(current);
      setBarberName(current.shop.barberName || '');
      setLocation(current.shop.location || '');
      setOpenHour(current.shop.openHour);
      setCloseHour(current.shop.closeHour);
      setWorkingDays(current.shop.workingDays);

      const shop = await getShop(current.shop.id);
      setServices(shop?.services || []);
    };

    loadBarber();
  }, [router]);

  const handleAccountUpdate = async () => {
    if (!barber?.shop?.id) return;
    setLoading(true);
    try {
      await updateShop(barber.shop.id, {
        barberName,
        location,
      });
      toast.success('Account aggiornato!');
      setStep(2);
    } catch (error: any) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddService = async () => {
    if (!barber?.shop?.id || !serviceName || !servicePrice) {
      toast.error('Compila tutti i campi');
      return;
    }
    setLoading(true);
    try {
      const newService = await addService(
        barber.shop.id,
        serviceName,
        Math.round(parseFloat(servicePrice) * 100),
        parseInt(serviceDuration)
      );
      setServices([...services, newService]);
      setServiceName('');
      setServicePrice('');
      setServiceDuration('30');
      toast.success('Servizio aggiunto!');
    } catch (error: any) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleScheduleUpdate = async () => {
    if (!barber?.shop?.id) return;
    setLoading(true);
    try {
      await updateShop(barber.shop.id, {
        openHour,
        closeHour,
        workingDays,
      });
      toast.success('Orari aggiornati!');
      setStep(4);
    } catch (error: any) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  if (!barber) {
    return <div className="p-4 text-center">{i18n.loading}</div>;
  }

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-2xl mx-auto">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex justify-between mb-4">
            {[1, 2, 3, 4].map((s) => (
              <div
                key={s}
                className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                  s <= step
                    ? 'bg-black text-white'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                {s}
              </div>
            ))}
          </div>
        </div>

        {/* Step 1: Account */}
        {step === 1 && (
          <div className="card p-6">
            <h2 className="text-2xl font-bold mb-6">{i18n.account}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Nome barbiere</label>
                <input
                  type="text"
                  value={barberName}
                  onChange={(e) => setBarberName(e.target.value)}
                  className="w-full px-4 py-2 border border-border rounded-lg"
                  placeholder="Mario Rossi"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Ubicazione</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full px-4 py-2 border border-border rounded-lg"
                  placeholder="Via Roma 123, Milano"
                />
              </div>
              <button
                onClick={handleAccountUpdate}
                disabled={loading}
                className="w-full btn-primary disabled:opacity-50"
              >
                {loading ? i18n.loading : i18n.save}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Services */}
        {step === 2 && (
          <div className="card p-6">
            <h2 className="text-2xl font-bold mb-6">{i18n.services}</h2>
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium mb-2">Nome servizio</label>
                <input
                  type="text"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  className="w-full px-4 py-2 border border-border rounded-lg"
                  placeholder="Taglio capelli"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Prezzo (€)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={servicePrice}
                    onChange={(e) => setServicePrice(e.target.value)}
                    className="w-full px-4 py-2 border border-border rounded-lg"
                    placeholder="15.00"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Durata (min)</label>
                  <input
                    type="number"
                    value={serviceDuration}
                    onChange={(e) => setServiceDuration(e.target.value)}
                    className="w-full px-4 py-2 border border-border rounded-lg"
                  />
                </div>
              </div>
              <button
                onClick={handleAddService}
                disabled={loading}
                className="w-full btn-secondary"
              >
                {i18n.add} Servizio
              </button>
            </div>

            <div className="border-t pt-6">
              <h3 className="font-bold mb-4">I tuoi servizi:</h3>
              {services.length === 0 ? (
                <p className="text-gray-600">Nessun servizio aggiunto ancora</p>
              ) : (
                <div className="space-y-2">
                  {services.map((s) => (
                    <div key={s.id} className="p-3 bg-gray-50 rounded-lg">
                      <p className="font-medium">{s.name}</p>
                      <p className="text-sm text-gray-600">
                        €{(s.priceCents / 100).toFixed(2)} • {s.durationMin} min
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {services.length > 0 && (
              <button
                onClick={() => setStep(3)}
                className="w-full btn-primary mt-6"
              >
                {i18n.save}
              </button>
            )}
          </div>
        )}

        {/* Step 3: Schedule */}
        {step === 3 && (
          <div className="card p-6">
            <h2 className="text-2xl font-bold mb-6">{i18n.schedule}</h2>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Apertura</label>
                  <input
                    type="number"
                    min="0"
                    max="23"
                    value={openHour}
                    onChange={(e) => setOpenHour(parseInt(e.target.value))}
                    className="w-full px-4 py-2 border border-border rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Chiusura</label>
                  <input
                    type="number"
                    min="0"
                    max="23"
                    value={closeHour}
                    onChange={(e) => setCloseHour(parseInt(e.target.value))}
                    className="w-full px-4 py-2 border border-border rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-3">Giorni di apertura</label>
                <div className="grid grid-cols-4 gap-2">
                  {['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'].map((day) => (
                    <button
                      key={day}
                      onClick={() => {
                        setWorkingDays((prev) =>
                          prev.includes(day)
                            ? prev.filter((d) => d !== day)
                            : [...prev, day]
                        );
                      }}
                      className={`p-2 rounded-lg font-medium transition ${
                        workingDays.includes(day)
                          ? 'bg-black text-white'
                          : 'bg-gray-200 text-gray-600'
                      }`}
                    >
                      {day}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={handleScheduleUpdate}
                disabled={loading}
                className="w-full btn-primary disabled:opacity-50"
              >
                {loading ? i18n.loading : i18n.save}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Done */}
        {step === 4 && (
          <div className="card p-6 text-center">
            <div className="text-6xl mb-4">✅</div>
            <h2 className="text-2xl font-bold mb-2">{i18n.done}</h2>
            <p className="text-gray-600 mb-6">La tua pagina di prenotazione è pronta!</p>

            <div className="bg-gray-50 p-4 rounded-lg mb-6">
              <p className="text-sm text-gray-600 mb-2">Il tuo link:</p>
              <p className="font-mono font-bold break-all">
                tonso.it/{barber.shop.slug}
              </p>
            </div>

            <button
              onClick={() => router.push('/dashboard')}
              className="w-full btn-primary mb-4"
            >
              Vai al cruscotto
            </button>
            <button
              onClick={() => {
                navigator.clipboard.writeText(`tonso.it/${barber.shop.slug}`);
                toast.success('Link copiato!');
              }}
              className="w-full btn-secondary"
            >
              Copia link
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
