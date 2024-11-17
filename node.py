import json
import os
from datetime import datetime

def save_session_info(proxy, data):
    """Save session information to a JSON file."""
    filename = f"sessions/{proxy.replace(':', '_')}.json"
    os.makedirs("sessions", exist_ok=True)
    
    session_data = {
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    with open(filename, 'w') as f:
        json.dump(session_data, f)

def load_session_info(proxy):
    """Load session information from JSON file."""
    filename = f"sessions/{proxy.replace(':', '_')}.json"
    
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                session_data = json.load(f)
                
            # Check if session is not expired (24 hours)
            timestamp = datetime.fromisoformat(session_data['timestamp'])
            if (datetime.now() - timestamp).total_seconds() < 86400:
                return session_data['data']
    except Exception as e:
        logger.error(f"Error loading session info for {proxy}: {e}")
    
    return None

def save_status(proxy, status):
    """Save proxy status to a JSON file."""
    filename = "proxy_status.json"
    
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                status_data = json.load(f)
        else:
            status_data = {}
        
        status_data[proxy] = {
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(status_data, f)
    except Exception as e:
        logger.error(f"Error saving status for {proxy}: {e}")

def is_valid_proxy(proxy):
    """Validate proxy format and connectivity."""
    try:
        # Validate proxy format
        if not proxy or ':' not in proxy:
            return False
            
        # Test proxy connectivity
        test_url = "https://api.nodepay.ai"
        response = requests.get(
            test_url,
            proxies={"http": proxy, "https": proxy},
            timeout=5
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Proxy validation failed for {proxy}: {e}")
        return False

def remove_proxy_from_list(proxy):
    """Remove failed proxy from the list and save to file."""
    try:
        with open('proxy.txt', 'r') as f:
            proxies = f.read().splitlines()
        
        if proxy in proxies:
            proxies.remove(proxy)
            
        with open('proxy.txt', 'w') as f:
            f.write('\n'.join(proxies))
            
        # Also remove any saved session
        session_file = f"sessions/{proxy.replace(':', '_')}.json"
        if os.path.exists(session_file):
            os.remove(session_file)
            
        logger.info(f"Removed proxy {proxy} from list")
    except Exception as e:
        logger.error(f"Error removing proxy {proxy}: {e}")

def call_api(url, data, proxy, max_retries=3):
    """Enhanced API call with retry mechanism."""
    headers = {
        "Authorization": f"Bearer {token_info}",
        "Content-Type": "application/json"
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                proxies={"http": proxy, "https": proxy},
                timeout=10
            )
            response.raise_for_status()
            return valid_resp(response.json())
            
        except requests.ConnectionError as e:
            logger.error(f"Connection error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise ValueError(f"Failed to connect to {url} after {max_retries} attempts")
                
        except requests.Timeout as e:
            logger.error(f"Timeout error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise ValueError(f"Timeout connecting to {url} after {max_retries} attempts")
                
        except requests.ProxyError as e:
            logger.error(f"Proxy error: {e}")
            remove_proxy_from_list(proxy)
            raise ValueError(f"Proxy {proxy} failed")
            
        await asyncio.sleep(API_RETRY_DELAY)
