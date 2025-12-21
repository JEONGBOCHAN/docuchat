'use client';

interface EmptyStateProps {
  onCreateChannel: () => void;
}

export default function EmptyState({ onCreateChannel }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mb-5">
        <svg
          className="w-10 h-10 text-gray-400 dark:text-gray-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          />
        </svg>
      </div>

      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        No channels yet
      </h3>

      <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-sm mb-5">
        Create your first channel to start uploading documents and chatting with AI.
      </p>

      <button
        onClick={onCreateChannel}
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
        Create your first channel
      </button>
    </div>
  );
}
