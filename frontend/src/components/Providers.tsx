'use client';

import { ThemeProvider } from 'next-themes';
import { ToastProvider } from '@/components/ui';
import { MCPProvider } from '@/contexts/MCPContext';

interface ProvidersProps {
  children: React.ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <MCPProvider autoConnect={false} autoReconnect={true}>
        <ToastProvider>{children}</ToastProvider>
      </MCPProvider>
    </ThemeProvider>
  );
}
