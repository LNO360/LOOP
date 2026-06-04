# Memory Gardener — Example Hermes Skill

Periodically reviews and prunes workspace memory to keep it accurate and relevant.

## When to use

Run weekly ("tidy up the workspace memory") or after major project changes.

## Steps

1. Retrieve all entries: `lno_get_workspace_memory`
2. Identify stale entries (outdated project status, superseded decisions, old facts)
3. For each stale entry, confirm it is no longer valid
4. Delete confirmed stale entries: `lno_delete_workspace_memory`
5. Update entries that need correction: `lno_upsert_workspace_memory`

## Guidelines

- Keep entries under 200 characters each
- Remove duplicates of information already in tasks or projects
- Preserve rationale and decisions even if the outcome changed
- Merge related entries to reduce total count
