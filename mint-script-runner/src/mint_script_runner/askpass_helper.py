#!/usr/bin/env python3
"""
Lightweight Git AskPass helper for Mint Script Runner.
Responds to Git credential prompts automatically using environment variables.
"""

import sys
import os

def main():
    prompt = " ".join(sys.argv[1:]).lower()
    user = os.environ.get("MINT_GIT_USER", "")
    token = os.environ.get("MINT_GIT_TOKEN", "")

    if "username" in prompt:
        print(user)
    elif "password" in prompt or "passphrase" in prompt or "token" in prompt:
        print(token)
    else:
        # Fallback to token if password-like
        print(token)

if __name__ == "__main__":
    main()
