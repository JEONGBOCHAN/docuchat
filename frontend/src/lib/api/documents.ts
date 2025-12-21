import apiClient from './client';

export type UploadStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface Document {
  id: string;
  filename: string;
  file_size: number;
  content_type: string;
  status: UploadStatus;
  channel_id: string;
  created_at: string;
  error_message?: string;
}

export interface DocumentList {
  documents: Document[];
  total: number;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  status: UploadStatus;
  message: string;
}

export const documentsApi = {
  list: (channelId: string) => {
    return apiClient.get<DocumentList>(`/api/v1/documents?channel_id=${channelId}`);
  },

  upload: (channelId: string, file: File) => {
    return apiClient.upload<DocumentUploadResponse>(
      `/api/v1/documents?channel_id=${channelId}`,
      file
    );
  },

  uploadFromUrl: (channelId: string, url: string) => {
    return apiClient.post<DocumentUploadResponse>(
      `/api/v1/documents/url?channel_id=${channelId}`,
      { url }
    );
  },

  getStatus: (documentId: string) => {
    return apiClient.get<{ id: string; done: boolean; error?: string }>(
      `/api/v1/documents/${documentId}/status`
    );
  },

  delete: (documentId: string) => {
    return apiClient.delete<void>(`/api/v1/documents/${documentId}`);
  },
};

export default documentsApi;
