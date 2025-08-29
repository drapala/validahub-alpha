#!/usr/bin/env python3
"""Generate JWT keys for development/testing.

WARNING: These keys should ONLY be used for development.
Production keys must be managed through Doppler/Vault.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.auth.jwt_service import JWTKeyGenerator


def main():
    print("=" * 60)
    print("JWT Key Generator - DEVELOPMENT ONLY")
    print("=" * 60)
    print("\nSelect algorithm:")
    print("1. RS256 (RSA, recommended)")
    print("2. ES256 (Elliptic Curve)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        print("\nGenerating RSA keys for RS256...")
        public_key, private_key = JWTKeyGenerator.generate_rsa_keys()
        algorithm = "RS256"
    elif choice == "2":
        print("\nGenerating EC keys for ES256...")
        public_key, private_key = JWTKeyGenerator.generate_ec_keys()
        algorithm = "ES256"
    else:
        print("Invalid choice")
        return
    
    print("\n" + "=" * 60)
    print(f"Generated {algorithm} Keys")
    print("=" * 60)
    
    print("\n### PUBLIC KEY (JWT_PUBLIC_KEY) ###")
    print(public_key)
    
    print("\n### PRIVATE KEY (JWT_PRIVATE_KEY) ###")
    print(private_key)
    
    print("\n" + "=" * 60)
    print("SECURITY NOTES:")
    print("- These keys are for DEVELOPMENT ONLY")
    print("- NEVER commit private keys to git")
    print("- Use Doppler/Vault for production keys")
    print("- Rotate keys regularly")
    print("=" * 60)
    
    # Optionally save to .env.development
    save = input("\nSave to .env.development? (y/n): ").strip().lower()
    if save == "y":
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".env.development"
        )
        
        # Read existing or create new
        existing_env = {}
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        existing_env[key] = value
        
        # Update with new keys
        existing_env["JWT_PUBLIC_KEY"] = public_key.replace("\n", "\\n")
        existing_env["JWT_PRIVATE_KEY"] = private_key.replace("\n", "\\n")
        existing_env["JWT_ALGORITHM"] = algorithm
        
        # Write back
        with open(env_file, "w") as f:
            f.write("# Auto-generated JWT keys for development\n")
            f.write("# DO NOT COMMIT THIS FILE\n\n")
            for key, value in existing_env.items():
                f.write(f"{key}={value}\n")
        
        print(f"\nKeys saved to {env_file}")
        print("Remember to add .env.development to .gitignore!")


if __name__ == "__main__":
    main()