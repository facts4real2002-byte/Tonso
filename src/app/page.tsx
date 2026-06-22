'use client';

import { i18n } from '@/lib/i18n';
import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      {/* Hero */}
      <section className="pt-20 pb-20 px-4">
        <div className="max-w-2xl mx-auto text-center">
          <h1 className="text-5xl font-bold mb-6 text-gray-900">
            Tonso
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            La piattaforma di prenotazione per barbieri. Agenda piena, niente telefonate, meno no-show.
          </p>
          <div className="flex gap-4 justify-center">
            <Link href="/signup" className="btn-primary">
              {i18n.createLink}
            </Link>
            <Link href="/login" className="btn-secondary">
              {i18n.login}
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-4 max-w-4xl mx-auto">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="card p-6">
            <div className="text-4xl mb-4">📅</div>
            <h3 className="font-bold mb-2">Agenda Automatica</h3>
            <p className="text-gray-600 text-sm">
              I tuoi clienti prenotano 24/7 dal loro telefono. Tu gestisci tutto dal cruscotto.
            </p>
          </div>
          <div className="card p-6">
            <div className="text-4xl mb-4">📱</div>
            <h3 className="font-bold mb-2">Promemoria WhatsApp</h3>
            <p className="text-gray-600 text-sm">
              I clienti ricevono un promemoria automatico 2 ore prima. Addio no-show!
            </p>
          </div>
          <div className="card p-6">
            <div className="text-4xl mb-4">⚡</div>
            <h3 className="font-bold mb-2">Aggiornamento in Tempo Reale</h3>
            <p className="text-gray-600 text-sm">
              Vedi nuove prenotazioni istantaneamente. Nessun refresh richiesto.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-4 text-center">
        <h2 className="text-3xl font-bold mb-4">Pronto a partire?</h2>
        <p className="text-gray-600 mb-8">14 giorni di prova gratuita, poi €20/mese</p>
        <Link href="/signup" className="btn-primary">
          {i18n.createLink}
        </Link>
      </section>
    </main>
  );
}
