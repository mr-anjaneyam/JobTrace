import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatJobDescription(raw: string | null | undefined): string {
  if (!raw) return "";

  let text = raw;
  const decode = (s: string) =>
    s
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&nbsp;/g, ' ');

  text = decode(text);
  if (text.includes('&lt;') || text.includes('&gt;') || text.includes('&quot;')) {
    text = decode(text);
  }

  // Convert list items to bullet points
  text = text.replace(/<li[^>]*>/gi, '\n• ');

  // Convert headers, paragraphs, and blockquotes to double newlines for readable paragraph spacing
  text = text.replace(/<(?:\/p|\/h[1-6]|\/div|\/blockquote)[^>]*>/gi, '\n\n');

  // Convert line breaks and table/list item closures to single newlines
  text = text.replace(/<(?:br|\/li|\/tr|\/table)[^>]*>/gi, '\n');

  // Strip remaining HTML tags
  text = text.replace(/<[^>]+>/g, '');

  // Strip unclosed tags or partial tag leftovers at the end of truncated strings
  text = text.replace(/<[^>]*$/, '');
  text = text.replace(/<>/g, '');

  // Normalize blank lines
  const lines = text.split('\n').map((l) => l.trim());
  const cleanLines: string[] = [];
  let prevBlank = false;
  for (const line of lines) {
    if (!line) {
      if (!prevBlank) {
        cleanLines.push('');
        prevBlank = true;
      }
    } else {
      cleanLines.push(line);
      prevBlank = false;
    }
  }

  return cleanLines.join('\n').trim();
}
