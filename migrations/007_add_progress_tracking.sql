-- Migration 007: Add progress tracking columns
-- Adds columns for live progress tracking in code analysis runs and log crawler

-- Add progress tracking to code_analysis_runs
ALTER TABLE code_analysis_runs 
ADD COLUMN IF NOT EXISTS progress_message TEXT,
ADD COLUMN IF NOT EXISTS files_analyzed INTEGER DEFAULT 0;

-- Add progress tracking to log_crawler_state (if not already exists)
ALTER TABLE log_crawler_state 
ADD COLUMN IF NOT EXISTS progress_message TEXT;
