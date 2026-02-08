-- Migration: 015_fix_experiment_type_validation.sql
-- Fix FIX-08 experiment_type from 'validation' to 'rollback_test'

UPDATE experiments 
SET experiment_type = 'rollback_test' 
WHERE name LIKE '%FIX-08%' 
  OR name LIKE '%Rollback Capability Test%'
  AND experiment_type = 'validation';
