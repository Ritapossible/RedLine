// A port of contracts/redline_text.py for the in-browser preview: visible
// text, normalisation, word-for-word presence, and the context print that
// decides whether a passage still on the page is kept without a model.
// The server uses the Python original; these must agree on the demo pages.
import type { TermsBlock } from "../types";

const HIDDEN_ELEMENTS = ["script", "style", "noscript", "template", "svg", "head", "iframe"];
const HIDING_CLASSES = ["hidden", "d-none", "sr-only", "visually-hidden", "invisible", "screen-reader-text"];
const HIDING_STYLES = ["display:none", "visibility:hidden", "font-size:0;", "font-size:0px", "opacity:0;"];

const FOLD: Record<string, string> = {
  "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
  "“": '"', "”": '"', "„": '"', "″": '"',
  "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
  " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
  "​": "", "‌": "", "‍": "", "﻿": "", "­": "",
  "…": "...",
};

export const MIN_PASSAGE = 40;
export const MAX_PASSAGE = 600;
const CONTEXT = 60;
const DATE_WORDS = new Set(
  "january february march april may june july august september october november december monday tuesday wednesday thursday friday saturday sunday".split(" "),
);

function isHidden(el: Element): boolean {
  if (HIDDEN_ELEMENTS.includes(el.tagName.toLowerCase())) return true;
  if (el.hasAttribute("hidden")) return true;
  if (el.getAttribute("aria-hidden") === "true") return true;
  const style = (el.getAttribute("style") ?? "").replace(/\s+/g, "").toLowerCase() + ";";
  if (HIDING_STYLES.some((s) => style.includes(s))) return true;
  const classes = (el.getAttribute("class") ?? "").toLowerCase().split(/\s+/);
  return classes.some((c) => HIDING_CLASSES.includes(c));
}

/** The page's visible blocks, in order: what a reader sees, not what the HTML hides. */
export function visibleBlocks(html: string): { title: string; blocks: TermsBlock[] } {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const title = doc.querySelector("title")?.textContent?.trim() ?? "";
  for (const el of Array.from(doc.body.querySelectorAll("*"))) if (isHidden(el)) el.remove();
  const els = Array.from(doc.body.querySelectorAll("h1, h2, h3, p, li, nav, footer, div.cookie"));
  const kind = (el: Element): TermsBlock["kind"] => {
    const tag = el.tagName.toLowerCase();
    if (tag === "h1") return "title";
    if (tag === "h2" || tag === "h3") return "heading";
    if (tag === "nav" || tag === "footer" || el.classList.contains("cookie") || el.classList.contains("stamp")) return "chrome";
    return "text";
  };
  const blocks = els
    .filter((b) => !els.some((o) => o !== b && o.contains(b)))
    .map((b) => ({ kind: kind(b), text: (b.textContent ?? "").replace(/\s+/g, " ").trim() }))
    .filter((b) => b.text);
  return { title, blocks };
}

/** Lower case, typography folded, whitespace collapsed (redline_text.normalize). */
export function normalize(text: string): string {
  let out = "";
  for (const ch of text) out += FOLD[ch] ?? ch;
  return out.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
}

// redline_text decodes numeric references and only these named ones; any
// other named reference (&copy;) stays as literal text. A browser decodes
// them all, so for the rules the page is rewritten the Python way first.
const ENTITIES: Record<string, string> = {
  amp: "&#38;", lt: "&#60;", gt: "&#62;", quot: "&#34;", apos: "&#39;", nbsp: " ",
  rsquo: "'", lsquo: "'", rdquo: '"', ldquo: '"', ndash: "-", mdash: "-",
  hellip: "...", shy: "", middot: "*", bull: "*",
};

function entitiesAsPython(html: string): string {
  return html.replace(/&([^;&\s]{1,10});/g, (whole, name: string) => {
    if (name.startsWith("#")) return whole; // numeric: decoded alike
    const known = ENTITIES[name.toLowerCase()];
    return known !== undefined ? known : "&#38;" + name + ";";
  });
}

/** The normalised visible text of a page (redline_text.page_text). */
export function pageText(html: string): string {
  const doc = new DOMParser().parseFromString(entitiesAsPython(html), "text/html");
  for (const el of Array.from(doc.body.querySelectorAll("*"))) if (isHidden(el)) el.remove();
  // Block boundaries are spaces, as in the Python original.
  const parts: string[] = [];
  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) parts.push(node.textContent ?? "");
    else node.childNodes.forEach(walk);
    if (node.nodeType === Node.ELEMENT_NODE) parts.push(" ");
  };
  walk(doc.body);
  return normalize(parts.join(""));
}

export function passagePresent(text: string, passage: string): boolean {
  const p = normalize(passage);
  return p !== "" && text.includes(p);
}

export function passageError(passage: string): string {
  const p = normalize(passage);
  if (p.length < MIN_PASSAGE) return `A pinned passage must be at least ${MIN_PASSAGE} characters.`;
  if (p.length > MAX_PASSAGE) return `A pinned passage must be at most ${MAX_PASSAGE} characters.`;
  return "";
}

function words(text: string): string[] {
  return text.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
}

function letters(text: string): string {
  return text
    .replace(/[^\p{L}]+/gu, " ")
    .split(" ")
    .filter((w) => w && !DATE_WORDS.has(w))
    .join(" ");
}

function significant(text: string): Set<string> {
  return new Set(words(text).filter((w) => w.length > 4 && /^\p{L}+$/u.test(w)));
}

/** redline_text.context_print: "" if the passage is not on the page. */
export function contextPrint(text: string, passage: string): string {
  const p = normalize(passage);
  if (!p || !text.includes(p)) return "";
  const parts: string[] = [];
  let at = text.indexOf(p);
  while (at !== -1) {
    const before = letters(text.slice(Math.max(0, at - 30 * CONTEXT), at)).split(" ").filter(Boolean).slice(-CONTEXT);
    const after = letters(text.slice(at + p.length, at + p.length + 30 * CONTEXT)).split(" ").filter(Boolean).slice(0, CONTEXT);
    parts.push(before.join(" ") + "|" + after.join(" "));
    at = text.indexOf(p, at + 1);
  }
  const want = significant(p);
  for (const sentence of text.split(p).join(" ").split("? ").join(". ").split("; ").join(". ").split(". ")) {
    let shared = 0;
    for (const w of significant(sentence)) if (want.has(w)) shared++;
    if (shared >= 3) parts.push(letters(sentence));
  }
  let h = 14695981039346656037n;
  for (const ch of parts.join("#")) h = ((h ^ BigInt(ch.codePointAt(0)!)) * 1099511628211n) % 18446744073709551616n;
  return h.toString(16).padStart(16, "0");
}

export async function sha256(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}
