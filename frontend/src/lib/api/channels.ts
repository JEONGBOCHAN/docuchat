import apiClient from './client';

// URL-safe encoding for channel IDs (replaces / with ~)
// Used because Azure Container Apps decodes %2F before reaching Next.js
export const encodeChannelIdForUrl = (id: string): string => id.replace(/\//g, '~');
export const decodeChannelIdFromUrl = (urlId: string): string => urlId.replace(/~/g, '/');

export interface Channel {
  id: string;
  name: string;
  description?: string;
  file_count: number;
  created_at: string;
  is_favorited?: boolean;
}

export interface ChannelList {
  channels: Channel[];
  total: number;
}

export interface CreateChannelRequest {
  name: string;
  description?: string;
}

export interface UpdateChannelRequest {
  name?: string;
  description?: string;
}

export const channelsApi = {
  list: (params?: { limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));
    const query = searchParams.toString();
    return apiClient.get<ChannelList>(`/api/v1/channels${query ? `?${query}` : ''}`);
  },

  get: (channelId: string) => {
    const decodedId = decodeURIComponent(channelId);
    return apiClient.get<Channel>(`/api/v1/channels/${encodeURIComponent(decodedId)}`);
  },

  create: (data: CreateChannelRequest) => {
    return apiClient.post<Channel>('/api/v1/channels', data);
  },

  update: (channelId: string, data: UpdateChannelRequest) => {
    const decodedId = decodeURIComponent(channelId);
    return apiClient.put<Channel>(`/api/v1/channels/${encodeURIComponent(decodedId)}`, data);
  },

  delete: (channelId: string) => {
    const decodedId = decodeURIComponent(channelId);
    return apiClient.delete<void>(`/api/v1/channels/${encodeURIComponent(decodedId)}`);
  },
};

export default channelsApi;
