/**
 * LabTrack email intake worker.
 *
 * Bound to labs@bodytools.work via Cloudflare Email Routing. Parses the
 * incoming message, extracts PDF attachments, and POSTs them to LabTrack's
 * intake webhook, which enforces the sender allowlist and shared-secret
 * token and feeds the PDFs into the results importer.
 *
 * Rejections bounce back to the sender with a reason, so a forwarder finds
 * out when nothing was ingested. Transient LabTrack/API failures also
 * bounce (Email Workers have no retry queue) — re-forwarding the email is
 * the retry, and the importer's hash dedup makes that safe.
 */

import PostalMime from "postal-mime";

export default {
  async email(message, env) {
    const sender = message.from || "";
    const parsed = await PostalMime.parse(message.raw);

    const pdfs = (parsed.attachments || []).filter(
      (attachment) =>
        attachment.mimeType === "application/pdf" ||
        (attachment.filename || "").toLowerCase().endsWith(".pdf")
    );
    if (pdfs.length === 0) {
      message.setReject("No PDF attachments found; nothing was imported.");
      return;
    }

    const form = new FormData();
    form.append("sender", sender);
    for (const pdf of pdfs) {
      form.append(
        "files",
        new Blob([pdf.content], { type: "application/pdf" }),
        pdf.filename || "result.pdf"
      );
    }

    const response = await fetch(env.INTAKE_URL, {
      method: "POST",
      headers: { "X-Intake-Token": env.INTAKE_TOKEN },
      body: form,
    });

    if (response.ok) {
      const result = await response.json();
      console.log(
        `Ingested ${result.items.length} PDF(s), ` +
          `${result.duplicates.length} duplicate(s) from ${sender}`
      );
      return;
    }

    const detail = await response
      .json()
      .then((body) => body.detail)
      .catch(() => response.statusText);
    console.error(`LabTrack intake rejected (${response.status}): ${detail}`);
    message.setReject(`LabTrack did not accept the report: ${detail}`);
  },
};
