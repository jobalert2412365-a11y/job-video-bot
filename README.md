# Free daily job-opening video bot

Runs on GitHub Actions once a day: RSS -> Gemini (script) -> edge-tts (voice) -> ffmpeg (video) -> YouTube upload.
Everything used here has a free tier. Videos upload as PRIVATE by default.

## Setup (about 30 minutes, once)
1. **GitHub**: create a new repo, upload all these files (keep the `.github` folder). Public repos have unlimited Actions minutes; private ones get a monthly free allowance.
2. **feeds.txt**: add your RSS feed URLs.
3. **Gemini key**: get a free API key at https://aistudio.google.com -> repo Settings > Secrets and variables > Actions > add `GEMINI_API_KEY`.
4. **YouTube API**: in Google Cloud Console create a project, enable "YouTube Data API v3", create an OAuth client of type *Desktop app*, download it as `client_secret.json`.
   - On the OAuth consent screen set publishing status to **In production**, otherwise the refresh token expires after 7 days.
   - Locally run `pip install google-auth-oauthlib` then `python get_token.py` and sign in with the channel's account.
   - Add the three printed values as secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
5. **Optional Telegram alert**: secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
6. Go to the Actions tab -> "Daily job video" -> **Run workflow** to test. Check the private video in YouTube Studio.

## Notes
- Unverified API projects: YouTube may force API uploads to stay private until the project passes an audit. Check the YouTube API docs; if so, publish manually from Studio (the Telegram link helps).
- In Studio, mark the video as containing altered/synthetic content where YouTube asks.
- Tamil: set VIDEO_LANGUAGE=Tamil, VOICE=ta-IN-PallaviNeural and the Noto Tamil font path in daily.yml. Test that the on-screen Tamil renders correctly.
- If GitHub pauses the schedule after a quiet period, re-enable it in the Actions tab.
