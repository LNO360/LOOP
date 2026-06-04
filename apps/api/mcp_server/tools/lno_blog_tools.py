"""
MCP tools for lno.co.in blog CMS.

Read tools  (execute immediately): lno_blog_list_posts, lno_blog_get_post, lno_blog_seo_audit
Write tools (execute immediately): lno_blog_create_post, lno_blog_update_post
Write tools (proposed_action):     lno_blog_publish_post, lno_blog_delete_post
"""
from typing import Optional

from mcp_server.server import mcp, agent_broadcast
from services import blog_service

# Re-export for tests
_seo_audit = blog_service.seo_audit
_extract_text = blog_service.extract_text


@mcp.tool()
async def lno_blog_list_posts(
    workspace_id: str,
    status: str = "all",
    category: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    List posts on lno.co.in.
    status: "all" | "draft" | "published"  (default: all)
    category: filter by category slug e.g. "operator" (optional)
    limit: max results, default 20, max 50
    Returns [{id, title, slug, status, category, tags, published_at, updated_at}].
    """
    if not blog_service.is_configured():
        return [blog_service.config_error()]

    await agent_broadcast(workspace_id, "lno_blog_list_posts", "running")
    data = await blog_service.list_posts(status=status, category=category, limit=limit)
    if isinstance(data, dict) and "error" in data:
        await agent_broadcast(workspace_id, "lno_blog_list_posts", "error", data["error"])
        return [data]
    await agent_broadcast(workspace_id, "lno_blog_list_posts", "done", f"{len(data)} posts")
    return data


@mcp.tool()
async def lno_blog_get_post(
    workspace_id: str,
    post_id: str,
) -> dict:
    """
    Fetch a full post by its UUID, including TipTap JSON content and all SEO fields.
    Use lno_blog_list_posts first to get a post_id.
    """
    if not blog_service.is_configured():
        return blog_service.config_error()

    await agent_broadcast(workspace_id, "lno_blog_get_post", "running")
    result = await blog_service.get_post(post_id)
    if "error" in result:
        await agent_broadcast(workspace_id, "lno_blog_get_post", "error", result["error"])
        return result
    await agent_broadcast(workspace_id, "lno_blog_get_post", "done", result.get("title", ""))
    return result


@mcp.tool()
async def lno_blog_seo_audit(
    workspace_id: str,
    post_id: str,
) -> dict:
    """
    Run an on-page SEO audit on a post.
    Returns {title_length, has_meta_description, meta_description_length, has_excerpt,
             has_tags, tag_count, has_cover_image, has_slug, estimated_word_count,
             issues: [...], score: 0-100}.
    score 80+ = good, 60-79 = needs work, <60 = poor.
    """
    if not blog_service.is_configured():
        return blog_service.config_error()

    await agent_broadcast(workspace_id, "lno_blog_seo_audit", "running")
    result = await blog_service.run_seo_audit(post_id)
    if "error" in result:
        await agent_broadcast(workspace_id, "lno_blog_seo_audit", "error", result["error"])
        return result
    await agent_broadcast(workspace_id, "lno_blog_seo_audit", "done", f"score {result['score']}/100")
    return result


@mcp.tool()
async def lno_blog_create_post(
    workspace_id: str,
    title: str,
    content: dict,
    slug: Optional[str] = None,
    excerpt: Optional[str] = None,
    category: str = "operator",
    meta_description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    cover_image_url: Optional[str] = None,
    read_time: Optional[int] = None,
    author_name: Optional[str] = None,
    author_role: Optional[str] = None,
    author_initials: Optional[str] = None,
) -> dict:
    """
    Create a new draft post on lno.co.in.
    content: TipTap JSON object e.g. {"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"Hello"}]}]}
    category: "operator" (default) | "subscriber" | "product" | "industry"
    Always creates as status=draft — use lno_blog_publish_post to go live.
    Returns full created Post record including id.
    """
    if not blog_service.is_configured():
        return blog_service.config_error()

    await agent_broadcast(workspace_id, "lno_blog_create_post", "running")
    result = await blog_service.create_post(
        title=title,
        content=content,
        slug=slug,
        excerpt=excerpt,
        category=category,
        meta_description=meta_description,
        tags=tags,
        cover_image_url=cover_image_url,
        read_time=read_time,
        author_name=author_name,
        author_role=author_role,
        author_initials=author_initials,
    )
    if isinstance(result, dict) and "error" in result:
        await agent_broadcast(workspace_id, "lno_blog_create_post", "error", str(result["error"]))
        return result
    post_id = result.get("id", "?")
    await agent_broadcast(workspace_id, "lno_blog_create_post", "done", f"created {post_id}")
    return result


@mcp.tool()
async def lno_blog_update_post(
    workspace_id: str,
    post_id: str,
    title: Optional[str] = None,
    content: Optional[dict] = None,
    slug: Optional[str] = None,
    excerpt: Optional[str] = None,
    category: Optional[str] = None,
    meta_description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    cover_image_url: Optional[str] = None,
    read_time: Optional[int] = None,
    author_name: Optional[str] = None,
    author_role: Optional[str] = None,
    author_initials: Optional[str] = None,
    featured: Optional[bool] = None,
) -> dict:
    """
    Update any fields on an existing post (draft or published).
    Only pass the fields you want to change — omitted fields are unchanged.
    Returns full updated Post record.
    """
    if not blog_service.is_configured():
        return blog_service.config_error()

    await agent_broadcast(workspace_id, "lno_blog_update_post", "running")
    result = await blog_service.update_post(
        post_id=post_id,
        title=title,
        content=content,
        slug=slug,
        excerpt=excerpt,
        category=category,
        meta_description=meta_description,
        tags=tags,
        cover_image_url=cover_image_url,
        read_time=read_time,
        author_name=author_name,
        author_role=author_role,
        author_initials=author_initials,
        featured=featured,
    )
    if isinstance(result, dict) and "error" in result:
        await agent_broadcast(workspace_id, "lno_blog_update_post", "error", str(result["error"]))
        return result
    await agent_broadcast(workspace_id, "lno_blog_update_post", "done", post_id[:8])
    return result


@mcp.tool()
async def lno_blog_publish_post(
    workspace_id: str,
    post_id: str,
) -> dict:
    """
    Queue a post for publishing on lno.co.in (requires human approval).
    Returns {"proposed": true, "action_id": "..."}.
    """
    if not blog_service.is_configured():
        return blog_service.config_error()

    await agent_broadcast(workspace_id, "lno_blog_publish_post", "running")
    result = await blog_service.propose_publish(workspace_id, post_id)
    if "error" in result:
        await agent_broadcast(workspace_id, "lno_blog_publish_post", "error", result["error"])
        return result
    await agent_broadcast(
        workspace_id,
        "lno_blog_publish_post",
        "done",
        f"queued publish for '{result.get('title', post_id)}'",
    )
    return result


@mcp.tool()
async def lno_blog_delete_post(
    workspace_id: str,
    post_id: str,
) -> dict:
    """
    Queue a post for deletion (requires human approval).
    Returns {"proposed": true, "action_id": "..."}.
    """
    if not blog_service.is_configured():
        return blog_service.config_error()

    await agent_broadcast(workspace_id, "lno_blog_delete_post", "running")
    result = await blog_service.propose_delete(workspace_id, post_id)
    if "error" in result:
        await agent_broadcast(workspace_id, "lno_blog_delete_post", "error", result["error"])
        return result
    await agent_broadcast(
        workspace_id,
        "lno_blog_delete_post",
        "done",
        f"queued delete for '{result.get('title', post_id)}'",
    )
    return result
