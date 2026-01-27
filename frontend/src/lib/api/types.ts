/**
 * Common API types for Docuchat
 */

/**
 * Source types for grounded content
 */
export type SourceType = 'document' | 'web' | 'arxiv';

/**
 * Represents a source/citation from RAG grounding
 * Used in chat responses, notes, and other grounded content
 */
export interface Source {
  source: string;
  content: string;
  url?: string | null;
  source_type?: SourceType;
}

// Type aliases for backward compatibility
export type ChatSource = Source;
export type GroundingSource = Source;
