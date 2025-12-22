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
  done: boolean;
}

export const documentsApi = {
  list: (channelId: string) => {
    const decodedChannelId = decodeURIComponent(channelId);
    return apiClient.get<DocumentList>(`/api/v1/documents?channel_id=${encodeURIComponent(decodedChannelId)}`);
  },

  upload: (channelId: string, file: File) => {
    const decodedChannelId = decodeURIComponent(channelId);
    return apiClient.upload<DocumentUploadResponse>(
      `/api/v1/documents?channel_id=${encodeURIComponent(decodedChannelId)}`,
      file
    );
  },

  uploadFromUrl: (channelId: string, url: string) => {
    const decodedChannelId = decodeURIComponent(channelId);
    return apiClient.post<DocumentUploadResponse>(
      `/api/v1/documents/url?channel_id=${encodeURIComponent(decodedChannelId)}`,
      { url }
    );
  },

  getStatus: (documentId: string) => {
    const decodedId = decodeURIComponent(documentId);
    return apiClient.get<{ id: string; done: boolean; error?: string }>(
      `/api/v1/documents/${encodeURIComponent(decodedId)}/status`
    );
  },

  delete: (documentId: string) => {
    const decodedId = decodeURIComponent(documentId);
    return apiClient.delete<void>(`/api/v1/documents/${encodeURIComponent(decodedId)}`);
  },
};

export default documentsApi;
