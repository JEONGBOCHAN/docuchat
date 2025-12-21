'use client';

import { ToastProvider } from '@/components/ui';

interface ProvidersProps {
  children: React.ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  return <ToastProvider>{children}</ToastProvider>;
}
