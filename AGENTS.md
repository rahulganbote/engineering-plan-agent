# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.


## 5. Target Specific Tests Rather Than the Full Suite

Running pytest runs all tests, including the expensive E2E pipeline_test.py.
Recommendation: When verifying specific code modifications (e.g., providers, security validator, or parser scripts), target only those files. Example:
- To run only provider unit tests (which use mock responses): pytest tests/unit/
- To test only a single pipeline test suite: 
pytest tests/pipeline_test.py -k test_simple_brd_pipeline 

---

## 6. Git Commit Message Best Practices

Writing clear Git commit messages ensures your project history remains clean, searchable, and easy for your team to navigate. Following industry standards transforms a chaotic history into a readable timeline.

### The 7 Rules of a Great Commit Message
The most universally accepted structure for Git commit messages follows the "50/72 rule":

*   **Separate subject from body**: Place a single blank line between the summary and the description.
*   **Limit the subject line**: Keep the first line under 50 characters whenever possible.
*   **Capitalize the subject line**: Begin the summary with a capital letter.
*   **No ending punctuation**: Do not finish the subject line with a period.
*   **Use the imperative mood**: Write the subject as a command or instruction.
*   **Wrap the body**: Restrict description lines to 72 characters to prevent visual stretching in terminal logs.
*   **Explain what and why**: Focus the body on the motivation and logic, not how the code works.

### The Imperative Mood
Write your subject line in the present tense as if you are giving an order. A great trick is to complete this sentence: *"If applied, this commit will... [your message]"*.

*   ❌ **Bad (Past Tense)**: `Added layout toggle`
*   ❌ **Bad (Present Continuous)**: `Adding layout toggle`
*   ✅ **Good (Imperative)**: `Add layout toggle`

### Conventional Commits Specification
Many modern teams enforce Conventional Commits. This structured format prefixes messages with a specific type to make them machine-readable and automate changelogs:
`<type>(<optional scope>): <description>`

Commonly accepted types include:
*   `feat`: A new feature for the user.
*   `fix`: A bug fix for the user.
*   `docs`: Changes exclusively to documentation.
*   `style`: Code formatting adjustments like spacing or semicolons.
*   `refactor`: Rewriting production code without changing behavior.
*   `test`: Adding or fixing test suites.
*   `chore`: Build configurations, routine maintenance, or tool updates.

*Note: When utilizing prefixes like `feat` or `fix`, standard practice dictates starting the type and description in lowercase.*

### Commit Discipline Best Practices
*   **Make atomic commits**: Keep commits single-purpose; do not mix a feature implementation and a distinct bug fix into one commit.
*   **Commit early and often**: Save your progress continuously to isolate errors and simplify merge conflicts.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
