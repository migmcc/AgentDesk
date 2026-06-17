"""Conflict guard — prevent tasks/models from working in incompatible zones.

Placeholder for Run D. The DB-level UNIQUE(project_id, file_path) constraint in the storage layer
already provides the core per-file locking primitive; this module will add the rule table
(allow / warn / block) on top of it.
"""
