import React from "react";

function inline(text: string, key: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <React.Fragment key={`${key}-${i}`}>{part}</React.Fragment>
    ),
  );
}

/** Minimal, safe renderer: paragraphs, bullets, numbered lists, **bold**. Never injects HTML. */
export default function RichText({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={`l${blocks.length}`} className={`my-1 ml-5 space-y-0.5 ${list.ordered ? "list-decimal" : "list-disc"}`}>
        {list.items.map((it, i) => (
          <li key={i}>{inline(it, `li${blocks.length}-${i}`)}</li>
        ))}
      </Tag>,
    );
    list = null;
  };
  text.split("\n").forEach((raw, i) => {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const num = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || num) {
      const ordered = !!num;
      if (list && list.ordered !== ordered) flush();
      list = list ?? { ordered, items: [] };
      list.items.push((bullet ?? num)![1]);
    } else {
      flush();
      if (line.trim()) blocks.push(<p key={`p${i}`} className="my-1">{inline(line, `p${i}`)}</p>);
    }
  });
  flush();
  return <>{blocks}</>;
}
