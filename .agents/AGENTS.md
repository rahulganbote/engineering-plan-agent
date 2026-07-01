# Project-Scoped Rules

## Git & Deployment Constraints
- **Do NOT commit or merge to the `main` branch automatically.** All development work, staging commits, and pushes must occur on the `dev-react-ui-upgrade` branch (or other dev branches).
- Let the user verify changes locally first. Only merge or push to `main` when the user explicitly instructs you to do so.
- When deploying to GCP, run `gcloud builds submit` on the active dev branch unless specifically directed to trigger a build of `main`.
