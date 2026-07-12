# Code Review HTML Patterns

A code-review artifact is not a diff viewer — it is an annotated walkthrough. The goal is to make the reader understand *why* a change matters, not just *what* changed.

## Overall structure

```
[Summary card — PR title, author, key stats]
[Severity legend]
[Per-file sections]
  Each file section:
    - File path header
    - Diff panel (left: before / right: after, or unified)
    - Annotation cards (severity-tagged)
[Conclusion — approve / request changes / discuss]
[Send-as-prompt button]
```

---

## Pattern 1: Two-panel diff with annotations

```css
.review-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  font-family: 'Menlo', 'Monaco', monospace;
  font-size: 13px;
}
.diff-panel { padding: .5rem; background: var(--paper-deep); overflow-x: auto; }
.annotation-panel { padding: .75rem; background: var(--surface); border-left: 1px solid var(--line); }

/* Diff line coloring */
.del { background: var(--red-bg); color: var(--red); display: block; }
.add { background: var(--green-bg); color: var(--green-dark); display: block; }
.ctx { color: var(--muted); display: block; }
.line-num { display: inline-block; width: 3ch; color: var(--muted); user-select: none; margin-right: .5rem; }
```

```html
<div class="review-grid">
  <div class="diff-panel">
    <span class="ctx"><span class="line-num">42</span> function authenticate(token) {</span>
    <span class="del"><span class="line-num">43</span>   return jwt.verify(token, process.env.SECRET);</span>
    <span class="add"><span class="line-num">43</span>   return jwt.verify(token, config.jwtSecret, { algorithms: ['HS256'] });</span>
    <span class="ctx"><span class="line-num">44</span> }</span>
  </div>
  <div class="annotation-panel">
    <div class="annotation critical">
      <strong>Critical:</strong> Old code accepts any algorithm; RS256/none attacks possible.
      Fix pins to HS256 and uses config (not raw env) for testability.
    </div>
  </div>
</div>
```

---

## Pattern 2: Severity badges and annotation cards

```css
.annotation { border-radius: 6px; padding: .6rem .8rem; margin-bottom: .5rem; font-size: .875rem; }
.critical { background: var(--red-bg); border-left: 4px solid var(--red); }
.warning  { background: var(--amber-bg); border-left: 4px solid var(--amber); }
.info     { background: #edf0f1; border-left: 4px solid var(--slate); }
.praise   { background: var(--green-bg); border-left: 4px solid var(--green); }
```

**Severity guide to include in the artifact:**
- `critical` — security issue, data loss risk, or correctness bug; must be fixed before merge
- `warning` — degrades performance, reliability, or maintainability; should be addressed
- `info` — style, naming, or improvement suggestion; optional
- `praise` — good pattern worth noting for the team

---

## Pattern 3: File tree navigation

For PRs with many files, a sticky sidebar with a file list helps navigation.

```css
.pr-layout { display: grid; grid-template-columns: 200px 1fr; gap: 1.5rem; align-items: start; }
.file-tree { position: sticky; top: 1rem; font-size: .875rem; }
.file-tree a { display: block; padding: .2rem .4rem; color: var(--green-dark); text-decoration: none; border-radius: 4px; }
.file-tree a:hover { background: var(--green-bg); }
.file-tree a.has-critical::before { content: '🔴 '; }
.file-tree a.has-warning::before  { content: '🟡 '; }
```

---

## Pattern 4: Summary card + send-as-prompt

At the top, a card with: PR title, author, date, file count, annotation tally, overall verdict.

At the bottom, a button that copies the review conclusion back to Claude:

```html
<button onclick="
  const verdict = document.getElementById('verdict').value;
  navigator.clipboard.writeText(
    'Based on the review:\n' + verdict + '\n\nPlease ' +
    (verdict.includes('approve') ? 'merge the PR.' : 'address the critical issues first.')
  ).then(() => this.textContent = 'Copied!')
">Copy review conclusion as prompt</button>
<textarea id="verdict" placeholder="Overall: approve / request changes because..."></textarea>
```

---

## Dos and don'ts for code review HTML

- **Do** show actual diff text, not paraphrased descriptions
- **Do** include a severity legend — readers forget what colors mean
- **Do** group annotations by file, not by severity (makes navigation by file natural)
- **Do** add a sticky file-tree sidebar for PRs with 5+ files
- **Don't** generate wall-of-diff with no annotations — the reader can read the PR itself
- **Don't** use red/green alone for severity — add the left border color for accessibility
- **Don't** include file contents not changed in the PR — scope to the actual diff
