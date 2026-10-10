"""Create a self-signed HTTPS certificate for the demo UI (certs/lan.pem and certs/lan.key; gitignored).

    python scripts/make_cert.py

Browsers only allow microphone access on HTTPS (or localhost), so serving the UI over HTTPS lets a phone on the
Wi-Fi use its own microphone. The certificate lists localhost, 127.0.0.1 and this laptop's private addresses; the
phone shows a one-time "not private" warning (Advanced > Proceed) because nobody vouches for it. Valid from 14 days
ago (devices without network time can be days behind) until 60 days from now.
"""

import datetime
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phone_url import lan_addresses  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ips = [ipaddress.ip_address("127.0.0.1")]
    for _, ip in lan_addresses():
        addr = ipaddress.ip_address(ip)
        if addr.is_private and addr not in ips:
            ips.append(addr)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "B612 incident assistant (demo)")])
    now = datetime.datetime.now(datetime.timezone.utc)
    san = [x509.DNSName("localhost")] + [x509.IPAddress(ip) for ip in ips]
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=14))   # tolerate devices whose clock is days behind (the dev board's is)
        .not_valid_after(now + datetime.timedelta(days=60))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    out = ROOT / "certs"
    out.mkdir(exist_ok=True)
    (out / "lan.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (out / "lan.key").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    print(f"Wrote {out / 'lan.pem'} and {out / 'lan.key'} for: localhost, " + ", ".join(str(i) for i in ips))
    return 0


if __name__ == "__main__":
    sys.exit(main())
