# Introduction

**RedLine is a prepay that refunds itself when a vendor takes a right away.**

When you pay a software vendor up front, you do it against the terms on its
website that day: "cancel within 30 days for a full refund", "we delete your
data within 7 days of a request", "99.9% uptime or credits". Those promises
live on a page the vendor can edit whenever it likes. If it shortens the
refund window or deletes the deletion promise a month later, you still have a
receipt, but no record of what the page said, and no contract that can read
the new page and act on it.

RedLine is that contract. It runs on [GenLayer](https://genlayer.com), a
blockchain whose Intelligent Contracts can fetch a web page and ask a panel of
AI models a question, with every validator doing both and agreeing on the
answer before anything happens.

## The idea in one paragraph

You (the **buyer**) send your prepay to RedLine instead of straight to the
vendor, and you **pin**, word for word, the passages of the vendor's terms page
you are relying on. The vendor **accepts** the cover. From that second the
prepay **streams** to the vendor: every second the pinned rights stand, it
earns its share. Anyone may ask RedLine to **check** the page. If every
pinned passage is still there, nothing happens and no model runs. If one is
gone, a **jury** of validators' models compares what you pinned with what the
page says now and answers one question: is the right it gave you the
**same**, **narrowed**, or **removed**? If it was cut, the cover ends: the
vendor keeps what it earned up to that check, and you get the rest back.

## Who it is for

- **Buyers who prepay**: a team buying a year of an API, an agent that
  buys data or compute on its owner's behalf, anyone whose decision to pay
  rested on a specific line of a terms page.
- **Vendors who want to be trusted up front**: accepting a RedLine cover is a
  public, verifiable commitment that the terms a customer paid for will hold.
  The vendor gets paid continuously and can withdraw at any time; it only
  gives up the ability to quietly cut a pinned right and keep the rest.

## What RedLine decides, and what it does not

| What the page shows | Who decides | What the money does |
| --- | --- | --- |
| Every pinned passage still there, word for word | The contract. No model. | Nothing. The vendor keeps earning. |
| A pinned passage reworded, the right unchanged | The jury | Nothing. A rewording is not a loss. |
| A pinned right narrowed or removed | The jury | The cover ends; the unearned rest goes back to the buyer. |
| No page, three checks running | The contract. No model. | The cover ends, dated from when the page went. |
| Validators cannot agree on what the page says, three checks running | The contract. No model. | Treated exactly like no page. |

RedLine never judges whether a change is fair, legal or well-meant, and it
never reads anyone's complaint. It reads one URL and asks one question about
the passages you pinned.

## Where to go next

- [User guide](USER-GUIDE.md): open a cover, accept one, check one, get paid.
- [How a cover works](COVERS.md): states, money, checks and clocks, with a
  worked example.
- [Integration](INTEGRATION.md): call the contracts from code or an agent.
- [Architecture](ARCHITECTURE.md) and [Threat model](THREAT-MODEL.md): how it
  is built and what stops each way of cheating it.
- [Build and deploy](DEPLOYMENT.md): tests, deployment, the on-chain runs.
- [FAQ](FAQ.md) and the [Roadmap](ROADMAP.md).
