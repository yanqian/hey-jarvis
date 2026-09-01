(function installNegotiationDiagnostics(root) {
  "use strict";

  function boundedDiagnosticValue(value) {
    return typeof value === "string" && /^[A-Za-z0-9_.:-]{1,100}$/.test(value)
      ? value
      : null;
  }

  function buildNegotiationDiagnostic(localHttpStatus, payload) {
    const detail = { reason: "webrtc_negotiation_failed", localHttpStatus };
    const providerError =
      payload && typeof payload.error === "object" && payload.error ? payload.error : {};
    const upstreamHttpStatus = providerError.upstream_http_status;
    if (
      Number.isInteger(upstreamHttpStatus) &&
      upstreamHttpStatus >= 400 &&
      upstreamHttpStatus <= 599
    ) {
      detail.upstreamHttpStatus = upstreamHttpStatus;
    }
    for (const [key, value] of [
      ["errorType", providerError.provider_error_type],
      ["errorCode", providerError.provider_error_code],
    ]) {
      const safe = boundedDiagnosticValue(value);
      if (safe !== null) detail[key] = safe;
    }
    return detail;
  }

  root.HeyJarvisNegotiationDiagnostics = Object.freeze({ buildNegotiationDiagnostic });
})(globalThis);
