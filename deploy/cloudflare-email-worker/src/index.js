/**
 * LabTrack email intake worker.
 *
 * Bound to labs@bodytools.work via Cloudflare Email Routing. Parses the
 * incoming message, extracts PDF attachments, and POSTs them to LabTrack's
 * intake webhook, which enforces the sender allowlist and shared-secret
 * token and feeds the PDFs into the results importer.
 *
 * Sender identity (Fix #1): the allowlist must gate on the identity that DMARC
 * actually authenticates, which is the RFC 5322 `From:` HEADER address — NOT
 * `message.from`, which Cloudflare documents as the SMTP envelope MAIL FROM (a
 * different, unauthenticated value a sender can set freely). We therefore parse
 * the MIME `From:` header and forward THAT address as `sender`.
 *
 * Sender authentication (Fix #2): Cloudflare runs SPF/DKIM/DMARC on receipt and
 * records the verdict in an `Authentication-Results` header stamped with its own
 * authserv-id (`mx.cloudflare.net`). We evaluate DMARC ONLY from a header
 * bearing that authserv-id, so a sender-supplied `Authentication-Results:
 * dmarc=pass` header can't forge a pass. Per RFC 8601 §7.1 a receiver strips
 * inbound Authentication-Results bearing its own authserv-id before stamping its
 * own; this check relies on that behaviour — verify with a spoof test (see the
 * setup doc). Anything other than a Cloudflare-stamped `dmarc=pass` is rejected.
 *
 * Anti-enumeration (Fix #5): rejections use a single generic message so a
 * prober can't learn whether an address is live or on the allowlist. The real
 * status/detail is logged server-side via console.error only.
 *
 * Batching (Fix #9): the backend caps a single request at 5 PDFs and each
 * attachment at MAX_UPLOAD_SIZE_MB. We skip oversize attachments and POST the
 * rest in batches of <=5, succeeding if ANY batch lands (dedup makes a
 * re-forward safe).
 */

import PostalMime from "postal-mime";

// Keep in sync with the backend: create_uploads caps 5 files/request and
// MAX_UPLOAD_SIZE_MB (default 10) per attachment.
const MAX_PDFS_PER_BATCH = 5;
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;

// Cloudflare stamps its DMARC verdict on an Authentication-Results header
// bearing this authserv-id. We trust only that header (see file docstring).
const CF_AUTHSERV_ID = "mx.cloudflare.net";

const GENERIC_REJECT = "Message not accepted.";

/**
 * Evaluate DMARC from Cloudflare-stamped Authentication-Results only.
 * `headers` is PostalMime's array of {key, value} (keys lowercased).
 * Returns "pass" only when a header carrying Cloudflare's authserv-id reports
 * dmarc=pass; "fail" if such a header exists but does not; "unknown" if no
 * Cloudflare-stamped header is present.
 */
function dmarcVerdict(headers) {
  const cfResults = (headers || [])
    .filter((h) => h.key === "authentication-results")
    .map((h) => h.value || "")
    .filter((v) => v.toLowerCase().includes(CF_AUTHSERV_ID));
  if (cfResults.length === 0) return "unknown";
  for (const value of cfResults) {
    const match = value.match(/dmarc=(\w+)/i);
    if (match && match[1].toLowerCase() === "pass") return "pass";
  }
  return "fail";
}

function chunk(items, size) {
  const batches = [];
  for (let i = 0; i < items.length; i += size) {
    batches.push(items.slice(i, i + size));
  }
  return batches;
}

export default {
  async email(message, env) {
    // Parse first: we need the MIME `From:` header (Fix #1) and the full header
    // set to evaluate Cloudflare's DMARC verdict (Fix #2).
    const parsed = await PostalMime.parse(message.raw);
    const sender = parsed.from?.address || "";

    // Fix #2: enforce Cloudflare's DMARC verdict before trusting the From header.
    const verdict = dmarcVerdict(parsed.headers);
    if (verdict !== "pass") {
      console.error(
        `Rejected ${sender || "(no From)"}: DMARC verdict=${verdict} ` +
          `(envelope=${message.from || "?"})`
      );
      message.setReject("Message failed sender authentication (DMARC).");
      return;
    }

    const allPdfs = (parsed.attachments || []).filter(
      (attachment) =>
        attachment.mimeType === "application/pdf" ||
        (attachment.filename || "").toLowerCase().endsWith(".pdf")
    );
    if (allPdfs.length === 0) {
      // The one case where a specific reason is genuinely useful to a real
      // forwarder and leaks nothing about the allowlist.
      message.setReject("No PDF attachments found; nothing was imported.");
      return;
    }

    // Fix #9: drop oversize attachments (they would bounce the whole message).
    const pdfs = allPdfs.filter(
      (pdf) => (pdf.content?.byteLength ?? 0) <= MAX_ATTACHMENT_BYTES
    );
    if (pdfs.length === 0) {
      message.setReject("PDF attachment(s) too large; nothing was imported.");
      return;
    }

    // The Cloudflare-stamped Authentication-Results we trusted, forwarded to the
    // backend as an audit signal (it logs it; it does not re-derive trust).
    const trustedAuthResults =
      (parsed.headers || [])
        .filter(
          (h) =>
            h.key === "authentication-results" &&
            (h.value || "").toLowerCase().includes(CF_AUTHSERV_ID)
        )
        .map((h) => h.value)
        .join(" | ") || "";

    // Fix #9: POST in batches of <=5; aggregate counts; succeed if any lands.
    let ingested = 0;
    let duplicates = 0;
    let anyBatchOk = false;
    let lastStatus = 0;
    let lastDetail = "";

    for (const batch of chunk(pdfs, MAX_PDFS_PER_BATCH)) {
      const form = new FormData();
      form.append("sender", sender);
      for (const pdf of batch) {
        form.append(
          "files",
          new Blob([pdf.content], { type: "application/pdf" }),
          pdf.filename || "result.pdf"
        );
      }

      const response = await fetch(env.INTAKE_URL, {
        method: "POST",
        headers: {
          "X-Intake-Token": env.INTAKE_TOKEN,
          // Fix #2 defense-in-depth: hand the trusted verdict to the backend as
          // an audit signal (it logs it; it does not hard-require it here).
          "X-Intake-Auth-Results": trustedAuthResults,
        },
        body: form,
      });

      if (response.ok) {
        anyBatchOk = true;
        const result = await response.json().catch(() => ({}));
        ingested += result.items?.length ?? 0;
        duplicates += result.duplicates?.length ?? 0;
        continue;
      }

      lastStatus = response.status;
      lastDetail = await response
        .json()
        .then((body) => body.detail)
        .catch(() => response.statusText);
      console.error(
        `LabTrack intake batch rejected (${lastStatus}): ${lastDetail}`
      );
    }

    if (anyBatchOk) {
      console.log(
        `Ingested ${ingested} PDF(s), ${duplicates} duplicate(s) from ${sender}`
      );
      return;
    }

    // Fix #5: every batch failed. Do not echo backend detail (avoids
    // backscatter/enumeration); the real status/detail is already logged.
    message.setReject(GENERIC_REJECT);
  },
};
