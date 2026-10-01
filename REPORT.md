# Stripe Connect web_test_webview — isStripeDomain() Suffix Bypass Allows Arbitrary Setter Dispatch from Attacker-Controlled Origin

## Summary

`connect-js.stripe.com/v1.0/web_test_webview.html` (and `/v0.1/` alias) is a live, publicly accessible, frameable HTML page that accepts `postMessage` commands from origins passing an `isStripeDomain()` check. This check uses `hostname.endsWith('connecttest.onrender.com')` **without a leading dot**, meaning any attacker who registers a Render subdomain ending in "connecttest" (e.g., `xconnecttest.onrender.com` — free tier) passes the origin validation. The attacker can then send arbitrary `callSetterWithSerializableValue` messages that invoke any setter method on any Stripe Connect embedded component, including `setKycRecipientAccountId` which source-traces to a recipient token with payout-method read/create/archive permissions.

## Affected Asset

- **URL**: `https://connect-js.stripe.com/v1.0/web_test_webview.html`
- **Alias**: `https://connect-js.stripe.com/v0.1/web_test_webview.html` (same content, same ETag)
- **Headers**: No `X-Frame-Options`, no `frame-ancestors` in CSP, no COOP
- **CSP**: `script-src 'self' https://js.stripe.com` (strict, but irrelevant — the attack uses postMessage, not script injection)

## Vulnerable Code

From source map `webTestWebview-f7ad220138f3ca9b1118.js.map`, source `isStripeDomain.ts`:

```typescript
export const isStripeDomain = (windowUrl: URL): boolean => {
  const hostname = windowUrl.hostname.toLowerCase();
  return (
    hostname.endsWith('.furever.dev') ||                              // SAFE - leading dot
    hostname.endsWith('stripe-connect-furever.onrender.com') ||      // UNSAFE
    hostname.endsWith('stripe-connect-test.onrender.com') ||         // UNSAFE
    hostname.endsWith('connecttest.onrender.com') ||                 // UNSAFE
    hostname.endsWith('issuing-embedded-components-app.vercel.app') || // UNSAFE
    hostname.endsWith('property-management-tau.vercel.app') ||       // UNSAFE
    hostname.endsWith('embedded-finance-app.vercel.app') ||          // UNSAFE
    hostname.endsWith('gym-management-mvhg.vercel.app') ||           // UNSAFE
    hostname.endsWith('coffee-shop-management-liard.vercel.app') ||  // UNSAFE
    hostname.endsWith('.stripe.com') ||                              // SAFE - leading dot
    hostname.endsWith('.stripe.me') ||                               // SAFE - leading dot
    hostname === 'localhost' || hostname === 'stripe.com' ||
    hostname.endsWith('hamster-dance.onrender.com') ||               // UNSAFE
    hostname.endsWith('express.stripe.dev')
  );
};
```

9 of 14 entries use suffix matching without a leading dot. Any attacker can register a subdomain on the same hosting provider whose name ends with the checked suffix.

## Attack Flow

```
1. Attacker registers xconnecttest.onrender.com on Render (free account)
   'xconnecttest.onrender.com'.endsWith('connecttest.onrender.com') === true ✓

2. Attacker page iframes connect-js.stripe.com/v1.0/web_test_webview.html
   (No frame-ancestors, no X-Frame-Options — frameable from any origin)

3. Webview calls fetchInitParams() which sends postMessage to parent with targetOrigin="*"
   → Attacker receives the message (confirms webview loaded)

4. Attacker sends {type: "connect-test-sdk-message", requestType: "fetchInitParams", values: {...}}
   → Webview checks isStripeDomain(new URL(event.origin))
   → 'xconnecttest.onrender.com' passes the endsWith check
   → Webview sets this.parentDomain = attacker origin
   → Webview now trusts attacker as the parent SDK coordinator

5. Attacker sends callSetterWithSerializableValue with arbitrary setter/value
   → Webview executes: component[setter](value)
   → No further validation on setter name or value
```

## Impact

### Direct capabilities from attacker origin:

| Handler | Effect |
|---|---|
| `callSetterWithSerializableValue` | Calls `component[setter](value)` — arbitrary method invocation on any Connect component |
| `fetchInitParams` / `fetchClientSecret` / `fetchAppInfo` | Intercepts initialization data, client secrets, and app info sent via `postMessage("*")` |
| `updateConnectInstance` | Modifies Connect instance configuration |
| `logout` | Forces user logout |
| `returnedFromAuthenticatedWebView` | Injects fake authentication completion |
| `mobileInputReceived` | Injects fake mobile input events |

### Escalation via setKycRecipientAccountId:

Source-traced from `ConnectElementDefinitions/account-onboarding.ts`:

1. `setKycRecipientAccountId(recipientId)` sets the recipient for KYC collection
2. `RecipientTokenInjector.tsx` passes sender context + attacker-chosen recipientId to `useRecipientToken`
3. `useRecipientToken.js` calls `getAccountVerifiedToken` with path `${senderId}/${recipientId}`
4. The derived token has permissions for:
   - `payout-method:list`, `payout-method:retrieve`, `payout-method:create`, `payout-method:archive`
   - `outbound-setup-intent` operations
   - `bank-account-spec` and routing lookups

**Note**: Backend authorization impact (whether the token is actually minted for an attacker-chosen recipientId that doesn't belong to the sender) requires owned-account A/B validation. The client-side trust boundary violation is confirmed.

## Reproduction

1. Deploy `poc.html` to `xconnecttest.onrender.com` (or any `*connecttest.onrender.com` subdomain)
2. Open the page in a browser
3. Click "Load web_test_webview.html in iframe"
4. Observe the webview sends `fetchInitParams` to the attacker page via `postMessage("*")`
5. Click "Send Init Params" — sets `parentDomain` to attacker origin
6. Click "Call setKycRecipientAccountId" — dispatches arbitrary setter

For local testing: `localhost` is also in the `isStripeDomain` allowlist, so the message flow works from `http://localhost:8888/poc.html` as well. Run `python3 server.py` and open `http://localhost:8888/poc.html`.

## Suggested Fix

Add a leading dot to all third-party hosting provider entries:

```typescript
// Before (UNSAFE):
hostname.endsWith('connecttest.onrender.com')

// After (SAFE):
hostname.endsWith('.connecttest.onrender.com') || hostname === 'connecttest.onrender.com'
```

Or better yet, remove all third-party hosting provider entries from production builds entirely — these appear to be development/demo environments that should not be trusted in the production `isStripeDomain` check.

Additionally:
- Add `X-Frame-Options: DENY` or `frame-ancestors 'none'` to `web_test_webview.html` if it should not be framed by external pages
- Bind `event.source` validation (the listener does not check that the message came from the expected parent window)
- Consider removing `web_test_webview.html` from production CDN if it is only needed for internal testing
