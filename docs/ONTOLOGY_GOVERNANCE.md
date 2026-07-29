# SSR Canonical Corporate Action Vocabulary: Governance Rules

**Rule 1: Absolute Immutability**
Ontology IDs (e.g., CC-001) are permanently immutable. Once issued, an ID retains its semantic meaning forever. IDs must never encode temporary phrases or abbreviations that might change.

**Rule 2: Deprecation Over Deletion**
Nodes are never deleted. If a corporate action type becomes obsolete or is structurally redefined, its status is updated to "Deprecated" and it must use the "superseded_by" pointer to reference the new active node.

**Rule 3: Unidirectional Dependency**
Parents may never reference their children. The hierarchy flows strictly downward. A child knows its parent; a parent is blind to its children.

**Rule 4: Singular Lineage**
A node has exactly one primary parent. Multiple inheritance is strictly forbidden to prevent cyclical dependencies and graph resolution failures.

**Rule 5: Synonyms are Metadata**
Regional naming conventions (e.g., "Scheme of Arrangement" vs. "Plan of Arrangement") or linguistic variations are aliases. They exist as metadata within the primary canonical node, not as separate hierarchical branches.

**Rule 6: Jurisdiction is an Attribute, Not a Branch**
Jurisdiction-specific behavior lives in the metadata. Do not create separate branches for "US Cash Merger" and "UK Cash Merger." Create one "Cash Merger" node that contains an array of eligible jurisdictions and maps to jurisdiction-specific Playbook Templates.
