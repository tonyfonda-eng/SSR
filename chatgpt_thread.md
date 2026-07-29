# Paste your ChatGPT thread below this line:Pasted text.txt
Document
here is the setup i've had so far. Far from perfect. idea is to receive email alerts if those keywords are met
SSR Operating Manual v1.0.pdf
PDF
here
SSR Operating Manual v1.0(1).pdf
PDF
uploaded yet again. can you see it?
SSR Operating Manual v1.0.docx
Document
deep-research-report.md
File
what about those?
Pasted text(1).txt
Document
here
Pasted markdown(1).md
File
here is a response - let me know when you have enough of those so i stop the copy paste back and forth
Pasted text(2).txt
Document
Pasted markdown(2).md
File
and this?
Today 8:27 AM
special-situations-radar-full-backup.zip
Zip Archive
i have the full zip file, when i upload it here, analyse it in full, audit and debug.
SSR Operating Manual v1.0(1).pdf
PDF
close but not exactly this


This is the point where the design becomes much more important than the code.

One of the biggest reasons M&A/news bots become noisy is that they try to match keywords instead of intent.

Our pipeline should be designed so that keywords are only used to help identify the type of article, never to decide whether something is interesting.

Proposed philosophy
Source
      ↓
Article
      ↓
Cash Event Detection
      ↓
Classification
      ↓
Playbook
      ↓
AI Research

Notice there is no "keyword alert" stage.

Keywords are simply evidence.

Stage 1 — Cash Event Detection

This stage asks only one question:

Is this article potentially about a corporate cash event?

It doesn't care whether we own the stock.

It doesn't care about arbitrage.

It doesn't care whether it's actionable.

Only:

"Is this article worth deeper analysis?"

Examples

YES

acquisition
merger
strategic review
going private
tender offer
asset sale
special dividend
liquidation
bankruptcy
restructuring
spin-off
rights issue
recapitalisation

NO

quarterly earnings
ESG report
new CEO
opens factory
product launch
sponsorship
wins award
Stage 2 — Classification

Now the bot decides

"What kind of event is this?"

Example

Merger

Acquisition

Asset sale

Tender offer

Going private

Activist

Strategic review

Bankruptcy

Liquidation

Capital raising

Special dividend

Court decision

Regulatory approval


This should be an AI decision.

Not keyword based.

Stage 3 — Playbook selection

Now we finally ask

"What playbook should analyse this?"

Examples

Cash merger

Tender offer

Take-private

Spin-off

Liquidation

Special dividend

Rights issue

Distressed


Each playbook knows

what to calculate
which documents to fetch
which questions to ask AI
Where do keywords fit?

I wouldn't expose a "Keywords" worksheet.

Instead I'd build something called

Event Signals

These are not filters.

They're evidence.

Example

Phrase	Weight
acquisition	10
merger agreement	10
strategic alternatives	9
tender offer	10
definitive agreement	10
all cash	9
board approved	8
activist	6
restructuring	5

The detector simply accumulates evidence.

For example

Article

Company announces definitive merger agreement in an all-cash transaction.

Scores

merger agreement +10

all cash +9

definitive agreement +10

Total = 29


Clearly worth passing onwards.

An article saying

Company launches new product

scores

0


and dies immediately.

Then AI decides

The detector only decides

Probably important

or

Probably not

The LLM decides

This is a cash acquisition.

Confidence 96%.


Very different jobs.

Intent beats wording

Example

PR A

Company enters into definitive merger agreement.

PR B

Company to be acquired by XYZ.

PR C

XYZ announces acquisition of ABC.

Different wording.

Exactly the same intent.

AI recognises intent.

Keywords help it.

Confidence score

Every article should have

Cash Event Score

0-100

Example

4

12

28

44

71

93


We can set

0-20

Ignore

21-50

Needs AI review

51-100

Run full playbook

What should be configurable?

Only things that humans genuinely want to tune.

Examples

Minimum confidence

Enabled playbooks

Enabled sources

Tracked exchanges

Tracked countries

Alert threshold


Not

200 keyword lists
My recommendation

I would avoid a traditional "keyword search" worksheet altogether.

Instead, the workbook would contain an Event Signals sheet that acts as a lightweight scoring aid, while the actual decision-making is driven by AI understanding of the article's intent. That gives you the best of both worlds: the system is explainable (you can see which signals contributed to the score), but it isn't brittle or dependent on exact wording.

I also suggest one refinement to the pipeline we locked down earlier:

Sources
      ↓
Articles
      ↓
Event Signals (evidence scoring)
      ↓
Cash Event Detection
      ↓
Classification
      ↓
Playbook
      ↓
AI Research
      ↓
Review
      ↓
Alert / Dashboard
      ↓
Archive
      ↓
Learning

That preserves the simple high-level flow while making it clear that "keywords" are merely evidence feeding the detector, not the mechanism that decides whether something is important. This approach will scale much better as you add more jurisdictions, languages, and event types.

then prefill the human side of the workbook as well

Yes. This is the right time to prefill the human-controlled parts of the workbook.

One thing I would change from how we've previously discussed it is that the workbook should not try to encode the logic itself. The workbook should encode investment knowledge. The bot contains the logic.

That distinction will make the system much easier to maintain.

Human-owned sheets

These are the sheets you maintain.

1. Sources

You've already started this.

Purpose:

Tell the bot where to look.

Contains

Source
Type (RSS/HTML/API)
URL
Poll frequency
Priority
Enabled
Notes
2. Cash Events

This is probably the single most important sheet in the entire workbook.

Not keywords.

Events.

Example

Event	Description	Priority
Acquisition	One company buying another	Critical
Merger	Combination	Critical
Tender Offer	Cash tender	Critical
Going Private	Delisting	Critical
Asset Sale	Disposal	High
Business Combination	Merger language	High
Strategic Alternatives	Sale process	High
Sale Process	Company looking for buyer	High
Bankruptcy Exit	Possible acquisition	Medium
Spin-off	Corporate action	Medium

Notice these are concepts.

3. Context Rules

This sheet explains how to interpret language.

Example

Positive Context	Negative Context
definitive agreement	rumor
board approved	speculation
entered into merger	market commentary
acquisition completed	analyst opinion
all-cash	hypothetical

The AI reads these.

4. Companies

Watchlist.

Ticker

Exchange

Sector

Market Cap

Country

Priority

Notes

5. Playbooks

This is your investment process.

Example

Playbook

Cash Merger

Questions

Cash?
Financing secured?
HSR?
Break fee?
Competing bidder?
Management support?
Regulatory risk?
6. AI Research Templates

This is where your Gemini prompts live.

For example

Cash Merger Prompt

Tender Offer Prompt

Take Private Prompt

Activist Prompt

Spin-off Prompt

These are editable without touching Python.

7. Filters

These aren't keywords.

They're business rules.

Example

Minimum market cap

Minimum spread

Countries

Exchanges

Sector exclusions

ADR allowed?

8. Dashboard Settings

Notification thresholds

Discord enabled

Email enabled

Research enabled

Archive days

Polling interval

Bot-owned sheets

Grey.

Hands off.

Examples

Articles

Research Queue

AI Output

Alerts

Dashboard

Archive

Learning

Logs

Health

Metrics

Colour convention

I'd make it extremely obvious.

Colour	Meaning
White	User edits
Light Grey	Bot writes
Dark Grey	Bot internal
Blue	Information
Yellow	Needs review
Green	Approved
Red	Failed/error
The keyword issue

I think we should stop thinking about "keyword search."

The pipeline should look like this:

Article

↓

Cash Event Detection

↓

Context Detection

↓

Intent Detection

↓

Confidence Score

↓

Playbook Selection

↓

AI Research

Notice there is no keyword sheet.

Instead:

Cash Event

↓

Evidence

↓

Confidence

For example

Article says

Company X entered into a definitive merger agreement...

Bot concludes

Event:
Acquisition

Evidence

✓ definitive agreement

✓ merger

✓ board approval

Confidence

97%

Completely different from

keyword = merger

which produces far too many false positives.

I would actually remove "Keywords" entirely

Instead the workbook contains

Cash Events

and

Context Rules

Those become the knowledge base.

The AI already understands synonyms.

It doesn't need us listing

acquisition
acquires
acquired
acquiring
acquisition of

It knows those.

What it needs is

"These all mean the Cash Acquisition playbook."

That's much more powerful.

I think this workbook is evolving into something much bigger than a configuration file. It is becoming the operating manual of your investment process. Someone unfamiliar with the Python code should be able to open the workbook and understand:

where the system looks,
what it is looking for,
how it classifies events,
which playbook it follows,
what research it performs,
when it alerts you,
and how outcomes are recorded for continuous improvement.

That's a much stronger design than a workbook full of keywords and settings.

ok. ready to produce the full workbook now?


Yes. I think we've now reached the point where it's worth designing the entire SSR workbook properly rather than adding sheets incrementally.

The workbook is no longer "just a spreadsheet." It is becoming the control plane for the whole platform.

I would build it once, with a stable architecture, and then let Gemini implement against that specification.

The workbook should have three sections
1. Control Centre (you edit these)

These are the sheets you own.

Sheet	Purpose
README	Documentation, colour legend, workflow
Pipeline	High-level SSR workflow (for reference)
Sources	Every monitored source (RSS/HTML/API/etc.)
Rules	Cash-event detection rules
Playbooks	What to do once an event is detected
Watchlist	Companies you're actively following
AI Research Queue	Companies requiring deep research
Settings	Poll intervals, confidence thresholds, etc.
2. Operational (bot-owned)

These should be grey and clearly marked DO NOT EDIT.

Sheet	Purpose
Source Health	Feed status
Crawl Log	Every crawl
Articles	Raw articles ingested
Cash Events	Extracted candidate events
Classification	AI classifications
Alert Queue	Pending alerts
Alerts Sent	Complete alert history
Dashboard	Live dashboard
Learning	Feedback database
Metrics	Runtime metrics
Errors	Runtime failures
3. Archive

Historical data.

Archived articles
Archived alerts
Old companies
Historical statistics
Colour convention

I'd actually make this extremely obvious.

Colour	Meaning
🟢 Light green	User editable
⚪ White	User input cells
🟡 Light yellow	AI recommendations awaiting review
🔵 Light blue	Calculated summaries
⚫ Grey	Bot owned — never edit
🔴 Red	Errors
🟣 Purple	Archived

This colour legend belongs on the README sheet.

The Sources sheet

This becomes the heart of ingestion.

Each row represents one source.

Enabled	Priority	Source	Type	HTML URL	RSS URL	Poll	Dedupe	Status	Notes

Examples:

PR Newswire
GlobeNewswire
Business Wire
SEC Edgar
LSE RNS
TSX News
Nasdaq
HKEX
ASX
SEDAR+
Companies House
FCA
Competition authorities
Bankruptcy courts

etc.

One thing I'd improve from our earlier discussions

Earlier we were thinking:

RSS OR HTML

I now think production should always support multiple endpoints.

For PR Newswire, for example:

HTML
RSS

Both enabled.

The crawler should simply ask

"Which one has newer content?"

If HTML is newer

→ use HTML

Otherwise

→ use RSS

Then deduplicate.

That makes the system far more resilient.

Rules

This is where the intelligence starts.

Not

Keyword = Merger

Instead

Rules describe

Cash Event Intent

For example

Event Family:

Merger
Tender Offer
Going Private
Asset Sale
Rights Issue
Special Dividend
Liquidation
Spin-off

Each rule contains

keywords
exclusions
confidence modifiers
AI prompt
downstream playbook
Playbooks

Each cash event maps to one playbook.

Example

Cash Merger

↓

Research

↓

Calculate spread

↓

Check regulatory approvals

↓

Check financing

↓

Score probability

↓

Generate investment note

Different playbooks exist for

Tender offer
Spin-off
Liquidation
Distressed recapitalisation
etc.
Dashboard

Very simple.

Top section

Today's Alerts

Middle

Pipeline

Sources

↓

Articles

↓

Cash Events

↓

Classification

↓

Playbook

↓

Research

↓

Review

↓

Alerts

Bottom

Health

feeds alive
articles/hour
errors
alerts today
average latency
One architectural change I recommend

I would remove AI Research Queue as a user-managed sheet.

Instead

The bot populates it automatically.

You only have

Approve
Reject
Hold

That prevents manual mistakes.

My recommendation

Before writing another line of Python, I would freeze Workbook v1.0.

Everything else—the bot, Gemini, GitHub Actions, event bus—should conform to the workbook, not the other way around.

That gives us a stable contract between you (the analyst) and the automation.

I think this is the right moment to define that contract once and keep it stable for the rest of the project.
