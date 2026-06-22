'use client';

import { useState } from 'react';
import { i18n } from '@/lib/i18n';
import { formatPrice } from '@/lib/utils';
import { createBooking, getAvailableSlots } from '@/app/actions/bookings';
import { toast } from 'sonner';

interface Service {
  id: string;
  name: string;
  priceCents: number;
  durationMin: number;
}

interface Shop {
  id: string;
  name: string;
  barberName: string;
  location: string;
  timezone: string;
}

export default function BookingPageClient({
  shop,
  services,
}: {
  shop: Shop;
  services: Service[];
}) {
  const [step, setStep] = useState<'service' | 'date' | 'time' | 'details'>('service');
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [selectedTime, setSelectedTime] = useState<string>('');
  const [availableSlots, setAvailableSlots] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');

  const handleSelectService = (service: Service) => {
    setSelectedService(service);
    setStep('date');
  };

  const handleDateChange = async (date: string) => {
    setSelectedDate(date);
    setLoading(true);
    try {
      const slots = await getAvailableSlots(shop.id, date);
      setAvailableSlots(slots);
      setStep('time');
    } catch (error) {
      toast.error(i18n.error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTime = (time: string) => {
    setSelectedTime(time);
    setStep('details');
  };

  const handleSubmitBooking = async () => {
    if (!customerName || !customerPhone) {
      toast.error('Compila tutti i campi');
      return;
    }

    setLoading(true);
    try {
      await createBooking({
        shopId: shop.id,
        serviceId: selectedService!.id,
        startTime: new Date(`${selectedDate}T${selectedTime}`),
        customerName,
        customerPhone,
      });
      toast.success(i18n.bookingConfirmed);
      // Reset form
      setStep('service');
      setSelectedService(null);
      setSelectedDate('');
      setSelectedTime('');
      setCustomerName('');
      setCustomerPhone('');
    } catch (error: any) {
      if (error.message?.includes('P2002')) {
        toast.error(i18n.timeJustTaken);
        setStep('time');
      } else {
        toast.error(i18n.error);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold mb-2">{shop.name}</h1>
          <p className="text-gray-600">{shop.barberName}</p>
          <p className="text-sm text-gray-500">{shop.location}</p>
        </div>

        {/* Service Selection */}
        {step === 'service' && (
          <div className="card p-6">
            <h2 className="text-xl font-bold mb-4">{i18n.selectService}</h2>
            <div className="space-y-3">
              {services.map((service) => (
                <button
                  key={service.id}
                  onClick={() => handleSelectService(service)}
                  className="w-full p-4 border border-border rounded-lg hover:bg-gray-50 transition text-left"
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="font-medium">{service.name}</p>
                      <p className="text-sm text-gray-600">
                        {service.durationMin} minuti
                      </p>
                    </div>
                    <p className="font-bold">{formatPrice(service.priceCents)}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Date Selection */}
        {step === 'date' && selectedService && (
          <div className="card p-6">
            <button
              onClick={() => setStep('service')}
              className="text-sm text-gray-600 mb-4 hover:text-gray-900"
            >
              ← {i18n.back}
            </button>
            <h2 className="text-xl font-bold mb-4">{i18n.selectDate}</h2>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => handleDateChange(e.target.value)}
              className="w-full px-4 py-2 border border-border rounded-lg"
              min={new Date().toISOString().split('T')[0]}
            />
          </div>
        )}

        {/* Time Selection */}
        {step === 'time' && selectedService && (
          <div className="card p-6">
            <button
              onClick={() => setStep('date')}
              className="text-sm text-gray-600 mb-4 hover:text-gray-900"
            >
              ← {i18n.back}
            </button>
            <h2 className="text-xl font-bold mb-4">{i18n.selectTime}</h2>
            {loading ? (
              <p className="text-center text-gray-600">{i18n.loading}</p>
            ) : availableSlots.length === 0 ? (
              <p className="text-center text-gray-600">{i18n.noAvailableSlots}</p>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                {availableSlots.map((slot) => (
                  <button
                    key={slot}
                    onClick={() => handleSelectTime(slot)}
                    className="p-3 border border-border rounded-lg hover:bg-black hover:text-white transition font-medium"
                  >
                    {slot}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Details & Confirmation */}
        {step === 'details' && selectedService && (
          <div className="card p-6">
            <button
              onClick={() => setStep('time')}
              className="text-sm text-gray-600 mb-4 hover:text-gray-900"
            >
              ← {i18n.back}
            </button>
            <h2 className="text-xl font-bold mb-6">{i18n.confirm}</h2>

            <div className="space-y-4 mb-6">
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">Servizio</p>
                <p className="font-bold">{selectedService.name}</p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">Data e ora</p>
                <p className="font-bold">
                  {selectedDate} {selectedTime}
                </p>
              </div>
            </div>

            <div className="space-y-4 mb-6">
              <input
                type="text"
                placeholder={i18n.yourName}
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full px-4 py-2 border border-border rounded-lg"
              />
              <input
                type="tel"
                placeholder={i18n.yourPhone}
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                className="w-full px-4 py-2 border border-border rounded-lg"
              />
            </div>

            <p className="text-sm text-gray-600 mb-6">{i18n.youWillReceiveReminder}</p>

            <button
              onClick={handleSubmitBooking}
              disabled={loading}
              className="w-full btn-primary disabled:opacity-50"
            >
              {loading ? i18n.loading : i18n.confirm}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
