'use client';

import { useReducer, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import MainLayout from '@/components/layout/MainLayout';
import { ChatContainer } from '@/components/chat';
import { DocumentUploader, DocumentList } from '@/components/documents';
import { NotesList, NoteEditor, DeleteNoteModal } from '@/components/notes';
import { channelsApi, type Channel } from '@/lib/api/channels';
import { notesApi, type Note, type CreateNoteRequest, type UpdateNoteRequest } from '@/lib/api/notes';
import type { ChatSource } from '@/lib/api/chat';

// =============================================================================
// Types
// =============================================================================

type ViewTab = 'chat' | 'notes';

interface ChannelPageState {
  // Channel data
  channel: Channel | null;
  isLoading: boolean;
  error: string | null;

  // UI state
  activeTab: ViewTab;
  showDocuments: boolean;
  refreshTrigger: number;

  // Notes state
  notes: Note[];
  isLoadingNotes: boolean;
  selectedNote: Note | null;
  isCreatingNote: boolean;
  noteToDelete: Note | null;
}

type ChannelPageAction =
  | { type: 'FETCH_START' }
  | { type: 'FETCH_SUCCESS'; channel: Channel; notes: Note[] }
  | { type: 'FETCH_ERROR'; error: string }
  | { type: 'SET_CHANNEL'; channel: Channel }
  | { type: 'SET_ACTIVE_TAB'; tab: ViewTab }
  | { type: 'TOGGLE_DOCUMENTS' }
  | { type: 'TRIGGER_REFRESH' }
  | { type: 'SET_NOTES'; notes: Note[] }
  | { type: 'ADD_NOTE'; note: Note }
  | { type: 'UPDATE_NOTE'; note: Note }
  | { type: 'DELETE_NOTE'; noteId: number }
  | { type: 'SELECT_NOTE'; note: Note | null }
  | { type: 'START_CREATE_NOTE' }
  | { type: 'CANCEL_CREATE_NOTE' }
  | { type: 'SET_NOTE_TO_DELETE'; note: Note | null }
  | { type: 'RESET_FOR_CHANNEL_CHANGE' }
  | { type: 'SAVE_AS_NOTE_SUCCESS'; note: Note };

// =============================================================================
// Reducer
// =============================================================================

const initialState: ChannelPageState = {
  channel: null,
  isLoading: true,
  error: null,
  activeTab: 'chat',
  showDocuments: true,
  refreshTrigger: 0,
  notes: [],
  isLoadingNotes: true,
  selectedNote: null,
  isCreatingNote: false,
  noteToDelete: null,
};

function channelPageReducer(state: ChannelPageState, action: ChannelPageAction): ChannelPageState {
  switch (action.type) {
    case 'FETCH_START':
      return {
        ...state,
        isLoading: true,
        isLoadingNotes: true,
        error: null,
      };

    case 'FETCH_SUCCESS':
      return {
        ...state,
        channel: action.channel,
        notes: action.notes,
        isLoading: false,
        isLoadingNotes: false,
        error: null,
      };

    case 'FETCH_ERROR':
      return {
        ...state,
        channel: null,
        notes: [],
        isLoading: false,
        isLoadingNotes: false,
        error: action.error,
      };

    case 'SET_CHANNEL':
      return {
        ...state,
        channel: action.channel,
      };

    case 'SET_ACTIVE_TAB':
      return {
        ...state,
        activeTab: action.tab,
      };

    case 'TOGGLE_DOCUMENTS':
      return {
        ...state,
        showDocuments: !state.showDocuments,
      };

    case 'TRIGGER_REFRESH':
      return {
        ...state,
        refreshTrigger: state.refreshTrigger + 1,
      };

    case 'SET_NOTES':
      return {
        ...state,
        notes: action.notes,
      };

    case 'ADD_NOTE':
      return {
        ...state,
        notes: [action.note, ...state.notes],
        selectedNote: action.note,
        isCreatingNote: false,
      };

    case 'UPDATE_NOTE':
      return {
        ...state,
        notes: state.notes.map((n) => (n.id === action.note.id ? action.note : n)),
        selectedNote: action.note,
      };

    case 'DELETE_NOTE': {
      const newNotes = state.notes.filter((n) => n.id !== action.noteId);
      const wasSelected = state.selectedNote?.id === action.noteId;
      return {
        ...state,
        notes: newNotes,
        selectedNote: wasSelected ? null : state.selectedNote,
        isCreatingNote: wasSelected ? false : state.isCreatingNote,
        noteToDelete: null,
      };
    }

    case 'SELECT_NOTE':
      return {
        ...state,
        selectedNote: action.note,
        isCreatingNote: false,
      };

    case 'START_CREATE_NOTE':
      return {
        ...state,
        selectedNote: null,
        isCreatingNote: true,
      };

    case 'CANCEL_CREATE_NOTE':
      return {
        ...state,
        isCreatingNote: false,
        selectedNote: state.notes.length > 0 ? state.notes[0] : null,
      };

    case 'SET_NOTE_TO_DELETE':
      return {
        ...state,
        noteToDelete: action.note,
      };

    case 'RESET_FOR_CHANNEL_CHANGE':
      return {
        ...initialState,
        activeTab: state.activeTab,
        showDocuments: state.showDocuments,
      };

    case 'SAVE_AS_NOTE_SUCCESS':
      return {
        ...state,
        notes: [action.note, ...state.notes],
        selectedNote: action.note,
        isCreatingNote: false,
        activeTab: 'notes',
      };

    default:
      return state;
  }
}

// =============================================================================
// Component
// =============================================================================

export default function ChannelDetailPage() {
  const params = useParams();
  const router = useRouter();
  const channelId = params.id as string;

  const [state, dispatch] = useReducer(channelPageReducer, initialState);
  const requestIdRef = useRef(0);

  const {
    channel,
    isLoading,
    error,
    activeTab,
    showDocuments,
    refreshTrigger,
    notes,
    isLoadingNotes,
    selectedNote,
    isCreatingNote,
    noteToDelete,
  } = state;

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const currentRequestId = ++requestIdRef.current;

    async function fetchData() {
      dispatch({ type: 'FETCH_START' });

      try {
        const [channelData, notesData] = await Promise.all([
          channelsApi.get(channelId),
          notesApi.list(channelId),
        ]);

        if (currentRequestId !== requestIdRef.current) return;

        dispatch({
          type: 'FETCH_SUCCESS',
          channel: channelData,
          notes: notesData.notes,
        });
      } catch (err) {
        if (currentRequestId !== requestIdRef.current) return;

        dispatch({
          type: 'FETCH_ERROR',
          error: err instanceof Error ? err.message : 'Failed to load channel',
        });
      }
    }

    dispatch({ type: 'RESET_FOR_CHANNEL_CHANGE' });
    fetchData();
  }, [channelId]);

  // ---------------------------------------------------------------------------
  // Refresh Handlers
  // ---------------------------------------------------------------------------

  const refreshChannel = useCallback(async () => {
    try {
      const data = await channelsApi.get(channelId);
      dispatch({ type: 'SET_CHANNEL', channel: data });
    } catch (err) {
      console.error('Failed to refresh channel:', err);
    }
  }, [channelId]);

  const handleUploadComplete = useCallback(() => {
    dispatch({ type: 'TRIGGER_REFRESH' });
    refreshChannel();
  }, [refreshChannel]);

  // ---------------------------------------------------------------------------
  // Note Handlers
  // ---------------------------------------------------------------------------

  /**
   * Save chat response as a note.
   * ChatSource and GroundingSource are identical types (both alias of Source interface),
   * so ChatSource[] can be directly passed to notesApi.create() which expects GroundingSource[].
   */
  const handleSaveAsNote = useCallback(async (content: string, sources: ChatSource[]) => {
    try {
      const title = content.slice(0, 50).replace(/[#*`\n]/g, '').trim() || 'New Note';
      const newNote = await notesApi.create(channelId, { title, content, sources });
      dispatch({ type: 'SAVE_AS_NOTE_SUCCESS', note: newNote });
    } catch (err) {
      console.error('Failed to save as note:', err);
    }
  }, [channelId]);

  const handleCreateNote = useCallback(() => {
    dispatch({ type: 'START_CREATE_NOTE' });
  }, []);

  const handleSelectNote = useCallback((note: Note) => {
    dispatch({ type: 'SELECT_NOTE', note });
  }, []);

  const handleSaveNote = useCallback(async (data: CreateNoteRequest | UpdateNoteRequest) => {
    if (isCreatingNote) {
      const newNote = await notesApi.create(channelId, data as CreateNoteRequest);
      dispatch({ type: 'ADD_NOTE', note: newNote });
    } else if (selectedNote) {
      const updatedNote = await notesApi.update(channelId, selectedNote.id, data as UpdateNoteRequest);
      dispatch({ type: 'UPDATE_NOTE', note: updatedNote });
    }
  }, [channelId, isCreatingNote, selectedNote]);

  const handleDeleteNote = useCallback(async () => {
    if (!noteToDelete) return;
    await notesApi.delete(channelId, noteToDelete.id);
    dispatch({ type: 'DELETE_NOTE', noteId: noteToDelete.id });
  }, [channelId, noteToDelete]);

  const handleCancelCreate = useCallback(() => {
    dispatch({ type: 'CANCEL_CREATE_NOTE' });
  }, []);

  // ---------------------------------------------------------------------------
  // Render: Loading State
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <MainLayout showSidebar={false}>
        <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
          <div className="flex flex-col items-center gap-3">
            <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading channel...</p>
          </div>
        </div>
      </MainLayout>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Error State
  // ---------------------------------------------------------------------------

  if (error || !channel) {
    return (
      <MainLayout showSidebar={false}>
        <div className="flex flex-col items-center justify-center h-[calc(100vh-8rem)]">
          <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Channel not found</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            {error || 'The channel you are looking for does not exist.'}
          </p>
          <button
            onClick={() => router.push('/channels')}
            className="px-4 py-2 bg-blue-600 text-sm text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Back to channels
          </button>
        </div>
      </MainLayout>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Main Content
  // ---------------------------------------------------------------------------

  return (
    <MainLayout showSidebar={false}>
      <div className="h-[calc(100vh-5rem)] flex flex-col">
        {/* Channel Header */}
        <div className="flex items-center gap-4 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <button
            onClick={() => router.push('/channels')}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white truncate">{channel.name}</h1>
            {channel.description && (
              <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{channel.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Tab Switcher */}
            <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-md p-0.5 mr-2">
              <button
                onClick={() => dispatch({ type: 'SET_ACTIVE_TAB', tab: 'chat' })}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  activeTab === 'chat'
                    ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                Chat
              </button>
              <button
                onClick={() => dispatch({ type: 'SET_ACTIVE_TAB', tab: 'notes' })}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                  activeTab === 'notes'
                    ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                Notes
                {notes.length > 0 && (
                  <span className="text-xs bg-gray-200 dark:bg-gray-600 px-1.5 rounded-full">{notes.length}</span>
                )}
              </button>
            </div>

            <span className="text-xs text-gray-400 dark:text-gray-500">{channel.file_count} files</span>
            <button
              onClick={() => dispatch({ type: 'TOGGLE_DOCUMENTS' })}
              className={`p-2 rounded-md transition-colors ${
                showDocuments
                  ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'
              }`}
              title={showDocuments ? 'Hide documents' : 'Show documents'}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar - Documents (for chat) or Notes List (for notes) */}
          {activeTab === 'chat' ? (
            showDocuments && (
              <div className="w-80 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950 overflow-y-auto">
                <div className="p-4 space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Add Documents</h3>
                    <DocumentUploader channelId={channelId} onUploadComplete={handleUploadComplete} />
                  </div>
                  <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
                    <DocumentList channelId={channelId} refreshTrigger={refreshTrigger} />
                  </div>
                </div>
              </div>
            )
          ) : (
            <div className="w-64 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
              <NotesList
                notes={notes}
                selectedNoteId={selectedNote?.id ?? null}
                onSelectNote={handleSelectNote}
                onCreateNote={handleCreateNote}
                onDeleteNote={(note) => dispatch({ type: 'SET_NOTE_TO_DELETE', note })}
                isLoading={isLoadingNotes}
              />
            </div>
          )}

          {/* Main Area - Chat or Note Editor */}
          <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 overflow-hidden">
            {activeTab === 'chat' ? (
              <ChatContainer channelId={channelId} onSaveAsNote={handleSaveAsNote} />
            ) : (
              <>
                {isCreatingNote ? (
                  <NoteEditor note={null} isNew={true} onSave={handleSaveNote} onCancel={handleCancelCreate} autoSaveDelay={0} />
                ) : selectedNote ? (
                  <NoteEditor key={selectedNote.id} note={selectedNote} onSave={handleSaveNote} autoSaveDelay={2000} />
                ) : (
                  <div className="h-full flex items-center justify-center bg-gray-50 dark:bg-gray-950">
                    <div className="text-center">
                      <svg className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">No note selected</h3>
                      <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Select a note from the sidebar or create a new one</p>
                      <button
                        onClick={handleCreateNote}
                        className="mt-4 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors inline-flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        New Note
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Delete Note Modal */}
      <DeleteNoteModal
        isOpen={!!noteToDelete}
        note={noteToDelete}
        onClose={() => dispatch({ type: 'SET_NOTE_TO_DELETE', note: null })}
        onConfirm={handleDeleteNote}
      />
    </MainLayout>
  );
}
