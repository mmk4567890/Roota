"""TLS settings for outbound HTTPS (Anthropic API, embedding model download).

httpx verifies against its own bundled CA list (certifi) by default. Machines
whose antivirus or corporate proxy re-signs HTTPS traffic (e.g. Avast Web
Shield) install their root certificate in the operating system's store only,
so every certifi-verified request fails with CERTIFICATE_VERIFY_FAILED.

``ssl.create_default_context()`` verifies against the OS trust store instead
(the Windows certificate store on Windows, the system CA paths elsewhere).
Verification stays fully on: CERT_REQUIRED and hostname checking.
"""

from __future__ import annotations

import ssl


def system_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # create_default_context already sets both; asserted so a future change
    # here can never silently turn verification off (never disable TLS).
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise RuntimeError("system SSL context must verify certificates and hostnames")
    return context
