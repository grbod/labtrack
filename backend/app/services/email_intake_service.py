"""Email intake: poll a Microsoft 365 mailbox and feed PDF attachments
into the results importer.

Forwarded lab reports land in the same pipeline as drag-and-drop uploads:
`ResultImportService.create_uploads` (hash dedup included) + the extraction
worker queue, so they show up in the Lab Test Import "Needs review" queue.

Mailbox protocol:
- Only unread messages with attachments are considered.
- A message whose PDFs were ingested is marked read and moved to the
  "LabTrack Processed" folder.
- A message that failed (rejected PDF, no allowed sender, no PDF attachment)
  is marked read and moved to "LabTrack Rejected" so it stays visible.

Auth is the OAuth2 client-credentials flow against Microsoft Graph; the app
registration needs application permission Mail.ReadWrite, ideally restricted
to this one mailbox with an application access policy.
"""

from __future__ import annotations

import base64
import time
from typing import Any, Optional

import httpx

from app.config import settings
from app.database import SessionLocal
from app.services.result_import_service import ResultImportService
from app.services.result_import_worker import enqueue_result_import
from app.services.user_service import UserService
from app.utils.logger import logger

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
LOGIN_BASE = "https://login.microsoftonline.com"

PROCESSED_FOLDER = "LabTrack Processed"
REJECTED_FOLDER = "LabTrack Rejected"

# Messages fetched per poll; anything left is picked up on the next tick.
FETCH_TOP = 10


class EmailIntakeService:
    """Polls the configured mailbox and ingests PDF attachments."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._folder_ids: dict[str, str] = {}
        self._import_service = ResultImportService()

    # -- Graph plumbing -------------------------------------------------

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.monotonic() < self._token_expires_at - 60:
            return self._token
        response = await client.post(
            f"{LOGIN_BASE}/{settings.email_intake_tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": settings.email_intake_client_id,
                "client_secret": settings.email_intake_client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.monotonic() + int(payload.get("expires_in", 3600))
        return self._token

    async def _graph(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        token = await self._get_token(client)
        response = await client.request(
            method,
            f"{GRAPH_BASE}/users/{settings.email_intake_mailbox}{path}",
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        response.raise_for_status()
        return response

    async def _folder_id(self, client: httpx.AsyncClient, name: str) -> str:
        if name in self._folder_ids:
            return self._folder_ids[name]
        listing = await self._graph(
            client,
            "GET",
            f"/mailFolders?$filter=displayName eq '{name}'&$select=id",
        )
        values = listing.json().get("value", [])
        if values:
            folder_id = values[0]["id"]
        else:
            created = await self._graph(
                client, "POST", "/mailFolders", json={"displayName": name}
            )
            folder_id = created.json()["id"]
        self._folder_ids[name] = folder_id
        return folder_id

    async def _finish_message(
        self, client: httpx.AsyncClient, message_id: str, folder_name: str
    ) -> None:
        """Mark a handled message read and file it out of the inbox."""
        await self._graph(
            client, "PATCH", f"/messages/{message_id}", json={"isRead": True}
        )
        destination = await self._folder_id(client, folder_name)
        await self._graph(
            client,
            "POST",
            f"/messages/{message_id}/move",
            json={"destinationId": destination},
        )

    # -- Intake logic ---------------------------------------------------

    @staticmethod
    def _sender_allowed(sender: str) -> bool:
        allowed = [
            entry.strip().lower()
            for entry in settings.email_intake_allowed_senders.split(",")
            if entry.strip()
        ]
        if not allowed:
            return True
        sender = sender.lower()
        return any(
            sender == entry or (entry.startswith("@") and sender.endswith(entry))
            for entry in allowed
        )

    def _upload_user_id(self) -> Optional[int]:
        db = SessionLocal()
        try:
            user = UserService().get_by_username(
                db, settings.email_intake_upload_username
            )
            return user.id if user else None
        finally:
            db.close()

    def _ingest_pdf(self, filename: str, content: bytes, user_id: int) -> list[int]:
        """Create one import from one attachment. Returns ids to enqueue."""
        db = SessionLocal()
        try:
            created, duplicates = self._import_service.create_uploads(
                db, [(filename, content, "application/pdf")], user_id
            )
            if duplicates:
                logger.info(
                    f"Email intake: '{filename}' is a duplicate of an existing import"
                )
            return [item.id for item in created]
        finally:
            db.close()

    async def poll_once(self) -> dict[str, int]:
        """One poll pass. Returns counters (for logs and tests)."""
        stats = {"messages": 0, "ingested": 0, "rejected": 0}
        user_id = self._upload_user_id()
        if user_id is None:
            logger.error(
                "Email intake: upload user "
                f"'{settings.email_intake_upload_username}' not found; skipping poll"
            )
            return stats

        async with httpx.AsyncClient(timeout=30) as client:
            listing = await self._graph(
                client,
                "GET",
                "/mailFolders/inbox/messages"
                "?$filter=isRead eq false and hasAttachments eq true"
                f"&$top={FETCH_TOP}"
                "&$select=id,subject,from,receivedDateTime",
            )
            for message in listing.json().get("value", []):
                stats["messages"] += 1
                message_id = message["id"]
                subject = message.get("subject") or "(no subject)"
                sender = (
                    (message.get("from") or {})
                    .get("emailAddress", {})
                    .get("address", "")
                )
                try:
                    if not self._sender_allowed(sender):
                        logger.warning(
                            f"Email intake: sender '{sender}' not allowed "
                            f"({subject!r}); rejecting"
                        )
                        await self._finish_message(client, message_id, REJECTED_FOLDER)
                        stats["rejected"] += 1
                        continue

                    attachments = await self._graph(
                        client,
                        "GET",
                        f"/messages/{message_id}/attachments"
                        "?$select=id,name,contentType,contentBytes",
                    )
                    pdfs = [
                        attachment
                        for attachment in attachments.json().get("value", [])
                        if attachment.get("contentBytes")
                        and (
                            attachment.get("contentType") == "application/pdf"
                            or (attachment.get("name") or "").lower().endswith(".pdf")
                        )
                    ]
                    if not pdfs:
                        logger.warning(
                            f"Email intake: no PDF attachments on {subject!r} "
                            f"from '{sender}'; rejecting"
                        )
                        await self._finish_message(client, message_id, REJECTED_FOLDER)
                        stats["rejected"] += 1
                        continue

                    created_ids: list[int] = []
                    errors: list[str] = []
                    for attachment in pdfs:
                        name = attachment.get("name") or "result.pdf"
                        try:
                            content = base64.b64decode(attachment["contentBytes"])
                            created_ids.extend(self._ingest_pdf(name, content, user_id))
                        except ValueError as exc:
                            errors.append(f"{name}: {exc}")

                    for import_id in created_ids:
                        await enqueue_result_import(import_id)

                    if created_ids or not errors:
                        # Duplicates-only messages count as processed too.
                        await self._finish_message(client, message_id, PROCESSED_FOLDER)
                        stats["ingested"] += len(created_ids)
                        logger.info(
                            f"Email intake: ingested {len(created_ids)} PDF(s) "
                            f"from '{sender}' ({subject!r})"
                        )
                    else:
                        logger.error(
                            f"Email intake: every PDF on {subject!r} from "
                            f"'{sender}' was rejected: {'; '.join(errors)}"
                        )
                        await self._finish_message(client, message_id, REJECTED_FOLDER)
                        stats["rejected"] += 1
                except httpx.HTTPError:
                    # Leave the message unread; it is retried next poll.
                    logger.opt(exception=True).error(
                        f"Email intake: Graph error handling {subject!r}"
                    )
        return stats
