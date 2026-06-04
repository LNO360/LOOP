"""Telegram notifications for pending proposed actions (send-only; Hermes owns bot polling)."""
import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def _allowed_chat_ids() -> list[str]:
    raw = (settings.telegram_allowed_users or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _format_proposed_action_message(
    action_id: str,
    action_type: str,
    payload: dict,
) -> str:
    lines = [
        "⏳ <b>Approval needed</b>",
        f"Type: <code>{action_type}</code>",
        f"ID: <code>{action_id}</code>",
    ]
    if action_type == "gmail_send":
        lines.append(f"To: {payload.get('to', '?')}")
        lines.append(f"Subject: {payload.get('subject', '?')}")
    elif action_type == "gcal_create_event":
        lines.append(f"Event: {payload.get('title', '?')}")
        lines.append(f"When: {payload.get('start_iso', '?')} → {payload.get('end_iso', '?')}")
    elif action_type == "gcal_create_event_with_meet":
        lines.append(f"Event: {payload.get('title', '?')} + Meet")
        lines.append(f"When: {payload.get('start_iso', '?')} → {payload.get('end_iso', '?')}")
    elif action_type == "gcal_update_event":
        lines.append(f"Event ID: {payload.get('event_id', '?')}")
        lines.append(f"Changes: {list(payload.get('patch', {}).keys())}")
    elif action_type == "gcal_delete_event":
        lines.append(f"Event ID: {payload.get('event_id', '?')} ⚠️ PERMANENT DELETE")
    elif action_type == "gmail_add_label":
        lines.append(f"Message: {payload.get('message_id', '?')}")
        lines.append(f"Labels: {payload.get('labels', payload.get('label_ids', '?'))}")
    elif action_type == "gmail_archive":
        lines.append(f"Message: {payload.get('message_id', '?')}")
    elif action_type in ("gsheets_append_row", "gsheets_update_cells"):
        lines.append(f"Sheet: {payload.get('spreadsheet_id', '?')}")
        if action_type == "gsheets_append_row":
            lines.append(f"Tab: {payload.get('sheet_name', '?')}")
            lines.append(f"Values: {str(payload.get('values', '?'))[:80]}")
        else:
            lines.append(f"Range: {payload.get('range_a1', '?')}")
            lines.append(f"Rows: {payload.get('rows', '?')}")
    elif action_type == "gdrive_upload_file":
        lines.append(f"File: {payload.get('filename', '?')}")
        lines.append(f"Type: {payload.get('mime_type', '?')}")
        lines.append(f"Size: ~{payload.get('size_kb', '?')}KB")
    elif action_type == "github_create_issue":
        lines.append(f"Repo: {payload.get('repo', '?')}")
        lines.append(f"Title: {payload.get('title', '?')}")
    elif action_type == "github_add_issue_comment":
        lines.append(f"Repo: {payload.get('repo', '?')}#{payload.get('issue_number', '?')}")
        lines.append(f"Preview: {str(payload.get('body_preview', '?'))[:80]}")
    elif action_type == "finance_create_transaction":
        amt = payload.get('amount_cents', 0)
        cur = payload.get('currency', 'INR')
        lines.append(f"Direction: {payload.get('direction', '?')}")
        lines.append(f"Amount: {amt/100:.2f} {cur}")
        lines.append(f"Date: {payload.get('occurred_on', '?')}")
        lines.append(f"Desc: {payload.get('description', '?')[:80]}")
    elif action_type == "finance_update_transaction":
        lines.append(f"TX ID: {str(payload.get('transaction_id', '?'))[:8]}…")
        lines.append(f"Fields: {payload.get('fields', list(payload.get('patch', {}).keys()))}")
    elif action_type == "finance_delete_transaction":
        lines.append(f"TX ID: {str(payload.get('transaction_id', '?'))[:8]}… ⚠️ PERMANENT DELETE")
    elif action_type == "finance_create_invoice":
        amt = payload.get('amount_cents', 0)
        cur = payload.get('currency', 'INR')
        lines.append(f"Customer: {payload.get('customer_name', '?')}")
        lines.append(f"Amount: {amt/100:.2f} {cur}")
        lines.append(f"Due: {payload.get('due_on', 'TBD')}")
    elif action_type == "finance_mark_invoice_paid":
        lines.append(f"Invoice ID: {str(payload.get('invoice_id', '?'))[:8]}…")
        lines.append(f"Paid on: {payload.get('paid_on', 'today')}")
    lines.extend([
        "",
        "Reply here to approve or reject:",
        f"• <code>approve {action_id}</code>",
        f"• <code>reject {action_id}</code>",
        "",
        "(Or use AI Work → Agents → Actions in the app.)",
    ])
    return "\n".join(lines)


async def notify_proposed_action_created(
    *,
    action_id: str,
    action_type: str,
    payload: dict,
) -> None:
    """Push a Telegram message to allowed users. Never raises."""
    token = (settings.telegram_bot_token or "").strip()
    chat_ids = _allowed_chat_ids()
    if not token or not chat_ids:
        return

    text = _format_proposed_action_message(action_id, action_type, payload or {})
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    async with httpx.AsyncClient() as client:
        for chat_id in chat_ids:
            try:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=10,
                )
                if resp.status_code >= 400:
                    logger.warning("Telegram notify failed for %s: %s", chat_id, resp.text[:200])
            except Exception as e:
                logger.warning("Telegram notify error for %s: %s", chat_id, e)
