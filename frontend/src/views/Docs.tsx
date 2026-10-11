import { useEffect, useMemo } from "react";
import { Marked, type Tokens } from "marked";
import { href, useApp } from "../state";
import introduction from "../../../docs/README.md?raw";
import userGuide from "../../../docs/USER-GUIDE.md?raw";
import covers from "../../../docs/COVERS.md?raw";
import integration from "../../../docs/INTEGRATION.md?raw";
import architecture from "../../../docs/ARCHITECTURE.md?raw";
import threatModel from "../../../docs/THREAT-MODEL.md?raw";
import deployment from "../../../docs/DEPLOYMENT.md?raw";
import faq from "../../../docs/FAQ.md?raw";
import roadmap from "../../../docs/ROADMAP.md?raw";

// The documentation lives in docs/*.md in the repository and is rendered here,
// so there is one source. Links between the files become links between pages;
// the roadmap comes last.
const REPO = "https://github.com/Ritapossible/RedLine";
const PAGES = [
  { slug: "introduction", file: "README.md", title: "Introduction", md: introduction },
  { slug: "user-guide", file: "USER-GUIDE.md", title: "User guide", md: userGuide },
  { slug: "covers", file: "COVERS.md", title: "How a cover works", md: covers },
  { slug: "integration", file: "INTEGRATION.md", title: "Integration", md: integration },
  { slug: "architecture", file: "ARCHITECTURE.md", title: "Architecture", md: architecture },
  { slug: "threat-model", file: "THREAT-MODEL.md", title: "Threat model", md: threatModel },
  { slug: "deployment", file: "DEPLOYMENT.md", title: "Build and deploy", md: deployment },
  { slug: "faq", file: "FAQ.md", title: "FAQ", md: faq },
  { slug: "roadmap", file: "ROADMAP.md", title: "Roadmap", md: roadmap },
];
const BY_FILE = new Map(PAGES.map((p) => [p.file, p.slug]));

/** GitHub's heading anchors, so links written for GitHub work here too. */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/<[^>]+>/g, "")
    .replace(/[^\p{L}\p{N}\- ]+/gu, "")
    .replace(/ /g, "-");
}

function rewrite(target: string, page: string): { url: string; external: boolean } {
  if (/^[a-z]+:/i.test(target)) return { url: target, external: true };
  const [path, anchor] = target.split("#");
  if (!path) return { url: href({ name: "docs", page, anchor }), external: false };
  const file = path.replace(/^\.\//, "");
  const slug = BY_FILE.get(file);
  if (slug) return { url: href({ name: "docs", page: slug, anchor }), external: false };
  // Anything else in the repository (the README, source files) opens on GitHub.
  const repoPath = file.startsWith("../") ? file.slice(3) : `docs/${file}`;
  return { url: `${REPO}/blob/main/${repoPath}${anchor ? `#${anchor}` : ""}`, external: true };
}

function render(md: string, page: string): { html: string; toc: { id: string; text: string }[] } {
  const toc: { id: string; text: string }[] = [];
  const marked = new Marked({
    gfm: true,
    renderer: {
      heading(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, token: Tokens.Heading) {
        const inner = this.parser.parseInline(token.tokens);
        const id = slugify(token.text);
        if (token.depth === 2) toc.push({ id, text: inner.replace(/<[^>]+>/g, "") });
        return `<h${token.depth} id="${id}">${inner}</h${token.depth}>\n`;
      },
      link(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, token: Tokens.Link) {
        const inner = this.parser.parseInline(token.tokens);
        const { url, external } = rewrite(token.href, page);
        return `<a href="${url}"${external ? ' target="_blank" rel="noreferrer"' : ""}>${inner}</a>`;
      },
      table(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, token: Tokens.Table) {
        const cell = (c: Tokens.TableCell, tag: string) => `<${tag}>${this.parser.parseInline(c.tokens)}</${tag}>`;
        const head = `<tr>${token.header.map((c) => cell(c, "th")).join("")}</tr>`;
        const body = token.rows.map((r) => `<tr>${r.map((c) => cell(c, "td")).join("")}</tr>`).join("");
        return `<div class="doc-table"><table><thead>${head}</thead><tbody>${body}</tbody></table></div>\n`;
      },
    },
  });
  // The documents are this repository's own files, written by its authors.
  const html = marked.parse(md, { async: false }) as string;
  return { html, toc };
}

export function Docs() {
  const { route } = useApp();
  const pageSlug = route.name === "docs" ? route.page : "introduction";
  const anchor = route.name === "docs" ? route.anchor : undefined;
  const index = Math.max(0, PAGES.findIndex((p) => p.slug === pageSlug));
  const page = PAGES[index];
  const { html, toc } = useMemo(() => render(page.md, page.slug), [page]);

  useEffect(() => {
    if (!anchor) return;
    const el = document.getElementById(anchor);
    if (el) el.scrollIntoView({ block: "start" });
  }, [anchor, html]);

  const prev = PAGES[index - 1];
  const next = PAGES[index + 1];
  return (
    <div className="wrap docs">
      <nav className="docs-nav" aria-label="Documentation">
        <span className="kicker">Docs</span>
        {PAGES.map((p, i) => (
          <a key={p.slug} href={href({ name: "docs", page: p.slug })} aria-current={p.slug === page.slug ? "page" : undefined}>
            <span className="n">{String(i + 1).padStart(2, "0")}</span>
            {p.title}
          </a>
        ))}
      </nav>
      <div className="docs-main">
        <select className="docs-select" aria-label="Page" value={page.slug}
          onChange={(e) => { window.location.hash = href({ name: "docs", page: e.target.value }); }}>
          {PAGES.map((p, i) => (
            <option key={p.slug} value={p.slug}>{`${String(i + 1).padStart(2, "0")}  ${p.title}`}</option>
          ))}
        </select>
        <article className="prose" dangerouslySetInnerHTML={{ __html: html }} />
        <div className="doc-foot">
          {prev ? <a className="btn" href={href({ name: "docs", page: prev.slug })}>← {prev.title}</a> : <span />}
          {next ? <a className="btn primary" href={href({ name: "docs", page: next.slug })}>{next.title} →</a> : <span />}
        </div>
        <p className="small muted" style={{ marginTop: 20 }}>
          Source: <a href={`${REPO}/blob/main/docs/${page.file}`} target="_blank" rel="noreferrer">docs/{page.file}</a>
        </p>
      </div>
      <aside className="toc" aria-label="On this page">
        {toc.length > 1 && <span className="kicker">On this page</span>}
        {toc.length > 1 &&
          toc.map((t) => (
            <a key={t.id} href={href({ name: "docs", page: page.slug, anchor: t.id })}>{t.text}</a>
          ))}
      </aside>
    </div>
  );
}
