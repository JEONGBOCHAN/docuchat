'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { channelsApi, encodeChannelIdForUrl, type Channel } from '@/lib/api/channels';

// Custom event name for channel updates
export const CHANNELS_UPDATED_EVENT = 'channels-updated';

// Helper function to trigger sidebar refresh from other components
export function triggerSidebarRefresh() {
  window.dispatchEvent(new CustomEvent(CHANNELS_UPDATED_EVENT));
}

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ isOpen = true, onClose }: SidebarProps) {
  const pathname = usePathname();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchChannels = useCallback(async () => {
    try {
      const response = await channelsApi.list();
      setChannels(response.channels);
    } catch (error) {
      console.error('Failed to fetch channels for sidebar:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchChannels();
  }, [pathname, fetchChannels]);

  // Listen for custom event to refresh channels
  useEffect(() => {
    const handleChannelsUpdated = () => {
      fetchChannels();
    };

    window.addEventListener(CHANNELS_UPDATED_EVENT, handleChannelsUpdated);
    return () => {
      window.removeEventListener(CHANNELS_UPDATED_EVENT, handleChannelsUpdated);
    };
  }, [fetchChannels]);

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`w-64 h-[calc(100vh-3.5rem)] border-r border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 fixed top-14 left-0 overflow-y-auto z-40 transition-transform duration-200 lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            Channels
          </h2>
          <Link
            href="/channels/new"
            className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
          >
            + New
          </Link>
        </div>

        <nav className="space-y-1">
          {isLoading ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-2">
              Loading...
            </p>
          ) : channels.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-2">
              No channels yet
            </p>
          ) : (
            channels.map((channel) => {
              const urlSafeId = encodeChannelIdForUrl(channel.id);
              const isActive = pathname === `/channels/${urlSafeId}`;
              return (
                <Link
                  key={channel.id}
                  href={`/channels/${urlSafeId}`}
                  className={`block px-3 py-2 rounded-md text-sm transition-colors ${
                    isActive
                      ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`}
                >
                  {channel.name}
                </Link>
              );
            })
          )}
        </nav>
      </div>

      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 dark:border-gray-800">
        <Link
          href="/settings"
          className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          Settings
        </Link>
      </div>
      </aside>
    </>
  );
}
