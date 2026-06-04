# Daily Digest — Example Hermes Skill

Sends a morning summary of tasks due today, overdue items, and workspace activity.

## When to use

Trigger manually ("give me the daily digest") or schedule as a cron job:
> "Every morning at 8am, run the daily digest"

## Steps

1. Fetch today's tasks: `lno_list_tasks` with `due_today=true`
2. Fetch overdue items: `lno_list_overdue_tasks`
3. Fetch workspace snapshot: `lno_get_workspace_snapshot`
4. Format as a concise summary (< 400 chars for Telegram)
5. Send via `lno_send_channel_message` to your preferred channel

## Example output

> 📋 **Daily Digest — Jun 4**
> ✅ 3 tasks due today
> ⚠️ 2 overdue (review needed)
> 💬 5 new channel messages

## Customising

- Change the target channel by passing a different `channel_id`
- Add finance summary using the finance MCP tools
- Filter by assignee for personalised digests
