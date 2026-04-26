# MDSynapse Paper-to-Blog Pipeline — n8n Setup Guide

Automated pipeline that monitors a Google Drive folder for new research papers, generates a blog-post summary + infographic via Gemini, and creates a PR on `slowvak/mdsynapse.org`.

## Pipeline Flow

```
Google Drive (new PDF) → Download → Extract Text → Gemini (blog post) → Gemini (infographic) → GitHub PR
```

---

## Step 1: Google Drive Connection (Service Account)

OAuth2 scopes may be restricted by your Google Workspace admin. Use a **Service Account** instead — it bypasses OAuth consent screen restrictions entirely.

### Setup

1. **Google Cloud Console** → [console.cloud.google.com](https://console.cloud.google.com)
   - Go to **APIs & Services → Library**
   - Search for **Google Drive API** → click **Enable** (if not already)

2. **Create Service Account** (IAM & Admin → Service Accounts)
   - Click **Create Service Account**
   - Name: `mdsynapse-pipeline` (or similar)
   - Skip optional permissions → click **Done**
   - Click into the new service account → **Keys** tab → **Add Key → Create New Key → JSON**
   - Save the downloaded JSON key file securely

3. **Share your Drive folder** with the service account
   - Copy the service account email (e.g., `mdsynapse-pipeline@your-project.iam.gserviceaccount.com`)
   - In Google Drive, right-click your target folder → **Share**
   - Paste the service account email → set to **Viewer** → Send
   - The service account can only see folders explicitly shared with it

4. **In n8n** → Settings → Credentials
   - Create new credential: **"Google Drive API (Service Account)"**
   - Paste or upload the JSON key file contents
   - Test with "Fetch Test Event" → should succeed

---

## Step 2: Set Up Gemini API Key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Create a new API key (or use existing)
3. In n8n → Settings → Variables, create:
   - **Name**: `GEMINI_API_KEY`
   - **Value**: your API key

---

## Step 3: Set Up GitHub Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Create a **Fine-grained personal access token**:
   - Repository access: Select `slowvak/mdsynapse.org`
   - Permissions:
     - Contents: **Read and write**
     - Pull requests: **Read and write**
3. In n8n → Settings → Credentials, create:
   - Type: **Header Auth**
   - Name: `GitHub Token`
   - Header Name: `Authorization`
   - Header Value: `Bearer ghp_YOUR_TOKEN_HERE`

---

## Step 4: Configure n8n Variables

In n8n → Settings → Variables, create these:

| Variable Name | Value |
|---|---|
| `GDRIVE_FOLDER_ID` | The ID from your Google Drive folder URL (the part after `/folders/`) |
| `GEMINI_API_KEY` | Your Gemini API key from Step 2 |
| `BLOG_POST_PROMPT` | Contents of `prompts/blog-post-prompt.txt` |
| `INFOGRAPHIC_PROMPT` | Contents of `prompts/infographic-prompt.txt` |

### Getting the Google Drive Folder ID
1. Open Google Drive in browser
2. Navigate to the folder you want to monitor
3. The URL will look like: `https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoPqRsTuVwXyZ`
4. The folder ID is: `1aBcDeFgHiJkLmNoPqRsTuVwXyZ`

---

## Step 5: Import the Workflow

1. In n8n → Workflows → click **"..."** menu → **Import from File**
2. Select `paper-to-blog-workflow.json`
3. Update credential references:
   - Click each Google Drive node → select your Google Drive OAuth2 credential
   - Click each GitHub HTTP Request node → select your GitHub Token credential
4. **Activate** the workflow (toggle in top-right)

---

## Step 6: Test

1. Upload a research paper PDF to your monitored Google Drive folder
2. Either wait for the hourly trigger, or click **"Test Workflow"** manually
3. Check the execution log in n8n for any errors
4. Verify a PR appears on [github.com/slowvak/mdsynapse.org/pulls](https://github.com/slowvak/mdsynapse.org/pulls)

---

## Troubleshooting

| Issue | Fix |
|---|---|
| No files detected | Check `GDRIVE_FOLDER_ID` is correct. Try changing filter from "created in last hour" to a wider window for testing |
| Gemini returns error | Check API key is valid. Check you haven't hit rate limits. The free tier allows 60 requests/min |
| GitHub 403 error | Token may not have write access to the repo. Regenerate with correct permissions |
| Infographic not generated | Gemini image generation is experimental. The workflow handles this gracefully — PR will be created without the infographic |
| PDF text extraction empty | Some scanned PDFs don't have extractable text. Consider adding an OCR step (Google Cloud Vision or Gemini multimodal) |

---

## Architecture Notes

- **Gemini model**: Uses `gemini-2.0-flash` for blog post (fast, good at structured output) and `gemini-2.0-flash-exp-image-generation` for infographics
- **To switch to Claude**: Replace the Gemini HTTP Request node with an Anthropic API call. The prompt templates work with any LLM
- **To switch to NotebookLM**: NotebookLM doesn't have a public API. You'd need to manually feed papers into NotebookLM and copy results. The automated pipeline uses Gemini as the closest equivalent
- **Deduplication**: The filter checks `createdTime` in the last hour. For more robust dedup, add a node that checks a Google Sheet or stores processed file IDs
