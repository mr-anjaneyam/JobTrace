import html
import re


def clean_html_text(text: str | None) -> str:
    """Sanitize raw or HTML-entity-encoded job descriptions into clean, formatted plain text."""
    if not text:
        return ""

    # Unescape HTML entities (e.g. &lt;h2&gt; -> <h2>, &quot; -> ", &nbsp; -> space)
    # Unescape twice to handle doubly-escaped entities
    s = html.unescape(text)
    if "&lt;" in s or "&gt;" in s or "&amp;" in s or "&quot;" in s or "&#" in s:
        s = html.unescape(s)

    # Convert list items to bullet points with newline
    s = re.sub(r'<li[^>]*>', '\n• ', s, flags=re.IGNORECASE)

    # Convert headers, paragraphs, and block quotes to double newlines for readable paragraph spacing
    s = re.sub(r'<(?:/p|/h[1-6]|/div|/blockquote)[^>]*>', '\n\n', s, flags=re.IGNORECASE)

    # Convert line breaks and table/list item closures to single newlines
    s = re.sub(r'<(?:br|/li|/tr|/table)[^>]*>', '\n', s, flags=re.IGNORECASE)

    # Strip any remaining HTML tags
    s = re.sub(r'<[^>]+>', '', s)

    # Strip unclosed tags or partial tag leftovers at the end of truncated strings
    s = re.sub(r'<[^>]*$', '', s)
    s = re.sub(r'<>', '', s)

    # Normalize whitespace & clean lines
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in s.splitlines()]
    result = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                result.append("")
                prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    return "\n".join(result).strip()
