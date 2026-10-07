---
name: html-prototype-interview
description: Plan a website or app through a working HTML prototype, then interview the user while they explore it and revise the screens and flows. Use for early product direction and missing-screen or interaction discovery.
---

# HTML Prototype Interview

Make the proposed product tangible enough for the user to try, then use their
responses to discover and settle requirements. The primary artifact is a website
or app-like HTML prototype with working navigation and representative actions.
A slide deck, screen inventory or specification alone does not satisfy this task.

## Establish the first slice

Read the supplied conversation, requirements and existing prototype. Reuse settled
choices and state the coverage when only a sample of history was read. Identify
the intended user, their main task, target device and the result they need.
Ask only about unknowns that prevent a useful first prototype; use clearly marked
assumptions for reversible choices. Do not invent confirmed requirements.

Choose a coherent path from entry to outcome, including the screens and states
needed to try it. Keep secondary or deferred paths explicit. When a prototype
already exists, inspect and continue it rather than starting another design.

## Optional design references

Consider `design-reference` when actual examples would help choose layout,
navigation, information hierarchy or visual direction. If available and relevant,
use its catalog and inspected examples; distinguish observed features from proposed
adaptations and keep source links. If unavailable, use supplied references or a
simple suitable layout and disclose the gap only when material.

Reference research is optional. A request to consider how references could fit
is not a request to restyle the current prototype. Preserve an accepted direction;
show a small comparison only when a design decision actually remains open.
Do not make a reference catalog or a particular aesthetic mandatory.

## Build something the user can try

Prefer a standalone HTML file with CSS and minimal JavaScript for a new small
prototype. Reuse the existing project structure when appropriate; do not add a
framework, backend or dependencies merely to simulate a flow.

Use realistic representative content and working controls for the chosen path:
links change screens, forms accept input, and actions visibly change state.
Include relevant cancel/back paths and consequential empty, validation or failure
states. Clearly identify unfinished controls instead of letting them silently do
nothing. Label sample data and simulated service actions; a mock success is not
proof of a real save, login, payment or API call. Do not wire live mutations just
to make a planning prototype feel real.

Choose in-memory or local browser state according to what the interview needs.
Explain persistence and refresh behavior. Avoid placing private source material
in shareable artifacts unless that scope is authorized. Keep prototype notes and
screen identifiers out of the product UI unless they help the user evaluate it.

Use native accessible controls, labels, visible focus and usable keyboard paths.
Fit the requested devices. Retain an editable artifact and a usable preview.

## Check before the interview

Open the actual artifact and exercise the chosen path through its visible UI.
Check representative input, cancellation/back navigation, important exceptional
states and any claimed persistence. Inspect the layout at the target viewport;
check narrow-screen overflow when mobile use is in scope. Report access failures
or untested behavior rather than treating a file write as a successful preview.
Use proportional existing checks; no generic test framework is required.

Show the preview and identify what can be tried, what is simulated and which
assumptions remain open. If only prototype creation was requested, deliver it
without making an interview mandatory. If interviewing was requested, begin with
one concrete task on the displayed screen and wait for the user's response.

## Interview through the screens

Ask a small batch of questions tied to the current screen and observed action.
Start with product purpose and task flow; explore detail when it changes behavior.
Useful prompts include:

- What would you expect to do next from this screen? Is a step or destination missing?
- When you press this action, what result should appear, and where does its information come from?
- Who can view or change this item? What should happen when input is missing or the action fails?

Select questions relevant to the product; this is not a questionnaire to exhaust.
Do not answer on the user's behalf, treat silence as approval, or infer acceptance
from a rendered screen. Separate user decisions, agent proposals and open questions.
If the user is reviewing an existing HTML, start there rather than rebuilding it
or demanding a full written specification first.

Keep a compact decision record in the existing task notes, or a small companion
Markdown file if no notes exist. Reference recognizable screen/action names and
the prototype revision. Record the decision and reason, affected behavior, unresolved
questions and the next change. Preserve the canonical record across iterations.

Apply settled changes within the authorized scope, recheck affected flows and
return to the revised screen. Continue until the user accepts the relevant
product direction or explicitly pauses the interview. A working first prototype
and an accepted plan are separate milestones.

## Hand off when requested

The default result is the editable prototype plus decisions and open questions.
API contracts follow the screen interview when requested. Map agreed actions to
inputs, displayed outputs, state changes, access rules and error behavior before
choosing endpoints or types. Trace contracts back to agreed screens/actions and
leave unresolved choices explicit. Do not automatically generate API schemas,
select a backend stack, or begin production implementation.
