# Researcher — Example User Agent Skill

Conducts thorough web research on a given topic and synthesises findings.

## When to use

"Research [topic] and summarise" or "Investigate [question] and save key facts to memory"

## Steps

1. Search for recent information: `web_search` with the topic as query
2. Read top 3–5 pages: `web_fetch_page` for each URL
3. Synthesise findings into a structured report with sources
4. If instructed, save key facts: `lno_upsert_workspace_memory`

## Output format

- **Summary** (2–3 sentences)
- **Key findings** (bullet list)
- **Sources** (URLs)
- **Saved to memory** (if applicable)

## Customising

Copy this file to `apps/user-agent-skills/<your-skill-name>/SKILL.md`
and adapt the steps and output format for your use case.
