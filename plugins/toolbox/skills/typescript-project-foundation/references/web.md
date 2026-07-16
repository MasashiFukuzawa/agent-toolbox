# Web profile

Use React + Vite for a client-rendered web application when SSR, server components, native rendering, or another framework-specific requirement is absent.

## Baseline

- React and Vite at current compatible stable versions
- Separate environment-safe public configuration from server secrets
- Route/API schemas shared only through an intentional package boundary
- Accessible semantic HTML, keyboard interaction, focus handling, and error/status announcements
- Error boundary and loading/empty/error states
- Unit/component tests for behavior and a small number of high-value browser flows

## Conditional choices

### TanStack Router

Add it when the SPA has multiple routes and benefits from typed path/search params, nested layouts, loaders, route prefetching, or route-level auth. A single-screen application does not need a router.

### TanStack Query

Add it for non-trivial server state: caching, invalidation, mutation lifecycle, retries, polling, optimistic updates, or route preloading. Do not wrap static/local state or a single fetch solely for stack uniformity.

### Tailwind

Add it when utility-first styling matches the intended component/token strategy and team workflow. Do not add it to an API-only project or as a substitute for design decisions. Establish tokens, focus states, contrast, responsive behavior, and component ownership early when a real UI will be maintained.

## Security boundaries

- Decide same-origin vs cross-origin deployment before auth implementation.
- Define cookie domain, Secure, HttpOnly, SameSite, CSRF, and CORS together.
- Never expose server secrets through Vite environment variables.
- Treat route guards as user experience; server-side authorization remains authoritative.
- Avoid rendering raw server error details or unsafe HTML.

## Testing

- Vitest for components and state behavior
- Mock Service Worker or equivalent only where it preserves the contract; retain real API integration tests
- Browser/E2E tests for authentication, authorization-denied flows, destructive confirmation, and critical user journeys
- Manual visual/interaction verification remains necessary for UI details; AI implementation does not compress human perception and requirement confirmation as much as deterministic code work

