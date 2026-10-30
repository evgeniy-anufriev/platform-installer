# Execution Node status consistency

Owner-reported screenshot: global header displayed Core fetch failure, the node
card header displayed Core waiting, and its inline status displayed Prepared.
The earlier fix synchronized only the two card indicators during local actions;
the App header and Core projection phase still had independent presentation.

The UI design's shared interaction rules and Servers section require readiness
and Core projection waiting/errors in the same node status. App now projects a
single display value from current backend readiness, the bounded preparation
response and Core projection state, and passes it to the Servers panel. Local
component tests retain a fallback for callers without the shared projection.
The global header, card header and inline status use that value and tone.
Core failure overrides Ready presentation until the matching projection arrives;
active preparation and preparation errors take precedence over old Core state.

Preparation presentation is bound to project revision, selected node and session
credentials. It survives page navigation; the Servers controls stay disabled
while the existing preparation call is pending. Later checks supersede it.
Backend return values, approval, Start and Core readiness authority are unchanged.
Saved project, Project Verify and deployment plan remain separate facts.
The saved-Core-preview effect from commit 4e41a9ba is unchanged.

Verification: affected App/Servers tests 98 PASS; TypeScript typecheck PASS;
git diff --check PASS. Tests cover pending Core fetch, failure with matching
danger tones, retry to success, and preparation across page navigation. Old
readiness fixtures now return matching Core runtime identities; an existing
navigation check waits for asynchronous Core availability instead of racing it.
Real Wails and visual acceptance were not performed. This is frontend-only:
delivery needs a new desktop build, with no runtime bundle change.
