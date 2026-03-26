# ADR-004: API Keys Over JWT for B2B Auth

**Status:** Accepted
**Date:** 2026-03-26

## Context
B2B clients (internal teams) need to authenticate with the Dars API. Options: API keys, JWT, OAuth2.

## Decision
API keys with SHA-256 hashing. Each client gets one key on creation.

## Reasons
- Stateless: no token refresh, no OAuth flows
- Simple: client sets `X-API-Key` header on every request — no token management library needed
- Sufficient: clients are internal teams, not end-users with individual identities
- SHA-256 hashing: raw key never stored, only the hash — a DB breach doesn't expose keys

## Consequences
- No per-user identity within a client — all requests from a client team look the same
- Key rotation requires creating a new client or implementing a key rotation endpoint (future)
- If per-teacher identity is needed later, JWT can be layered on top
