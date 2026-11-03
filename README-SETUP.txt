STORIES OF THE WORLD - AUTOMATIC STORY SETUP

This bundle keeps your existing website design and adds a separate stories.json archive.
The original Egypt Day 1 story remains in index.html. New generated stories are stored in stories.json.

FILES
- index.html: your existing page, updated to load stories.json
- stories.json: starts empty; new stories are appended here
- scripts/generate_story.py: asks Gemini for a story, and uses Groq if Gemini fails
- .github/workflows/daily-story.yml: runs daily at 06:00 India time and can also be run manually

IMPORTANT SECURITY
The API keys shown in your earlier screenshot must be revoked because they were exposed.
Create fresh keys only after revoking the exposed ones. Never paste the new keys into ChatGPT or commit them into files.

GITHUB SETUP
1. Open your repository: https://github.com/ariasurela-code/stories_of_the_world
2. Add/replace index.html with this bundle's index.html.
3. Create stories.json in the repository root and paste [] into it.
4. Create folder .github/workflows and add daily-story.yml inside it.
5. Create folder scripts and add generate_story.py inside it.
6. Commit the changes to the main branch.
7. In the repository, open Settings > Secrets and variables > Actions > New repository secret.
   Add GEMINI_API_KEY with your NEW Google AI Studio key.
   Add GROQ_API_KEY with your NEW Groq key.
   Keep both keys private. You may add just one provider; Gemini is tried first and Groq is fallback.
8. Open Actions and enable workflows if GitHub asks.
9. Open "Publish a new country story" > Run workflow to test once.
10. Check that stories.json now contains a Day 2 story. GitHub Pages will publish the updated file.

SCHEDULE
The workflow is scheduled for 06:00 India Standard Time (00:30 UTC). GitHub scheduled workflows can occasionally start late.

LIMITATION
This creates daily automatic publication and a manual GitHub Actions run. It does NOT automatically detect a story you ask ChatGPT to write. For that, a separate authenticated ChatGPT-to-GitHub integration/webhook is needed; this chat currently cannot directly trigger a commit in your repository.

COST
GitHub Actions usage may be within GitHub's included limits for a public repository. Gemini and Groq API usage/quotas depend on their current account terms; check their dashboards. API usage is separate from a ChatGPT subscription.
