import apiClient from './client';
import type { GroundingSource } from './types';

export type { GroundingSource };

export interface Note {
  id: number;
  channel_id: string;
  title: string;
  content: string;
  sources: GroundingSource[];
  created_at: string;
  updated_at: string;
}

export interface NoteList {
  notes: Note[];
  total: number;
}

export interface CreateNoteRequest {
  title: string;
  content: string;
  sources?: GroundingSource[];
}

export interface UpdateNoteRequest {
  title?: string;
  content?: string;
}

export const notesApi = {
  list: (channelId: string, params?: { limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', channelId);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));
    return apiClient.get<NoteList>(`/api/v1/notes?${searchParams.toString()}`);
  },

  get: (channelId: string, noteId: number) => {
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', channelId);
    return apiClient.get<Note>(`/api/v1/notes/${noteId}?${searchParams.toString()}`);
  },

  create: (channelId: string, data: CreateNoteRequest) => {
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', channelId);
    return apiClient.post<Note>(`/api/v1/notes?${searchParams.toString()}`, data);
  },

  update: (channelId: string, noteId: number, data: UpdateNoteRequest) => {
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', channelId);
    return apiClient.put<Note>(`/api/v1/notes/${noteId}?${searchParams.toString()}`, data);
  },

  delete: (channelId: string, noteId: number) => {
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', channelId);
    return apiClient.delete<void>(`/api/v1/notes/${noteId}?${searchParams.toString()}`);
  },
};

export default notesApi;
