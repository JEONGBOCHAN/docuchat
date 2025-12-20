/**
 * Common API types for Chalssak
 */

/**
 * Represents a source/citation from RAG grounding
 * Used in chat responses, notes, and other grounded content
 */
export interface Source {
  source: string;
  content: string;
}

// Type aliases for backward compatibility
export type ChatSource = Source;
export type GroundingSource = Source;
