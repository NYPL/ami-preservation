#!/usr/bin/env python3
"""
AWS SSO Authentication Checker
Usage: python aws_sso_check.py [--profile PROFILE_NAME]
"""

import subprocess
import sys
import argparse


def check_aws_auth(profile_name=None):
    """Check if AWS credentials are valid using AWS CLI"""
    cmd = ['aws', 'sts', 'get-caller-identity']
    if profile_name:
        cmd.extend(['--profile', profile_name])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr

    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        print("❌ Error: AWS CLI not found. Please install it first.")
        sys.exit(1)


def run_sso_login(profile_name=None):
    """Run AWS SSO login"""
    cmd = ['aws', 'sso', 'login']
    if profile_name:
        cmd.extend(['--profile', profile_name])

    print(f"\n🔐 Running: {' '.join(cmd)}")
    print("=" * 50)

    try:
        # Use call() to let user interact with the login process
        result = subprocess.call(cmd)

        if result == 0:
            print("\n✅ SSO login successful!")
            return True
        else:
            print("\n❌ SSO login failed")
            return False

    except KeyboardInterrupt:
        print("\n\n⚠️  Login cancelled by user")
        return False


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Check AWS SSO authentication and prompt login if needed'
    )
    parser.add_argument(
        '--profile',
        help='AWS profile name to use',
        default=None
    )
    args = parser.parse_args()

    return args


def main(profile_name=None):
    profile_msg = f" (profile: {profile_name})" if profile_name else ""
    print(f"🔍 Checking AWS authentication{profile_msg}...")

    is_authenticated, output = check_aws_auth(profile_name)

    if is_authenticated:
        print(f"✅ Already authenticated{profile_msg}")
        return 0

    print(f"❌ Not authenticated{profile_msg}")
    print(f"Reason: {output.strip()}")

    if run_sso_login(profile_name):
        # Verify authentication succeeded
        is_authenticated, _ = check_aws_auth(profile_name)
        if is_authenticated:
            print("✅ Authentication verified!")
            return 0
        else:
            print("⚠️ Login completed but authentication check failed")
            return 1
    else:
        return 1


if __name__ == '__main__':
    args = parse_arguments()

    sys.exit(main(args.profile))