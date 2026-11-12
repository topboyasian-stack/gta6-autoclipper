# YouTube publishing and authorized live sources

This app runs on the computer that performs media processing. A static web host is not enough: FFmpeg, local storage, and the app process must stay running.

## What is available

- **Kick clips:** paste a public clip page from a channel that you own or are authorized to edit/repost.
- **Your older YouTube videos:** download your own upload using YouTube Studio or Google Takeout, then upload the file in AutoClipper and paste the original YouTube URL as its source.
- **YouTube publishing:** connect your own channel with OAuth. After you approve a candidate, AutoClipper uploads it as **Private**. Review the private upload in YouTube before using the separate **Publish publicly on YouTube** button.
- **Live stream capture:** a creator can provide an RTMP/RTMPS feed they control and explicitly authorize for clipping. Completed 30–300-second segments are processed into candidate clips as the stream runs. The segment duration defaults to 120 seconds.

The clipper combines one-second audio-energy peaks (72%) with FFmpeg visual scene-change signals (28%) when available, then renders around the strongest candidate in 9:16 using the full gameplay picture over a blurred background. If scene detection fails, it falls back to audio-only ranking. This is still a signal-based first pass, not semantic understanding: it does not reliably identify kills, jokes, clutch plays, or the story of a moment yet. A candidate always waits for manual review. Publishing is never automatic.

## Connect YouTube (one-time setup)

1. Open the [Google Cloud Console](https://console.cloud.google.com/), create a project, and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen. While the app is in testing mode, add the Google account you use for your channel as a test user if Google asks for one.
3. Create an OAuth client ID. Use a Web application client and add this exact authorized redirect URI: `http://localhost:8000/youtube/oauth/callback`.
4. Download the client JSON and save it locally as `data/client_secrets.json` in this repository. Do not commit the file or share it publicly. The entire `data/` directory is ignored by Git.
5. Install the dependencies and start the app from the repository folder:

   ```bash
   python -m pip install -r requirements.txt
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

6. Open [http://localhost:8000](http://localhost:8000), choose **Connect YouTube**, and authorize the correct Google/YouTube account.
7. Approve a clip in the AutoClipper queue. It will then offer **Upload privately to YouTube**. Open and inspect the private upload. Only when you're satisfied should you click **Publish publicly on YouTube**.

OAuth tokens are saved under `data/youtube-token.json`, which is also ignored by Git. The app requests the `youtube.upload` scope only. You can disconnect/revoke access from your Google account's third-party access settings.

## Your own past YouTube uploads

The YouTube Data API is not a general video-download API. For source processing, use YouTube Studio or Google Takeout to obtain a local copy of your own upload, then add that copy through the file-upload form. The app doesn't attempt to extract the media stream from a YouTube watch page.

## Live streams from other creators

A live stream is eligible only if the streamer has granted permission for recording, editing, and your intended YouTube reuse, and the platform/source permits the workflow. Ask the creator for a dedicated RTMP/RTMPS feed or a relay feed that they control. Paste that feed into **Clip a live stream** and record the authorization in the rights field.

This feature does **not** crawl all Kick/Twitch/YouTube watch pages, defeat DRM, bypass login gates, or scrape arbitrary playback URLs. A public livestream URL is not by itself permission to download or repost the content. The user-provided feed URL is held in app memory for the capture; the database stores only its scheme and host to avoid persisting the stream key.

## Current limitations

- This is local processing, not an always-on cloud service. The computer and app need to stay running during live capture.
- An authorized RTMP/RTMPS media feed is required for live capture. Auto-discovery/authorization across every platform is not implemented.
- Moment ranking combines audio energy and scene changes, but it still needs speech/transcription and gameplay-event signals before it can reliably identify the best moments.
- YouTube OAuth requires your own Google Cloud project and client JSON. The API has quota and channel eligibility constraints set by Google/YouTube.
- Generated videos upload as private first, and the app does not publish them without a separate explicit user action.

## Official references

- [YouTube Data API video uploads](https://developers.google.com/youtube/data/guides/uploading_a_video)
- [YouTube Data API videos.insert](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert)
- [YouTube Terms of Service](https://www.youtube.com/t/terms)
- [Kick Public API documentation](https://docs.kick.com/)
