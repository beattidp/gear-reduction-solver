# Worklog: GitHub Pages 404 Resolution & Deployment Options

- **Date**: 2026-11-10
- **Time**: 13:21:00-07:00
- **Agent**: Antigravity
- **User**: beattidp

## Summary of Actions
1. **Investigated GitHub Pages 404 Return Code**:
   - Confirmed `origin/main` is up to date with commit `896dc20`.
   - Verified HTTP headers via `curl -ILs https://beattidp.github.io/gear-reduction-solver/` returned HTTP 404 from GitHub's Fastly CDN edge.
2. **Identified Root Cause**:
   - In GitHub repositories, GitHub Pages defaults to "Deploy from a branch" with no branch selected (or root/docs).
   - Because all web assets are in `web/` (rather than repository root), GitHub Pages requires either:
     - **Option 1 (GitHub Actions)**: Setting repository **Settings > Pages > Source** to **"GitHub Actions"**. This activates our `.github/workflows/deploy-pages.yml` workflow to deploy `web/` directly.
     - **Option 2 (`gh-pages` branch)**: Creating a dedicated `gh-pages` branch where `web/` is mounted at root, and selecting `gh-pages` / `root` in Settings > Pages.
3. **Prepared Solutions**:
   - Verified subtree extraction for `gh-pages` (`git subtree split --prefix web -b gh-pages-local`).
   - Prepared clear step-by-step guidance for the user.
