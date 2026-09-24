import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-sans/latin-600.css';
import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'ASCENSION · Safety Intelligence',
  description: 'Evidence-grounded SIF precursor intelligence and HSE review.',
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
