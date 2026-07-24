#!/usr/bin/env python3
"""
Quick script to delete a specific path on the Firebase Realtime Database.
"""

import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from firebase_auth import auth_headers

# ============================================================================
# CONFIGURATION - Edit these variables as needed
# ============================================================================

# Firebase Realtime Database URL
DATABASE_URL = "https://geogm-simple-map-default-rtdb.firebaseio.com"

# Path to delete (without leading slash, without .json extension)
PATHS_TO_DELETE = [
    "testBed/zzz_clientRequests",
    "testBed/zzz_clientRequests_processed"
]
# PATH_TO_DELETE = "testBed/zzz_clientRequests"
PATH_TO_DELETE = "testBed/zzz_clientRequests_processed"

# ============================================================================
# END CONFIGURATION
# ============================================================================


def build_node_url(database_url: str, *path_segments: str) -> str:
    """Build a Firebase REST URL from path segments, appending .json."""
    from urllib.parse import quote
    base = database_url.rstrip("/")
    encoded = "/".join(quote(s, safe="") for s in path_segments)
    return f"{base}/{encoded}.json"


def delete_path(database_url: str, path: str) -> bool:
    """
    Delete a path from the Firebase Realtime Database.
    
    Args:
        database_url: The Firebase database URL
        path: The path to delete (e.g., "testBed/zzz_clientRequests_processed")
    
    Returns:
        True if successful, False otherwise
    """
    url = build_node_url(database_url, *path.split("/"))
    headers = auth_headers()
    
    print(f"Deleting path: {path}")
    print(f"URL: {url}")
    
    try:
        request = Request(url, method="DELETE", headers=headers)
        response = urlopen(request)
        status = response.status
        content = response.read().decode("utf-8")
        
        print(f"✓ Successfully deleted. Status: {status}")
        if content:
            print(f"  Response: {content}")
        return True
        
    except HTTPError as e:
        print(f"✗ HTTP Error {e.code}: {e.reason}")
        try:
            error_body = e.read().decode("utf-8")
            print(f"  Error details: {error_body}")
        except:
            pass
        return False
        
    except URLError as e:
        print(f"✗ URL Error: {e.reason}")
        return False
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Firebase Realtime Database Path Purge")
    print("=" * 70)
    print()

    for each_path in PATHS_TO_DELETE:
        success = delete_path(DATABASE_URL, each_path)
    
    print()
    sys.exit(0 if success else 1)
