import apiClient, { API_BASE_URL } from './client';

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: number;
  modifiedTime?: string;
  iconLink?: string;
  thumbnailLink?: string;
  parents?: string[];
}

export interface DriveFilesResponse {
  files: DriveFile[];
  next_page_token?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  token_type: string;
}

export interface ImportFileResponse {
  id: string;
  filename: string;
  status: string;
  message: string;
}

// Token storage keys
const TOKEN_KEY = 'google_drive_token';
const REFRESH_TOKEN_KEY = 'google_drive_refresh_token';

export const googleDriveApi = {
  /**
   * Get stored access token
   */
  getStoredToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return sessionStorage.getItem(TOKEN_KEY);
  },

  /**
   * Store tokens in session storage
   */
  storeTokens: (tokens: TokenResponse): void => {
    if (typeof window === 'undefined') return;
    sessionStorage.setItem(TOKEN_KEY, tokens.access_token);
    if (tokens.refresh_token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    }
  },

  /**
   * Clear stored tokens
   */
  clearTokens: (): void => {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  /**
   * Check if user is connected to Google Drive
   */
  isConnected: (): boolean => {
    return !!googleDriveApi.getStoredToken();
  },

  /**
   * Get OAuth authorization URL
   */
  getAuthUrl: async (): Promise<string> => {
    const response = await apiClient.get<{ auth_url: string }>(
      '/api/v1/integrations/google-drive/auth-url'
    );
    return response.auth_url;
  },

  /**
   * Exchange authorization code for tokens
   */
  exchangeToken: async (code: string): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>(
      '/api/v1/integrations/google-drive/token',
      { code }
    );
    googleDriveApi.storeTokens(response);
    return response;
  },

  /**
   * Refresh access token using refresh token
   */
  refreshToken: async (): Promise<TokenResponse | null> => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!refreshToken) return null;

    try {
      const response = await apiClient.post<TokenResponse>(
        '/api/v1/integrations/google-drive/refresh-token',
        { refresh_token: refreshToken }
      );
      googleDriveApi.storeTokens(response);
      return response;
    } catch {
      googleDriveApi.clearTokens();
      return null;
    }
  },

  /**
   * List files from Google Drive
   */
  listFiles: async (
    folderId?: string,
    pageToken?: string,
    pageSize: number = 20
  ): Promise<DriveFilesResponse> => {
    const token = googleDriveApi.getStoredToken();
    if (!token) {
      throw new Error('Not connected to Google Drive');
    }

    const params = new URLSearchParams();
    params.set('access_token', token);
    if (folderId) params.set('folder_id', folderId);
    if (pageToken) params.set('page_token', pageToken);
    params.set('page_size', String(pageSize));

    try {
      return await apiClient.get<DriveFilesResponse>(
        `/api/v1/integrations/google-drive/files?${params.toString()}`
      );
    } catch (error: unknown) {
      // Try to refresh token on 401
      if (error instanceof Error && error.message.includes('401')) {
        const refreshed = await googleDriveApi.refreshToken();
        if (refreshed) {
          params.set('access_token', refreshed.access_token);
          return await apiClient.get<DriveFilesResponse>(
            `/api/v1/integrations/google-drive/files?${params.toString()}`
          );
        }
      }
      throw error;
    }
  },

  /**
   * Import a file from Google Drive to a channel
   */
  importFile: async (
    channelId: string,
    fileId: string
  ): Promise<ImportFileResponse> => {
    const token = googleDriveApi.getStoredToken();
    if (!token) {
      throw new Error('Not connected to Google Drive');
    }

    return await apiClient.post<ImportFileResponse>(
      `/api/v1/integrations/google-drive/import/${channelId}`,
      {
        file_id: fileId,
        access_token: token,
      }
    );
  },

  /**
   * Open OAuth popup and handle callback
   */
  connect: async (): Promise<boolean> => {
    try {
      const authUrl = await googleDriveApi.getAuthUrl();

      return new Promise((resolve) => {
        const width = 600;
        const height = 700;
        const left = window.screenX + (window.outerWidth - width) / 2;
        const top = window.screenY + (window.outerHeight - height) / 2;

        const popup = window.open(
          authUrl,
          'google-drive-auth',
          `width=${width},height=${height},left=${left},top=${top}`
        );

        if (!popup) {
          resolve(false);
          return;
        }

        // Listen for callback message
        const handleMessage = async (event: MessageEvent) => {
          if (event.origin !== window.location.origin) return;

          if (event.data?.type === 'google-drive-callback') {
            window.removeEventListener('message', handleMessage);

            const { code, error } = event.data;

            if (error || !code) {
              resolve(false);
              return;
            }

            try {
              await googleDriveApi.exchangeToken(code);
              resolve(true);
            } catch {
              resolve(false);
            }
          }
        };

        window.addEventListener('message', handleMessage);

        // Check if popup was closed without completing auth
        const checkClosed = setInterval(() => {
          if (popup.closed) {
            clearInterval(checkClosed);
            window.removeEventListener('message', handleMessage);
            resolve(googleDriveApi.isConnected());
          }
        }, 500);
      });
    } catch {
      return false;
    }
  },

  /**
   * Disconnect from Google Drive
   */
  disconnect: (): void => {
    googleDriveApi.clearTokens();
  },
};

export default googleDriveApi;
