"""Uploading to YouTube via the Data API v3.

Auth is the standard installed-app OAuth dance: the first run opens a browser,
after which a refresh token is cached locally. Both the client secret and the
token file are gitignored.

Defaults are deliberately conservative — uploads go out `private` unless you
change `upload.privacy`, so nothing reaches an audience before you've watched it.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .models import RenderResult, Script
from .util import env, log

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
MAX_TITLE = 100
MAX_DESCRIPTION = 4800
MAX_TAG_CHARS = 460


def _require_libs():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "YouTube upload needs the Google client libraries. Run:\n"
            "  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        ) from exc
    return Request, Credentials, InstalledAppFlow, build, MediaFileUpload


def authenticate(config: Config):
    """Return an authorised YouTube service, prompting for consent if needed."""
    Request, Credentials, InstalledAppFlow, build, _ = _require_libs()

    secret_path = Path(env("YOUTUBE_CLIENT_SECRET", default="client_secret.json"))
    token_path = Path(env("YOUTUBE_TOKEN_FILE", default="youtube_token.json"))

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        log.info("refreshing YouTube credentials")
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not secret_path.exists():
            raise RuntimeError(
                f"OAuth client secret not found at {secret_path}.\n"
                "Create one in Google Cloud Console: enable the YouTube Data API v3, "
                "create an OAuth client of type 'Desktop app', download the JSON, and "
                "point YOUTUBE_CLIENT_SECRET at it."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        log.info("saved refresh token to %s", token_path)

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def build_metadata(script: Script, config: Config) -> dict:
    """Shape the script into a valid videos.insert body."""
    suffix = str(config.get("upload.title_suffix", " #shorts"))
    title = script.title.strip()
    if len(title) + len(suffix) > MAX_TITLE:
        title = title[: MAX_TITLE - len(suffix) - 1].rstrip(" ,.;:-") + "…"
    title = f"{title}{suffix}"

    body_parts = [script.description.strip()]
    if script.disclaimer:
        body_parts.append(script.disclaimer)
    body_parts.append(str(config.get("upload.description_footer", "")).strip())
    description = "\n\n".join(p for p in body_parts if p)[:MAX_DESCRIPTION]

    # YouTube caps the *combined* length of all tags, not just each one.
    tags: list[str] = []
    budget = MAX_TAG_CHARS
    for tag in script.tags:
        clean = tag.strip()[:30]
        if not clean or len(clean) + 1 > budget:
            continue
        tags.append(clean)
        budget -= len(clean) + 1

    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": str(config.get("upload.category_id", "17")),
        },
        "status": {
            "privacyStatus": str(config.get("upload.privacy", "private")),
            "selfDeclaredMadeForKids": bool(config.get("upload.made_for_kids", False)),
        },
    }


def upload(result: RenderResult, config: Config, *, dry_run: bool = False) -> str | None:
    """Upload the rendered short. Returns the video id, or None on a dry run."""
    if not bool(config.get("upload.enabled", False)):
        raise RuntimeError(
            "upload.enabled is false. Set it to true in your config once you've "
            "reviewed what the pipeline produces."
        )

    body = build_metadata(result.script, config)
    if dry_run:
        log.info("dry run — would upload %s as: %s", result.video_path, body["snippet"]["title"])
        print(f"title:   {body['snippet']['title']}")
        print(f"privacy: {body['status']['privacyStatus']}")
        print(f"tags:    {', '.join(body['snippet']['tags'])}")
        print(f"\n{body['snippet']['description']}")
        return None

    _, _, _, _, MediaFileUpload = _require_libs()
    service = authenticate(config)

    media = MediaFileUpload(
        str(result.video_path), chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4"
    )
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log.info("upload %d%%", int(status.progress() * 100))

    video_id = response["id"]
    log.info("uploaded: https://youtube.com/watch?v=%s (%s)", video_id, body["status"]["privacyStatus"])

    if result.thumbnail_path and result.thumbnail_path.exists():
        try:
            service.thumbnails().set(
                videoId=video_id, media_body=str(result.thumbnail_path)
            ).execute()
        except Exception as exc:  # thumbnails need a verified channel
            log.warning("thumbnail upload skipped: %s", exc)

    return video_id
