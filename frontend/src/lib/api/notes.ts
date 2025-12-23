import apiClient from './client';
import type { GroundingSource } from './types';

export type { GroundingSource };

/**
 * Note entity - represents a user note in a channel.
 *
 * Note: `id` is a number (database auto-increment ID), unlike Channel/Document
 * which use string UUIDs. This is intentional as notes are stored in our DB
 * while channels/documents use external Gemini store IDs.
 */
export interface Note {
  /** Database auto-increment ID (number, not UUID) */
  id: number;
  /** Parent channel's Gemini store ID */
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
    const decodedChannelId = decodeURIComponent(channelId);
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', decodedChannelId);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));
    return apiClient.get<NoteList>(`/api/v1/notes?${searchParams.toString()}`);
  },

  get: (channelId: string, noteId: number) => {
    const decodedChannelId = decodeURIComponent(channelId);
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', decodedChannelId);
    return apiClient.get<Note>(`/api/v1/notes/${noteId}?${searchParams.toString()}`);
  },

  create: (channelId: string, data: CreateNoteRequest) => {
    const decodedChannelId = decodeURIComponent(channelId);
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', decodedChannelId);
    return apiClient.post<Note>(`/api/v1/notes?${searchParams.toString()}`, data);
  },

  update: (channelId: string, noteId: number, data: UpdateNoteRequest) => {
    const decodedChannelId = decodeURIComponent(channelId);
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', decodedChannelId);
    return apiClient.put<Note>(`/api/v1/notes/${noteId}?${searchParams.toString()}`, data);
  },

  delete: (channelId: string, noteId: number) => {
    const decodedChannelId = decodeURIComponent(channelId);
    const searchParams = new URLSearchParams();
    searchParams.set('channel_id', decodedChannelId);
    return apiClient.delete<void>(`/api/v1/notes/${noteId}?${searchParams.toString()}`);
  },
};

export default notesApi;
