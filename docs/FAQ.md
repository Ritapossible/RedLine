# FAQ

## Why would a vendor accept a RedLine cover?

Because it is paid through it, continuously, and can prove to every customer
that the terms they paid for will hold. Accepting costs a vendor nothing as
long as it keeps the pinned passages; it only loses the unearned part of a
prepay if it cuts a right the buyer paid for. A vendor that never plans to
do that has nothing to lose and a credible promise to gain.

## What if the vendor redesigns its website?

Nothing happens. RedLine reduces the page to its visible text and looks for
each pinned passage, word for word. New layouts, menus, cookie banners,
build ids and "last updated" dates do not touch that answer. Only an edit to
a pinned sentence, or moving it to a different URL, is noticed.

## What if the vendor rewords a passage but keeps the promise?

The word-for-word check fails, so the jury reads the pinned passage against
today's page. If the right is the same, it rules **same** and the cover
carries on. On chain, a reworded refund sentence with the 30 days kept was
ruled same on both networks (confidence 95 on Studio, 99 on Bradbury).

## Can the vendor trick the jury with text on the page?

It was tried: a page that narrowed the refund and also told the jury to
answer "same". The jury ruled it **narrowed** on both networks. Page text is
shown to the jury as quoted material inside markers the page cannot close,
and validators each re-read the page themselves; a breach stands only if
they agree.

## What if the page is down for a while?

One absent check stops the vendor accruing from that moment. If the page is
back at the next check, accrual resumes. Only three absent checks running
end the cover, dated from the first. A brief outage costs an honest vendor
only the paused time.

## What if the vendor shows different text to different validators?

Then the validators cannot agree, no observation is recorded, and the check
is expired as **contested**, which counts like a page that is down. Three
running refund the buyer. A vendor cannot keep being paid by making every
check fail.

## Who pays for checks, and who sends them?

Anyone can request a check, and whoever sends the transaction pays its fee.
Today the buyer, the vendor or anyone else has to send them; a cover nobody
checks simply pays the vendor. An automatic keeper is on the
[Roadmap](ROADMAP.md).

## Can the vendor lose money it already earned?

No. Credits are never clawed back. A breach closes the cover as of the check
that found it; everything earned before that stays the vendor's.

## What does RedLine not do?

It does not judge fairness, legality or intent, and it does not read
anything but the one pinned URL. It does not follow redirects reliably
(untested), and it cannot catch a vendor that fools a majority of validators
the same way every time: that looks exactly like a page that really says
what they saw. See the [Threat model](THREAT-MODEL.md).

## Is this on mainnet?

Not yet. It runs on GenLayer Studio and the Bradbury testnet. Every case was
run on both, with 0 failed checks, and every payout re-read from the chain
(see the [Build and deploy](DEPLOYMENT.md) page and the README's record).
