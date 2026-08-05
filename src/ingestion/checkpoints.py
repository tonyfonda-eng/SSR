import json
import os
import logging
import threading

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "docs/crawl_checkpoints.json"
_checkpoint_lock = threading.Lock()

def get_checkpoint(source_name: str, channel: str) -> str:
    """Retrieves the last seen article URL/ID for a specific source and channel."""
    try:
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE, "r") as f:
                data = json.load(f)
                key = f"{source_name}::{channel}"
                return data.get(key)
    except Exception as e:
        logger.debug(f"Failed to load checkpoint for {source_name}::{channel}: {e}")
    return None

def set_checkpoint(source_name: str, channel: str, identifier: str):
    """Saves the newest article URL/ID for a specific source and channel."""
    if not identifier:
        return
        
    try:
        with _checkpoint_lock:
            data = {}
            if os.path.exists(CHECKPOINT_FILE):
                with open(CHECKPOINT_FILE, "r") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        pass
                        
            key = f"{source_name}::{channel}"
            data[key] = identifier
            
            os.makedirs(os.path.dirname(os.path.abspath(CHECKPOINT_FILE)), exist_ok=True)
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump(data, f, indent=2)
    except Exception as e:
        logger.debug(f"Failed to save checkpoint for {source_name}::{channel}: {e}")
