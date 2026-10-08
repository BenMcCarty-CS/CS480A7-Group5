# Review-effort measurement rules

Status: Working definitions for development.
The team must finalize these before producing the analysis-ready dataset.

## Unit of analysis

The final quantitative dataset has one row per pull request.

The activity table has one row per discussion comment, inline comment,
or submitted review. Activity rows are inputs, not independent PRs.

## Proposed primary outcome

Number of substantive human reviewer comments during the defined
review observation period.

Eligible sources:
- PR discussion comments.
- Inline review comments.
- Nonempty submitted-review bodies.

A substantive comment raises or addresses a technical issue, asks for
technical clarification, evaluates the proposed implementation, or
requests a meaningful change.

Examples include correctness, design, testing, documentation,
maintainability, and coding-convention feedback.

Exclude from this outcome:
- Automated messages.
- Contributions written by the PR author.
- Empty review bodies.
- Standalone acknowledgments, thanks, or approval-only messages.
- Purely administrative messages without technical evaluation.

Keep excluded activity in the intermediate data with exclusion reasons.
Author replies may be analyzed separately.

An image, link, or short reply may carry substantive meaning.
Ambiguous cases require context and human inspection.

A submitted review containing inline comments is not an additional
substantive comment unless its own body independently qualifies.

## Human and automated activity

Identify likely automation using account type, bot-name patterns,
and a documented list of known automated accounts.

An account marked User is only a potential human account.
Validate the classification using human inspection.

Identify PR authors using account IDs.
Missing identity information remains unknown.

## Time boundaries

The team must specify the PR inclusion window and the activity cutoff
separately. A PR creation-window end is not automatically the cutoff
for observing its review activity.

For an outcome measuring effort through merge, exclude post-merge
activity from that outcome.

Specify how closed-unmerged and reopened PRs are handled before
constructing duration outcomes.

Preserve creation, submission, and update timestamps separately.
Where inline comments belong to a submitted review, consider the
review submission time when determining when feedback became visible.

## Additional outcomes

Review rounds:
Do not equate review-record count or commit count with review rounds.
Define an operational rule and validate it against manually inspected PRs.

Review duration:
Measure from first qualifying substantive reviewer feedback to the
chosen endpoint, such as merge or qualifying approval.

Keep time to merge and time to approval as separate outcomes.

If no qualifying starting feedback is observed, duration is undefined,
not zero.

Current DISMISSED review states do not reconstruct historical approvals
or dismissal times. Flag affected historical approval measurements.

## Data quality and missingness

Compare PR-detail counts against unique raw records before filtering.

Count agreement is supporting evidence, not proof of completeness.
Submitted reviews have no reference total in the supplied PR details.

Missing or failed collection must not become zero effort.
Retain collection-status flags and distinguish provisional observed
counts from validated analysis outcomes.

## Validation

Use the five supplied PRs for developing and checking the rules.
They are not a representative validation sample.

Validate substantive-comment and automation classifications on a
broader sample with independent human judgments before adjudication.
Document disagreements and any resulting rule changes.