'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import MarkdownEditor from './MarkdownEditor';
import MarkdownPreview from './MarkdownPreview';
import type { Note, CreateNoteRequest, UpdateNoteRequest } from '@/lib/api/notes';

interface NoteEditorProps {
  note: Note | null;
  isNew?: boolean;
  onSave: (data: CreateNoteRequest | UpdateNoteRequest) => Promise<void>;
  onCancel?: () => void;
  autoSaveDelay?: number; // ms, 0 to disable
}

type ViewMode = 'edit' | 'preview' | 'split';

export default function NoteEditor({
  note,
  isNew = false,
  onSave,
  onCancel,
  autoSaveDelay = 2000,
}: NoteEditorProps) {
  const [title, setTitle] = useState(note?.title || '');
  const [content, setContent] = useState(note?.content || '');
  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const autoSaveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const initialTitleRef = useRef(note?.title || '');
  const initialContentRef = useRef(note?.content || '');

  // Reset when note changes
  useEffect(() => {
    setTitle(note?.title || '');
    setContent(note?.content || '');
    initialTitleRef.current = note?.title || '';
    initialContentRef.current = note?.content || '';
    setHasChanges(false);
    setError(null);
  }, [note?.id, note?.title, note?.content]);

  // Track changes
  useEffect(() => {
    const titleChanged = title !== initialTitleRef.current;
    const contentChanged = content !== initialContentRef.current;
    setHasChanges(titleChanged || contentChanged);
  }, [title, content]);

  // Auto-save logic
  const performSave = useCallback(async () => {
    if (isNew && (!title.trim() || !content.trim())) {
      return; // Don't auto-save empty new notes
    }

    if (!hasChanges) return;

    setIsSaving(true);
    setError(null);

    try {
      if (isNew) {
        // New notes created directly via NoteEditor have no sources.
        // Sources are only populated when saving a chat response as a note
        // (via handleSaveAsNote in page.tsx), which preserves the AI's citations.
        await onSave({
          title: title.trim(),
          content: content.trim(),
          sources: [],
        } as CreateNoteRequest);
      } else {
        const updates: UpdateNoteRequest = {};
        if (title !== initialTitleRef.current) updates.title = title.trim();
        if (content !== initialContentRef.current) updates.content = content.trim();

        if (Object.keys(updates).length > 0) {
          await onSave(updates);
        }
      }

      initialTitleRef.current = title;
      initialContentRef.current = content;
      setHasChanges(false);
      setLastSaved(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  }, [title, content, isNew, hasChanges, onSave]);

  // Setup auto-save
  useEffect(() => {
    if (autoSaveDelay <= 0 || !hasChanges) return;

    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }

    autoSaveTimerRef.current = setTimeout(() => {
      if (!isNew || (title.trim() && content.trim())) {
        performSave();
      }
    }, autoSaveDelay);

    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [title, content, autoSaveDelay, hasChanges, isNew, performSave]);

  // Manual save with keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        performSave();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [performSave]);

  const formatLastSaved = () => {
    if (!lastSaved) return null;
    return lastSaved.toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-3 flex-1">
          {onCancel && (
            <button
              onClick={onCancel}
              className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <svg
                className="w-5 h-5 text-gray-500 dark:text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
          )}
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Note title..."
            className="flex-1 text-lg font-semibold text-gray-900 dark:text-white bg-transparent border-none focus:outline-none placeholder-gray-400 dark:placeholder-gray-500"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Save Status */}
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            {isSaving && (
              <span className="flex items-center gap-1">
                <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Saving...
              </span>
            )}
            {!isSaving && hasChanges && (
              <span className="text-amber-500">Unsaved</span>
            )}
            {!isSaving && !hasChanges && lastSaved && (
              <span>Saved at {formatLastSaved()}</span>
            )}
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-md p-0.5">
            <button
              onClick={() => setViewMode('edit')}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                viewMode === 'edit'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              Edit
            </button>
            <button
              onClick={() => setViewMode('split')}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                viewMode === 'split'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              Split
            </button>
            <button
              onClick={() => setViewMode('preview')}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                viewMode === 'preview'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              Preview
            </button>
          </div>

          {/* Manual Save Button */}
          <button
            onClick={performSave}
            disabled={isSaving || !hasChanges}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Save
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="px-3 py-2 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {(viewMode === 'edit' || viewMode === 'split') && (
          <div className={`${viewMode === 'split' ? 'w-1/2 border-r border-gray-200 dark:border-gray-800' : 'w-full'}`}>
            <MarkdownEditor
              value={content}
              onChange={setContent}
              placeholder="Write your note in Markdown..."
            />
          </div>
        )}
        {(viewMode === 'preview' || viewMode === 'split') && (
          <div className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} bg-gray-50 dark:bg-gray-900/50`}>
            <MarkdownPreview content={content} />
          </div>
        )}
      </div>
    </div>
  );
}
