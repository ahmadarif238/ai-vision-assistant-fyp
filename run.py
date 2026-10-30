#!/usr/bin/env python3
"""
AI Vision Assistant 2026 - Master Launcher
Starts the FastAPI backend and serves the mobile PWA interface with local network access.
"""

import socket
import sys
import uvicorn
from backend.core.config import settings

def get_local_ip() -> str:
    """Detect LAN IP address so smartphones on the same WiFi can connect"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually establish connection, just determines route
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def main():
    local_ip = get_local_ip()
    port = settings.PORT

    print("\n" + "=" * 70)
    print(" 🚀 AI VISION ASSISTANT FOR THE VISUALLY IMPAIRED (2026 SOTA)")
    print("=" * 70)
    print(f" ▶ Local Web Access:    http://localhost:{port}")
    print(f" ▶ Smartphone LAN PWA:  http://{local_ip}:{port}")
    print("=" * 70)
    print(" 💡 Smartphone Tip:")
    print(f"    Connect your phone to the same WiFi and open http://{local_ip}:{port}")
    print("    Tap 'Add to Home Screen' in Chrome or Safari for full-screen PWA.")
    print("=" * 70 + "\n")

    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()

