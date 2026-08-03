import sys
import argparse
from mcp_server.google_client import GoogleWorkspaceClient

def run_auth():
    print("Checking Google Workspace API credentials...")
    try:
        client = GoogleWorkspaceClient()
        print("\n🎉 Google Authentication Successful!")
        print(f"Token file verified: {client.token_path}")
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Authentication Failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Blinkit Review Analyzer CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    # Auth subcommand
    subparsers.add_parser("auth", help="Execute the one-time browser OAuth authentication flow")
    
    # Fallback to help if no command is given
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
        
    args = parser.parse_args()
    
    if args.command == "auth":
        run_auth()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
