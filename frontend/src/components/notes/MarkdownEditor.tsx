'use client';

import { useRef, useEffect, useCallback } from 'react';

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export default function MarkdownEditor({
  value,
  onChange,
  placeholder = 'Write your note in Markdown...',
  disabled = false,
}: MarkdownEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.max(textarea.scrollHeight, 300)}px`;
    }
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const textarea = e.currentTarget;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);

    // Bold: Ctrl/Cmd + B
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      const newText = selectedText
        ? `**${selectedText}**`
        : '**bold text**';
      insertText(newText, selectedText ? 0 : 2, selectedText ? 0 : 11);
      return;
    }

    // Italic: Ctrl/Cmd + I
    if ((e.ctrlKey || e.metaKey) && e.key === 'i') {
      e.preventDefault();
      const newText = selectedText
        ? `*${selectedText}*`
        : '*italic text*';
      insertText(newText, selectedText ? 0 : 1, selectedText ? 0 : 12);
      return;
    }

    // Code: Ctrl/Cmd + `
    if ((e.ctrlKey || e.metaKey) && e.key === '`') {
      e.preventDefault();
      const newText = selectedText
        ? `\`${selectedText}\``
        : '`code`';
      insertText(newText, selectedText ? 0 : 1, selectedText ? 0 : 5);
      return;
    }

    // Tab: Insert 2 spaces
    if (e.key === 'Tab') {
      e.preventDefault();
      insertText('  ', 0, 0);
      return;
    }
  };

  const insertText = (text: string, cursorOffsetStart: number, cursorOffsetEnd: number) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const newValue = value.substring(0, start) + text + value.substring(end);

    onChange(newValue);

    // Set cursor position after state update
    requestAnimationFrame(() => {
      textarea.focus();
      const newCursorPos = start + text.length - cursorOffsetEnd;
      textarea.setSelectionRange(
        start + cursorOffsetStart,
        newCursorPos
      );
    });
  };

  // Toolbar button handlers
  const insertHeading = (level: number) => {
    const prefix = '#'.repeat(level) + ' ';
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    const newValue = value.substring(0, lineStart) + prefix + value.substring(lineStart);
    onChange(newValue);

    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length);
    });
  };

  const insertLink = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);
    const linkText = selectedText || 'link text';
    const newText = `[${linkText}](url)`;

    const newValue = value.substring(0, start) + newText + value.substring(end);
    onChange(newValue);

    requestAnimationFrame(() => {
      textarea.focus();
      if (selectedText) {
        // Select "url"
        textarea.setSelectionRange(start + linkText.length + 3, start + linkText.length + 6);
      } else {
        // Select "link text"
        textarea.setSelectionRange(start + 1, start + 10);
      }
    });
  };

  const insertList = (ordered: boolean) => {
    const prefix = ordered ? '1. ' : '- ';
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    const newValue = value.substring(0, lineStart) + prefix + value.substring(lineStart);
    onChange(newValue);

    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length);
    });
  };

  const insertCodeBlock = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);
    const codeText = selectedText || 'code here';
    const newText = `\n\`\`\`\n${codeText}\n\`\`\`\n`;

    const newValue = value.substring(0, start) + newText + value.substring(end);
    onChange(newValue);

    requestAnimationFrame(() => {
      textarea.focus();
      if (!selectedText) {
        textarea.setSelectionRange(start + 5, start + 14);
      }
    });
  };

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-1 p-2 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
        <button
          type="button"
          onClick={() => insertHeading(1)}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Heading 1"
        >
          <span className="text-xs font-bold">H1</span>
        </button>
        <button
          type="button"
          onClick={() => insertHeading(2)}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Heading 2"
        >
          <span className="text-xs font-bold">H2</span>
        </button>
        <button
          type="button"
          onClick={() => insertHeading(3)}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Heading 3"
        >
          <span className="text-xs font-bold">H3</span>
        </button>

        <div className="w-px h-4 bg-gray-300 dark:bg-gray-700 mx-1" />

        <button
          type="button"
          onClick={() => {
            const textarea = textareaRef.current;
            if (textarea) {
              const start = textarea.selectionStart;
              const end = textarea.selectionEnd;
              const selectedText = value.substring(start, end);
              const newText = `**${selectedText || 'bold'}**`;
              const newValue = value.substring(0, start) + newText + value.substring(end);
              onChange(newValue);
            }
          }}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Bold (Ctrl+B)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 4h8a4 4 0 014 4 4 4 0 01-4 4H6z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 12h9a4 4 0 014 4 4 4 0 01-4 4H6z" />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => {
            const textarea = textareaRef.current;
            if (textarea) {
              const start = textarea.selectionStart;
              const end = textarea.selectionEnd;
              const selectedText = value.substring(start, end);
              const newText = `*${selectedText || 'italic'}*`;
              const newValue = value.substring(0, start) + newText + value.substring(end);
              onChange(newValue);
            }
          }}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Italic (Ctrl+I)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 4h4M8 20h4M12 4l-4 16" />
          </svg>
        </button>

        <div className="w-px h-4 bg-gray-300 dark:bg-gray-700 mx-1" />

        <button
          type="button"
          onClick={() => insertList(false)}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Bullet List"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => insertList(true)}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Numbered List"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h10M7 16h10M3 8h.01M3 12h.01M3 16h.01" />
          </svg>
        </button>

        <div className="w-px h-4 bg-gray-300 dark:bg-gray-700 mx-1" />

        <button
          type="button"
          onClick={insertLink}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Insert Link"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        </button>
        <button
          type="button"
          onClick={insertCodeBlock}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Code Block"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
        </button>
      </div>

      {/* Editor */}
      <div className="flex-1 overflow-y-auto">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full h-full min-h-[300px] p-4 resize-none bg-transparent text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none font-mono"
          spellCheck={false}
        />
      </div>
    </div>
  );
}
