'use client';

import { useMemo } from 'react';

interface MarkdownPreviewProps {
  content: string;
}

// Simple markdown parser (for basic rendering without external deps)
function parseMarkdown(text: string): string {
  if (!text) return '';

  let html = text
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

    // Code blocks (must be before other rules)
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')

    // Inline code
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

    // Headers
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')

    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

    // Italic
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')

    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')

    // Unordered lists
    .replace(/^[-*] (.*)$/gm, '<li>$1</li>')

    // Ordered lists
    .replace(/^\d+\. (.*)$/gm, '<li>$1</li>')

    // Blockquotes
    .replace(/^> (.*)$/gm, '<blockquote>$1</blockquote>')

    // Horizontal rule
    .replace(/^---$/gm, '<hr />')

    // Line breaks (double newline = paragraph)
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br />');

  // Wrap consecutive li elements in ul
  html = html.replace(/(<li>.*?<\/li>)(\s*<li>.*?<\/li>)*/g, (match) => {
    return '<ul>' + match + '</ul>';
  });

  // Wrap consecutive blockquotes
  html = html.replace(/(<blockquote>.*?<\/blockquote>)(\s*<blockquote>.*?<\/blockquote>)*/g, (match) => {
    return '<div class="blockquote-wrapper">' + match.replace(/<\/blockquote><br \/><blockquote>/g, '</blockquote><blockquote>') + '</div>';
  });

  // Wrap in paragraph if not empty
  if (html.trim()) {
    html = '<p>' + html + '</p>';
  }

  // Clean up empty paragraphs
  html = html.replace(/<p><\/p>/g, '');
  html = html.replace(/<p><br \/><\/p>/g, '');

  return html;
}

export default function MarkdownPreview({ content }: MarkdownPreviewProps) {
  const html = useMemo(() => parseMarkdown(content), [content]);

  if (!content) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 dark:text-gray-500">
        <p className="text-sm">Preview will appear here...</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div
        className="prose prose-sm dark:prose-invert max-w-none
          prose-headings:font-semibold prose-headings:text-gray-900 dark:prose-headings:text-white
          prose-h1:text-2xl prose-h1:border-b prose-h1:border-gray-200 dark:prose-h1:border-gray-700 prose-h1:pb-2 prose-h1:mb-4
          prose-h2:text-xl prose-h2:mt-6 prose-h2:mb-3
          prose-h3:text-lg prose-h3:mt-4 prose-h3:mb-2
          prose-p:text-gray-700 dark:prose-p:text-gray-300 prose-p:leading-relaxed
          prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
          prose-strong:text-gray-900 dark:prose-strong:text-white
          prose-code:text-sm prose-code:bg-gray-100 dark:prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
          prose-pre:bg-gray-900 dark:prose-pre:bg-gray-950 prose-pre:text-gray-100 prose-pre:p-4 prose-pre:rounded-lg prose-pre:overflow-x-auto
          prose-ul:list-disc prose-ul:pl-5
          prose-ol:list-decimal prose-ol:pl-5
          prose-li:text-gray-700 dark:prose-li:text-gray-300
          prose-blockquote:border-l-4 prose-blockquote:border-gray-300 dark:prose-blockquote:border-gray-600 prose-blockquote:pl-4 prose-blockquote:italic prose-blockquote:text-gray-600 dark:prose-blockquote:text-gray-400
          prose-hr:border-gray-200 dark:prose-hr:border-gray-700"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
