'use client';

import { useState, useEffect, useCallback } from 'react';
import { googleDriveApi, type DriveFile } from '@/lib/api/google-drive';

interface GoogleDrivePickerProps {
  channelId: string;
  onImportComplete?: () => void;
  onClose?: () => void;
}

export default function GoogleDrivePicker({
  channelId,
  onImportComplete,
  onClose,
}: GoogleDrivePickerProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [folderPath, setFolderPath] = useState<{ id: string | null; name: string }[]>([
    { id: null, name: 'My Drive' },
  ]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [importingFiles, setImportingFiles] = useState<Set<string>>(new Set());
  const [nextPageToken, setNextPageToken] = useState<string | undefined>();

  // Check connection on mount
  useEffect(() => {
    setIsConnected(googleDriveApi.isConnected());
  }, []);

  // Load files when connected
  const loadFiles = useCallback(async (folderId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await googleDriveApi.listFiles(folderId || undefined);
      setFiles(response.files);
      setNextPageToken(response.next_page_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load files');
      if (err instanceof Error && err.message.includes('Not connected')) {
        setIsConnected(false);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isConnected) {
      const currentFolder = folderPath[folderPath.length - 1];
      loadFiles(currentFolder.id || undefined);
    }
  }, [isConnected, folderPath, loadFiles]);

  const handleConnect = async () => {
    setIsConnecting(true);
    setError(null);
    try {
      const success = await googleDriveApi.connect();
      setIsConnected(success);
      if (!success) {
        setError('Failed to connect to Google Drive');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = () => {
    googleDriveApi.disconnect();
    setIsConnected(false);
    setFiles([]);
    setFolderPath([{ id: null, name: 'My Drive' }]);
  };

  const handleFolderClick = (file: DriveFile) => {
    setFolderPath([...folderPath, { id: file.id, name: file.name }]);
    setSelectedFiles(new Set());
  };

  const handleBreadcrumbClick = (index: number) => {
    setFolderPath(folderPath.slice(0, index + 1));
    setSelectedFiles(new Set());
  };

  const handleFileSelect = (file: DriveFile) => {
    if (file.mimeType === 'application/vnd.google-apps.folder') {
      handleFolderClick(file);
      return;
    }

    const newSelected = new Set(selectedFiles);
    if (newSelected.has(file.id)) {
      newSelected.delete(file.id);
    } else {
      newSelected.add(file.id);
    }
    setSelectedFiles(newSelected);
  };

  const handleImport = async () => {
    if (selectedFiles.size === 0) return;

    const filesToImport = files.filter((f) => selectedFiles.has(f.id));
    setImportingFiles(new Set(selectedFiles));

    let successCount = 0;
    for (const file of filesToImport) {
      try {
        await googleDriveApi.importFile(channelId, file.id);
        successCount++;
      } catch (err) {
        console.error(`Failed to import ${file.name}:`, err);
      }
    }

    setImportingFiles(new Set());
    setSelectedFiles(new Set());

    if (successCount > 0) {
      onImportComplete?.();
    }
  };

  const loadMore = async () => {
    if (!nextPageToken || isLoading) return;

    setIsLoading(true);
    try {
      const currentFolder = folderPath[folderPath.length - 1];
      const response = await googleDriveApi.listFiles(
        currentFolder.id || undefined,
        nextPageToken
      );
      setFiles([...files, ...response.files]);
      setNextPageToken(response.next_page_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load more files');
    } finally {
      setIsLoading(false);
    }
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType === 'application/vnd.google-apps.folder') {
      return (
        <svg className="w-5 h-5 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
        </svg>
      );
    }
    if (mimeType === 'application/pdf') {
      return (
        <svg className="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
            clipRule="evenodd"
          />
        </svg>
      );
    }
    return (
      <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
          clipRule="evenodd"
        />
      </svg>
    );
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (!isConnected) {
    return (
      <div className="p-6 text-center">
        <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-gray-400" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12.545 10.239v3.821h5.445c-.712 2.315-2.647 3.972-5.445 3.972a6.033 6.033 0 110-12.064c1.498 0 2.866.549 3.921 1.453l2.814-2.814A9.969 9.969 0 0012.545 2C7.021 2 2.543 6.477 2.543 12s4.478 10 10.002 10c8.396 0 10.249-7.85 9.426-11.748l-9.426-.013z" />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
          Connect Google Drive
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Import documents directly from your Google Drive
        </p>
        {error && (
          <p className="text-sm text-red-500 mb-4">{error}</p>
        )}
        <button
          onClick={handleConnect}
          disabled={isConnecting}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 inline-flex items-center gap-2"
        >
          {isConnecting ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Connecting...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12.545 10.239v3.821h5.445c-.712 2.315-2.647 3.972-5.445 3.972a6.033 6.033 0 110-12.064c1.498 0 2.866.549 3.921 1.453l2.814-2.814A9.969 9.969 0 0012.545 2C7.021 2 2.543 6.477 2.543 12s4.478 10 10.002 10c8.396 0 10.249-7.85 9.426-11.748l-9.426-.013z" />
              </svg>
              Connect with Google
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full max-h-[500px]">
      {/* Header */}
      <div className="p-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm overflow-x-auto">
          {folderPath.map((folder, index) => (
            <div key={index} className="flex items-center">
              {index > 0 && (
                <svg className="w-4 h-4 text-gray-400 mx-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
              <button
                onClick={() => handleBreadcrumbClick(index)}
                className={`hover:text-blue-600 dark:hover:text-blue-400 whitespace-nowrap ${
                  index === folderPath.length - 1
                    ? 'font-medium text-gray-900 dark:text-white'
                    : 'text-gray-500 dark:text-gray-400'
                }`}
              >
                {folder.name}
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={handleDisconnect}
          className="text-xs text-gray-500 hover:text-red-500 whitespace-nowrap ml-2"
        >
          Disconnect
        </button>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="p-4 text-center text-red-500 text-sm">{error}</div>
        )}

        {isLoading && files.length === 0 ? (
          <div className="p-8 text-center">
            <svg className="animate-spin h-6 w-6 mx-auto text-gray-400" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : files.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400 text-sm">
            No supported files in this folder
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {files.map((file) => {
              const isFolder = file.mimeType === 'application/vnd.google-apps.folder';
              const isSelected = selectedFiles.has(file.id);
              const isImporting = importingFiles.has(file.id);

              return (
                <div
                  key={file.id}
                  onClick={() => handleFileSelect(file)}
                  className={`flex items-center gap-3 p-3 cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-900/20'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                  }`}
                >
                  {!isFolder && (
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  )}
                  <div className="flex-shrink-0">{getFileIcon(file.mimeType)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {file.name}
                    </p>
                    {!isFolder && file.size && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatFileSize(file.size)}
                      </p>
                    )}
                  </div>
                  {isImporting && (
                    <svg className="animate-spin h-4 w-4 text-blue-600" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  {isFolder && (
                    <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {nextPageToken && !isLoading && (
          <button
            onClick={loadMore}
            className="w-full p-3 text-sm text-blue-600 dark:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Load more
          </button>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-800 flex items-center justify-between">
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {selectedFiles.size > 0 ? `${selectedFiles.size} file(s) selected` : 'Select files to import'}
        </span>
        <div className="flex gap-2">
          {onClose && (
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleImport}
            disabled={selectedFiles.size === 0 || importingFiles.size > 0}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {importingFiles.size > 0 ? 'Importing...' : 'Import Selected'}
          </button>
        </div>
      </div>
    </div>
  );
}
