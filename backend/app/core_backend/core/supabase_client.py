import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """
    Returns a singleton instance of the Supabase Client.
    Initializes from SUPABASE_URL and SUPABASE_KEY environment variables.
    """
    global _client
    if _client is not None:
        return _client
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in backend/.env to use Supabase authentication."
        )
    
    _client = create_client(url, key)
    return _client

