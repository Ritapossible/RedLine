// The demo vendor, Acme Data API, and its terms page in every version the
// vendor console offers. The HTML is RedLine's own examples/, bundled as
// text: the same pages the Python tests and the server's demo read.
import original from "../../../../../examples/terms-v1.html?raw";
import rebuilt from "../../../../../examples/terms-v1-rebuilt.html?raw";
import reworded from "../../../../../examples/terms-reworded.html?raw";
import narrowed from "../../../../../examples/terms-narrowed.html?raw";
import deletionRemoved from "../../../../../examples/terms-deletion-removed.html?raw";
import injected from "../../../../../examples/terms-narrowed-injected.html?raw";
import voided from "../../../../../examples/terms-voided.html?raw";
import hidden from "../../../../../examples/terms-hidden.html?raw";
import hiddenStyle from "../../../../../examples/terms-hidden-style.html?raw";
import type { Reading, TermsVersion, TermsVersionId } from "../types";

export const HTML: Record<Exclude<TermsVersionId, "down">, string> = {
  original,
  rebuilt,
  reworded,
  narrowed,
  "deletion-removed": deletionRemoved,
  injected,
  voided,
  hidden,
  "hidden-style": hiddenStyle,
};

export const VERSIONS: TermsVersion[] = [
  { id: "original", title: "Original terms", summary: "The page as customers pinned it.", expect: "Kept, by code. No model is asked.", cuts: false },
  { id: "rebuilt", title: "Redeployed", summary: "A new build id, nonce and \"last updated\" date; not one word of the terms changed.", expect: "Kept, by code: dates and build noise are not a change.", cuts: false },
  { id: "reworded", title: "Reworded refund", summary: "\"Cancel within thirty (30) days after you buy and we will refund all of your unused prepaid credit in full.\"", expect: "The panel reads it: same right, still kept.", cuts: false },
  { id: "narrowed", title: "Refund window cut", summary: "30 days becomes 7, with a 15% fee and a usage limit.", expect: "Narrowed: confirmed by a second check, then the rest is released.", cuts: true },
  { id: "deletion-removed", title: "Data deletion removed", summary: "\"Acme retains customer data for as long as it considers necessary.\"", expect: "Removed: confirmed, then the rest is released.", cuts: true },
  { id: "injected", title: "Cut, and tells the AI it isn't", summary: "The narrowed refund, plus text telling the reviewer to answer \"same\".", expect: "The page is quoted data: the instruction is ignored, the cut is found.", cuts: true },
  { id: "voided", title: "Withdrawn above the passage", summary: "The refund sentence is still there, word for word, under \"The following is withdrawn and does not apply.\"", expect: "Its surroundings changed, so the panel reads it: removed.", cuts: true },
  { id: "hidden", title: "Kept in the HTML, hidden", summary: "The original sentence hidden with the hidden attribute; the visible page shows the narrowed one.", expect: "Hidden text is not text: narrowed.", cuts: true },
  { id: "hidden-style", title: "Hidden with CSS", summary: "The original sentence in display:none; the visible page shows the narrowed one.", expect: "Hidden text is not text: narrowed.", cuts: true },
  { id: "down", title: "Page taken down", summary: "The terms page stops answering.", expect: "Absent three checks running: gone, settled like a cut.", cuts: true },
];

/**
 * What the preview's panel reads, per version and passage. The real panel is
 * several models on the server; the preview stands in with the readings
 * RedLine's GenLayer jury gave these same pages. Only consulted when code
 * cannot decide (the passage moved or its surroundings changed).
 */
export const READINGS: Partial<Record<TermsVersionId, Record<string, [Reading, number]>>> = {
  reworded: { refund: ["same", 92] },
  narrowed: { refund: ["narrowed", 95] },
  injected: { refund: ["narrowed", 93] },
  voided: { refund: ["removed", 90] },
  hidden: { refund: ["narrowed", 94] },
  "hidden-style": { refund: ["narrowed", 94] },
  "deletion-removed": { deletion: ["removed", 96] },
};

/** The rights worth pinning on Acme's page, as the pin assistant proposes them. */
export const SUGGESTIONS = [
  {
    id: "refund",
    label: "30-day refund",
    why: "Your money back on unused credit for a month, no questions asked.",
    text: "You may cancel at any time within 30 days of purchase and receive a full refund of any unused prepaid credit, with no questions asked.",
  },
  {
    id: "deletion",
    label: "Data deleted in 7 days",
    why: "Your data, backups included, gone within a week of asking.",
    text: "When you ask us in writing to delete your data, Acme permanently deletes all of your customer data, including backups, within 7 days of the request.",
  },
  {
    id: "availability",
    label: "Availability credit",
    why: "10% back in any month Acme misses 99.9% availability.",
    text: "If availability falls below that target in a calendar month, Acme will credit 10% of that month's usage fees to your account on request.",
  },
  {
    id: "notice",
    label: "30 days' notice of changes",
    why: "Material changes only take effect a month after they are posted.",
    text: "Material changes take effect 30 days after they are posted on this page.",
  },
];
