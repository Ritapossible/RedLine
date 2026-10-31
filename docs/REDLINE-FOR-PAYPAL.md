# RedLine for PayPal

RedLine for PayPal brings RedLine's promise to an ordinary checkout: **pay for
the terms you were promised, and only while they hold.**

**[Open RedLine for PayPal](https://redline-paypal.vercel.app)**: buy from a
fictional vendor, pin the rights you rely on, then become the vendor and cut
one yourself. The site runs as a preview while its server is built: PayPal and
the model panel are simulated in your browser, and every screen says so. The
rules are the real ones.

## How it works

1. **Pin the rights you rely on.** At checkout, the customer pins up to four
   passages of the vendor's terms page, word for word. RedLine suggests the
   ones worth pinning; code checks each one is on the live page.
2. **PayPal holds the payment.** The amount is authorized, not collected.
   RedLine never holds money.
3. **Watched, then settled.** RedLine reads the page on a schedule. If the
   terms hold, the vendor collects in full. If a pinned right is narrowed or
   removed, and a second check confirms it, PayPal collects only the share the
   vendor earned up to that check and releases the rest.

## What it shares with RedLine on GenLayer

RedLine for PayPal is built on this project, not beside it.

- **The same rules.** `redline_text` (visible text, hidden text, word-for-word
  matching), `redline_core` (cover states and the earned share) and
  `redline_prompts` (the question put to the models) are imported unchanged.
- **The same tests.** Those modules keep their tests; the web app's preview
  is checked against `redline_text` on every example page.
- **The log is anchored on GenLayer.** Every check, reading and PayPal call
  goes into a hash-chained log whose newest hash is published to an
  Intelligent Contract on GenLayer.

The difference is who reads the page and who holds the money. On GenLayer,
validators run by different people each read the page and must agree, and a
treasury contract holds the prepayment. On PayPal, RedLine's server reads the
page and PayPal holds the payment; the log makes every ruling checkable
afterwards.

## Learn more

- [The architecture](https://github.com/Ritapossible/RedLine/blob/paypal/docs/PAYPAL-ARCHITECTURE.md):
  memory, the settlement journal, scheduling, security and the decisions behind them.
- [The code](https://github.com/Ritapossible/RedLine/tree/paypal/paypal), on the
  `paypal` branch.
