"""Shared contract text samples — zero side-effect imports, safe to import at collection time."""
from __future__ import annotations

SAMPLE_CLEAN_CONTRACT: str = """
SERVICES AGREEMENT

This Services Agreement (the "Agreement") is entered into as of January 15, 2024
(the "Effective Date") by and between Acme Corporation, a Delaware corporation
("Client") and SupplyCo Ltd, a New York limited liability company ("Vendor").

1. GOVERNING LAW. This Agreement shall be governed by and construed in accordance
with the laws of the State of Delaware, without regard to its conflict of law
provisions.

2. LIMITATION OF LIABILITY. IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY
INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES. EACH PARTY'S TOTAL
CUMULATIVE LIABILITY SHALL NOT EXCEED THE FEES PAID IN THE TWELVE MONTHS PRIOR
TO THE CLAIM.

3. TERMINATION FOR CONVENIENCE. Either party may terminate this Agreement for any
reason upon thirty (30) days written notice to the other party.

4. TERM. This Agreement commences on the Effective Date and continues until
January 15, 2025, unless earlier terminated.
""".strip()

SAMPLE_HIGH_RISK_CONTRACT: str = """
VENDOR AGREEMENT

This agreement is made between TechVendor Inc and ClientCorp.

Services shall be provided on a best-efforts basis.

Payment terms are net-60 from invoice date.

This agreement is effective immediately upon signature.
""".strip()

SAMPLE_MFN_CONTRACT: str = """
SOFTWARE LICENSE AGREEMENT

This Software License Agreement ("Agreement") is entered into as of March 1, 2024
by and between DataSoft LLC ("Licensor") and Enterprise Co ("Licensee").

GOVERNING LAW: This Agreement shall be governed by the laws of the State of
California.

MOST FAVORED NATION: Licensor represents that the fees charged to Licensee are
no greater than those charged to any other customer for substantially similar
services and volumes. If Licensor offers lower pricing to any third party,
Licensee shall be entitled to the same pricing.

EFFECTIVE DATE: March 1, 2024.
EXPIRATION DATE: February 28, 2027.
""".strip()
