import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Tonso - Prenota il tuo barbiere',
  description: 'La piattaforma di prenotazione per barbieri',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className="bg-background">{children}</body>
    </html>
  );
}
