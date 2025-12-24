'use client';

import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';
import MainLayout from '@/components/layout/MainLayout';

/**
 * 설정 페이지
 *
 * Dark Mode toggle enabled, other settings Coming Soon
 */
export default function SettingsPage() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Prevent hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  const isDarkMode = mounted ? resolvedTheme === 'dark' : false;

  const handleToggle = () => {
    setTheme(isDarkMode ? 'light' : 'dark');
  };

  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Settings
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage your application preferences
          </p>
        </div>

        {/* Settings Sections */}
        <div className="space-y-6">
          {/* Theme Section - Active */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
              Appearance
            </h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Dark Mode
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Toggle between light and dark theme
                </p>
              </div>
              {/* Toggle Switch */}
              <button
                type="button"
                role="switch"
                aria-checked={isDarkMode}
                aria-label="Toggle dark mode"
                onClick={handleToggle}
                disabled={!mounted}
                className={`
                  relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full
                  border-2 border-transparent transition-colors duration-200 ease-in-out
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                  dark:focus:ring-offset-gray-900
                  ${!mounted ? 'opacity-50 cursor-not-allowed' : ''}
                  ${isDarkMode ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'}
                `}
              >
                <span
                  className={`
                    pointer-events-none inline-block h-5 w-5 transform rounded-full
                    bg-white shadow ring-0 transition duration-200 ease-in-out
                    ${isDarkMode ? 'translate-x-5' : 'translate-x-0'}
                  `}
                />
              </button>
            </div>
            {/* Theme Options */}
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Theme Preference
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setTheme('light')}
                  disabled={!mounted}
                  className={`
                    px-4 py-2 text-sm rounded-md border transition-colors
                    ${theme === 'light'
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                      : 'border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                    }
                    ${!mounted ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                >
                  Light
                </button>
                <button
                  onClick={() => setTheme('dark')}
                  disabled={!mounted}
                  className={`
                    px-4 py-2 text-sm rounded-md border transition-colors
                    ${theme === 'dark'
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                      : 'border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                    }
                    ${!mounted ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                >
                  Dark
                </button>
                <button
                  onClick={() => setTheme('system')}
                  disabled={!mounted}
                  className={`
                    px-4 py-2 text-sm rounded-md border transition-colors
                    ${theme === 'system'
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                      : 'border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                    }
                    ${!mounted ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                >
                  System
                </button>
              </div>
            </div>
          </div>

          {/* API Section - Coming Soon */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-6 opacity-50 pointer-events-none">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                API Configuration
              </h3>
              <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 rounded">
                Coming Soon
              </span>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Gemini API Key
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Configure your own API key for enhanced usage
              </p>
            </div>
          </div>

          {/* Data Section - Coming Soon */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-6 opacity-50 pointer-events-none">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                Data Management
              </h3>
              <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 rounded">
                Coming Soon
              </span>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Export Data
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Download all your channels and documents
              </p>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
