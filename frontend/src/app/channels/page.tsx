'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import MainLayout from '@/components/layout/MainLayout';
import { ChannelCard, CreateChannelModal, DeleteConfirmModal, EmptyState } from '@/components/channels';
import { channelsApi, type Channel, type CreateChannelRequest, type UpdateChannelRequest } from '@/lib/api/channels';
import { triggerSidebarRefresh } from '@/components/layout/Sidebar';

function ChannelsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editChannel, setEditChannel] = useState<Channel | null>(null);
  const [deleteChannel, setDeleteChannel] = useState<Channel | null>(null);

  const fetchChannels = useCallback(async () => {
    try {
      setError(null);
      const response = await channelsApi.list();
      setChannels(response.channels);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load channels');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchChannels();
  }, [fetchChannels]);

  // Open create modal if ?create=true query param is present
  useEffect(() => {
    if (searchParams.get('create') === 'true') {
      setIsCreateModalOpen(true);
      // Remove the query param from URL
      router.replace('/channels', { scroll: false });
    }
  }, [searchParams, router]);

  const handleCreateChannel = async (data: CreateChannelRequest | UpdateChannelRequest) => {
    if (editChannel) {
      // Update existing channel
      await channelsApi.update(editChannel.id, data as UpdateChannelRequest);
    } else {
      // Create new channel
      await channelsApi.create(data as CreateChannelRequest);
    }
    await fetchChannels();
    triggerSidebarRefresh(); // Update sidebar
    setEditChannel(null);
  };

  const handleEditChannel = (channel: Channel) => {
    setEditChannel(channel);
    setIsCreateModalOpen(true);
  };

  const handleDeleteChannel = async () => {
    if (!deleteChannel) return;
    try {
      await channelsApi.delete(deleteChannel.id);
      await fetchChannels();
      triggerSidebarRefresh(); // Update sidebar
      setDeleteChannel(null);
    } catch (err) {
      console.error('Failed to delete channel:', err);
      alert(`채널 삭제 실패: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleCloseCreateModal = () => {
    setIsCreateModalOpen(false);
    setEditChannel(null);
  };

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto">
        {/* Page Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
              Channels
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Manage your document channels
            </p>
          </div>
          {channels.length > 0 && (
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-4 py-2 bg-blue-600 text-sm text-white rounded-md hover:bg-blue-700 transition-colors flex items-center gap-2"
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
                  d="M12 4v16m8-8H4"
                />
              </svg>
              New Channel
            </button>
          )}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="flex flex-col items-center gap-3">
              <svg
                className="animate-spin h-8 w-8 text-blue-600"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <p className="text-sm text-gray-500 dark:text-gray-400">Loading channels...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-red-600 dark:text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Failed to load channels
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">{error}</p>
            <button
              onClick={() => {
                setIsLoading(true);
                fetchChannels();
              }}
              className="px-4 py-2 border border-gray-200 dark:border-gray-800 text-sm text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Try again
            </button>
          </div>
        ) : channels.length === 0 ? (
          <EmptyState onCreateChannel={() => setIsCreateModalOpen(true)} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {channels.map((channel) => (
              <ChannelCard
                key={channel.id}
                channel={channel}
                onEdit={handleEditChannel}
                onDelete={setDeleteChannel}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      <CreateChannelModal
        isOpen={isCreateModalOpen}
        onClose={handleCloseCreateModal}
        onSubmit={handleCreateChannel}
        editChannel={editChannel}
      />

      {/* Delete Confirmation Modal */}
      <DeleteConfirmModal
        isOpen={!!deleteChannel}
        channel={deleteChannel}
        onClose={() => setDeleteChannel(null)}
        onConfirm={handleDeleteChannel}
      />
    </MainLayout>
  );
}

export default function ChannelsPage() {
  return (
    <Suspense fallback={
      <MainLayout>
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <svg
              className="animate-spin h-8 w-8 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading...</p>
          </div>
        </div>
      </MainLayout>
    }>
      <ChannelsContent />
    </Suspense>
  );
}
