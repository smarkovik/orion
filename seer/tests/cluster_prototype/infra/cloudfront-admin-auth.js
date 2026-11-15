// CloudFront Function (viewer-request): HTTP Basic auth for /admin/*, everything else passes through.
// Do not commit the real credential. Replace the placeholder below at deploy time (for example with `sed` in the
// deploy script, from a secret) so the repository only ever holds "PLACEHOLDER_BASE64_USER_COLON_PASSWORD".
// Generate the value with: printf 'user:password' | base64
var EXPECTED = "Basic PLACEHOLDER_BASE64_USER_COLON_PASSWORD";

function handler(event) {
  var request = event.request;
  if (request.uri.indexOf("/admin/") !== 0 && request.uri !== "/admin") return request;
  var headers = request.headers;
  if (headers.authorization && headers.authorization.value === EXPECTED) return request;
  return {
    statusCode: 401,
    statusDescription: "Unauthorized",
    headers: {
      "www-authenticate": { value: 'Basic realm="Admin", charset="UTF-8"' },
      "cache-control": { value: "no-store" },
    },
  };
}
