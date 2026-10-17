"""Local package replacing Emergent's private ``emergentintegrations`` dependency.

The original package was only installable inside Emergent's environment
(it is not on PyPI), which made this backend impossible to deploy anywhere
else. This shim provides the same import paths and interfaces, backed by
public SDKs (litellm for LLM chat, stripe for checkout), so the app is
fully self-hostable — Render, a VPS, anywhere — with no vendor lock-in.
"""
