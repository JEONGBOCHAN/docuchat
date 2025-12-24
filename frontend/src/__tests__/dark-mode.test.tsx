import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from 'next-themes';

// Mock next-themes
vi.mock('next-themes', async () => {
  const actual = await vi.importActual('next-themes');
  return {
    ...actual,
    useTheme: vi.fn(() => ({
      theme: 'light',
      setTheme: vi.fn(),
      resolvedTheme: 'light',
    })),
  };
});

// Mock MainLayout
vi.mock('@/components/layout/MainLayout', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="main-layout">{children}</div>,
}));

import { useTheme } from 'next-themes';
import SettingsPage from '@/app/settings/page';

describe('Dark Mode Feature', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Settings Page', () => {
    it('renders the settings page with dark mode toggle', () => {
      render(<SettingsPage />);

      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('Appearance')).toBeInTheDocument();
      expect(screen.getByText('Dark Mode')).toBeInTheDocument();
    });

    it('renders theme preference buttons', () => {
      render(<SettingsPage />);

      expect(screen.getByText('Light')).toBeInTheDocument();
      expect(screen.getByText('Dark')).toBeInTheDocument();
      expect(screen.getByText('System')).toBeInTheDocument();
    });

    it('renders Coming Soon sections for API and Data Management', () => {
      render(<SettingsPage />);

      const comingSoonBadges = screen.getAllByText('Coming Soon');
      expect(comingSoonBadges).toHaveLength(2);

      expect(screen.getByText('API Configuration')).toBeInTheDocument();
      expect(screen.getByText('Data Management')).toBeInTheDocument();
    });

    it('toggle switch has correct accessibility attributes', () => {
      render(<SettingsPage />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-label', 'Toggle dark mode');
      expect(toggle).toHaveAttribute('aria-checked');
    });
  });

  describe('Theme Toggle Functionality', () => {
    it('calls setTheme when toggle is clicked', async () => {
      const mockSetTheme = vi.fn();
      vi.mocked(useTheme).mockReturnValue({
        theme: 'light',
        setTheme: mockSetTheme,
        resolvedTheme: 'light',
        themes: ['light', 'dark', 'system'],
        forcedTheme: undefined,
        systemTheme: 'light',
      });

      render(<SettingsPage />);

      // Wait for component to mount
      await waitFor(() => {
        const toggle = screen.getByRole('switch');
        expect(toggle).not.toBeDisabled();
      });

      const toggle = screen.getByRole('switch');
      fireEvent.click(toggle);

      expect(mockSetTheme).toHaveBeenCalledWith('dark');
    });

    it('calls setTheme with correct value when theme buttons are clicked', async () => {
      const mockSetTheme = vi.fn();
      vi.mocked(useTheme).mockReturnValue({
        theme: 'light',
        setTheme: mockSetTheme,
        resolvedTheme: 'light',
        themes: ['light', 'dark', 'system'],
        forcedTheme: undefined,
        systemTheme: 'light',
      });

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Dark')).not.toBeDisabled();
      });

      fireEvent.click(screen.getByText('Dark'));
      expect(mockSetTheme).toHaveBeenCalledWith('dark');

      fireEvent.click(screen.getByText('Light'));
      expect(mockSetTheme).toHaveBeenCalledWith('light');

      fireEvent.click(screen.getByText('System'));
      expect(mockSetTheme).toHaveBeenCalledWith('system');
    });

    it('toggle shows correct state when in dark mode', async () => {
      vi.mocked(useTheme).mockReturnValue({
        theme: 'dark',
        setTheme: vi.fn(),
        resolvedTheme: 'dark',
        themes: ['light', 'dark', 'system'],
        forcedTheme: undefined,
        systemTheme: 'light',
      });

      render(<SettingsPage />);

      await waitFor(() => {
        const toggle = screen.getByRole('switch');
        expect(toggle).toHaveAttribute('aria-checked', 'true');
      });
    });

    it('toggle shows correct state when in light mode', async () => {
      vi.mocked(useTheme).mockReturnValue({
        theme: 'light',
        setTheme: vi.fn(),
        resolvedTheme: 'light',
        themes: ['light', 'dark', 'system'],
        forcedTheme: undefined,
        systemTheme: 'light',
      });

      render(<SettingsPage />);

      await waitFor(() => {
        const toggle = screen.getByRole('switch');
        expect(toggle).toHaveAttribute('aria-checked', 'false');
      });
    });
  });

  describe('ThemeProvider Configuration', () => {
    it('ThemeProvider is exported from next-themes', async () => {
      const nextThemes = await import('next-themes');
      expect(nextThemes.ThemeProvider).toBeDefined();
    });
  });
});
