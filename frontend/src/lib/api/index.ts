export { apiClient, ApiClientError } from './client';
export type { ApiError } from './client';

// Common types
export type { Source, ChatSource, GroundingSource } from './types';

export { channelsApi } from './channels';
export type { Channel, ChannelList, CreateChannelRequest, UpdateChannelRequest } from './channels';

export { chatApi } from './chat';
export type { ChatResponse, ChatMessage, SummarizeRequest, SummarizeResponse, StreamCallbacks, StreamOptions, StreamController } from './chat';

export { documentsApi } from './documents';
export type { Document, DocumentList, DocumentUploadResponse, UploadStatus } from './documents';

export { notesApi } from './notes';
export type { Note, NoteList, CreateNoteRequest, UpdateNoteRequest } from './notes';
