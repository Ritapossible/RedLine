# User guide

The app is at [red-line-v0.vercel.app](https://red-line-v0.vercel.app).

Everything in RedLine is done from the app: **Covers** lists every cover on
the network you picked, **Open a cover** creates one, and each cover has its
own page showing the money, the pinned passages, the latest check, and the
actions you can take right now.

## Before you start

**Pick a network** with the selector at the top right of the app.

- **GenLayer Studio** is a development network. Its GEN has no value, and
  transactions settle in seconds. Click **Studio burner** to get a wallet in
  one click: a key is made in your browser and funded from Studio's faucet.
  Use **Top up** for more GEN, **Forget** to drop the key.
- **GenLayer Studio Next** is the development network that runs what
  mainnet will run, fees included: every transaction carries a small fee
  deposit, worked out by the app before you sign. It has a faucet too, so
  **Studio Next burner**, **Top up** and **Forget** work as on Studio.
- **GenLayer Bradbury** is the public testnet. Its Phase 2 reset erased
  every contract, so it shows as unavailable until RedLine is redeployed
  there. When it returns, connect your own wallet (**Connect wallet**);
  transactions take longer, and the appeal window is 40 minutes instead of 5.

If your wallet is on a different chain from the app, a banner offers to
switch it. Nothing can be signed until the two match.

## As a buyer: open a cover

1. Go to **Open a cover**. To try it with a sample, click **Use the example
   vendor's terms**: it fills in a fictional vendor's terms page and two
   passages from it (a 30-day refund and a 7-day data deletion promise).
2. **Vendor address**: the address the vendor will accept from and be paid
   to. It must be different from yours.
3. **Terms page URL**: the public page the passages are on, as a plain
   `https` address with no query string (`?…`), fragment (`#…`), user name
   or password: every validator fetches it and it is stored in public. Use
   its final URL; redirects have not been tested.
4. **Pinned passages**: 1 to 4, each with a short name (`refund`,
   `deletion`) and its text, **copied word for word from the page**, 40 to
   600 characters. Spacing, capital letters and typographic variants (curly
   quotes, long dashes) do not matter; the words and punctuation do.
5. **Prepay**: the GEN you are paying the vendor for the whole period.
6. **Coverage period**: how long the vendor must keep the terms.
   **Vendor must accept within**: how long the offer stands.
   **Minimum gap between checks**: how often the page may be checked. It must
   leave room for three checks in the coverage period.
7. Click **Prepay … GEN and pin**. Anything the contract would refuse is
   listed before you sign.

The watcher then fetches the page. If every passage is on it, the cover
becomes **offered** and waits for the vendor. If one is not, the cover is
**refunded** in full at once: no money was ever at risk. Send the vendor the
link to the cover page.

Until the vendor accepts, you can **Cancel the offer** and take the whole
prepay back. If the vendor never accepts, the cover refunds in full after the
deadline (anyone can press **Settle** to apply it).

## As a vendor: accept and get paid

1. Open the cover page with the wallet whose address the buyer entered. Read
   the pinned passages: they are exactly what you are promising to keep.
2. Click **Accept the terms**. The cover becomes **active** and the prepay
   starts accruing to you, second by second.
3. Any time, click **Settle** to credit what you have earned so far, then
   **Withdraw** to receive it. What you have been credited is never taken
   back.

If the page stays as it was, at the end of the coverage period (plus the
appeal window) the cover completes and the whole prepay is yours.

What counts as keeping the terms: each pinned passage stays on the page,
visible, word for word. Moving it into hidden markup counts as taking it
away. Editing the text right around it, or another sentence on the same
subject, sends it to the jury at the next check: a harmless edit is ruled
the same and costs you nothing; a line that withdraws or overrides the
passage ends the cover. Dates, numbers and the rest of the page do not
matter.

## As anyone: check a cover

Checks are open to everyone, buyer, vendor or a stranger, because nobody
should have to trust a particular person to look.

- **Request a check** asks the watcher to read the page now. It can be done
  once per check gap. The watcher records the request and observes the page
  by itself within seconds on Studio and Studio Next, a few minutes on Bradbury.
- **Observe again** appears while a requested check is still open and no
  reading has been agreed. It asks the validators to try again.
- **Expire the check** appears when the window closed with no agreed
  reading. It records the check as *contested*, which counts like a page that
  did not answer.

The **Watcher** card shows the result: *kept* (word for word, or the jury
ruled the right the same), *absent* (no page), *breach* (with the jury's
reading and confidence), or *gone* (absent three checks running).

## When a right is cut

A breach or a gone page stops the vendor accruing at once, then waits out
the **appeal window** (5 minutes on Studio and Studio Next, 40 on Bradbury), during which
the check can still be challenged on GenLayer. After that, **Settle** closes
the cover: the vendor keeps what it earned up to the check, the buyer gets
the rest, and each withdraws.

## Withdrawing

The treasury never pushes money to anyone; it credits it. Whenever the cover
page shows **Withdraw … GEN**, that is everything owed to your address across
all covers. One click sends it.
