import asyncio
import requests
import json
import time
import uuid
import os
from datetime import datetime, timedelta
from logger_config import log

# Constants
NP_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMzAyNjY1Mzk4MzY1MTkyMTkyIiwiaWF0IjoxNzMxNjYxMTg2LCJleHAiOjE3MzI4NzA3ODZ9.EuiVpbXQaX-sdQjpCjXGDaNRAs5ctpscnb1-6GN-MLLVRoRkyQdUkzrUJeXqFWXZzxUFe76PW_ZxAexmG0HDNw"
PING_INTERVAL = 30  # seconds
RETRIES = 60  # Global retry counter for ping failures
MAX_API_RETRIES = 3
API_RETRY_DELAY = 5

DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": "https://nw2.nodepay.ai/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

# Create necessary directories
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

class NodePaySession:
    def __init__(self, proxy):
        self.proxy = proxy
        self.token_info = NP_TOKEN
        self.browser_id = str(uuid.uuid4())
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
        self.account_info = {}
        self.retry_count = 0

    def get_proxy_dict(self):
        return {
            "http": f"http://{self.proxy}",
            "https": f"http://{self.proxy}"
        }

    async def call_api(self, url, data):
        """Enhanced API call with retry mechanism"""
        headers = {
            "Authorization": f"Bearer {self.token_info}",
            "Content-Type": "application/json"
        }

        for attempt in range(MAX_API_RETRIES):
            try:
                response = requests.post(
                    url,
                    json=data,
                    headers=headers,
                    proxies=self.get_proxy_dict(),
                    timeout=10
                )
                response.raise_for_status()
                return self.valid_resp(response.json())

            except requests.ConnectionError as e:
                log.error(f"Connection error on attempt {attempt + 1} for proxy {self.proxy}: {e}")
                if attempt == MAX_API_RETRIES - 1:
                    raise ValueError(f"Failed to connect to {url} after {MAX_API_RETRIES} attempts")

            except requests.Timeout as e:
                log.error(f"Timeout error on attempt {attempt + 1} for proxy {self.proxy}: {e}")
                if attempt == MAX_API_RETRIES - 1:
                    raise ValueError(f"Timeout connecting to {url} after {MAX_API_RETRIES} attempts")

            except requests.ProxyError as e:
                log.error(f"Proxy error for {self.proxy}: {e}")
                raise ValueError(f"Proxy {self.proxy} failed")

            await asyncio.sleep(API_RETRY_DELAY)

    def valid_resp(self, resp):
        """Validate API response"""
        if not resp or "code" not in resp or resp["code"] < 0:
            raise ValueError("Invalid response")
        return resp

    def save_session_info(self):
        """Save session information to file"""
        filename = os.path.join(SESSIONS_DIR, f"{self.proxy.replace(':', '_')}.json")
        
        session_data = {
            "timestamp": datetime.now().isoformat(),
            "data": {
                "account_info": self.account_info,
                "browser_id": self.browser_id,
                "status": self.status_connect,
                "retry_count": self.retry_count
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(session_data, f, indent=4)

    def load_session_info(self):
        """Load session information from file"""
        filename = os.path.join(SESSIONS_DIR, f"{self.proxy.replace(':', '_')}.json")
        
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    session_data = json.load(f)
                    
                # Check if session is not expired (24 hours)
                timestamp = datetime.fromisoformat(session_data['timestamp'])
                if (datetime.now() - timestamp) < timedelta(hours=24):
                    self.account_info = session_data['data']['account_info']
                    self.browser_id = session_data['data']['browser_id']
                    self.status_connect = session_data['data']['status']
                    self.retry_count = session_data['data']['retry_count']
                    return True
        except Exception as e:
            log.error(f"Error loading session info for {self.proxy}: {e}")
        
        return False

    async def ping(self):
        """Send ping to keep connection alive"""
        try:
            data = {
                "id": self.account_info.get("uid"),
                "browser_id": self.browser_id,
                "timestamp": int(time.time())
            }

            response = await self.call_api(DOMAIN_API["PING"], data)
            if response["code"] == 0:
                log.info(f"Ping successful via proxy {self.proxy}")
                self.retry_count = 0
                self.status_connect = CONNECTION_STATES["CONNECTED"]
            else:
                await self.handle_ping_fail(response)
        except Exception as e:
            log.error(f"Ping failed via proxy {self.proxy}: {e}")
            await self.handle_ping_fail(None)

    async def handle_ping_fail(self, response):
        """Handle ping failure"""
        self.retry_count += 1
        if response and response.get("code") == 403:
            self.handle_logout()
        elif self.retry_count < 2:
            self.status_connect = CONNECTION_STATES["DISCONNECTED"]
        else:
            self.status_connect = CONNECTION_STATES["DISCONNECTED"]
        
        self.save_session_info()

    def handle_logout(self):
        """Handle session logout"""
        self.token_info = None
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
        self.account_info = {}
        self.save_session_info()
        log.info(f"Logged out session for proxy {self.proxy}")

    async def start_ping(self):
        """Start ping loop"""
        try:
            await self.ping()
            while True:
                await asyncio.sleep(PING_INTERVAL)
                await self.ping()
        except asyncio.CancelledError:
            log.info(f"Ping task cancelled for proxy {self.proxy}")
        except Exception as e:
            log.error(f"Error in ping loop for proxy {self.proxy}: {e}")

    async def initialize(self):
        """Initialize session"""
        try:
            if not self.load_session_info():
                response = await self.call_api(DOMAIN_API["SESSION"], {})
                self.account_info = response["data"]
                if self.account_info.get("uid"):
                    self.save_session_info()
                    await self.start_ping()
                else:
                    self.handle_logout()
            else:
                await self.start_ping()
        except Exception as e:
            log.error(f"Error initializing session for proxy {self.proxy}: {e}")
            return None
        
        return self.proxy

def load_proxies(proxy_file='proxy.txt', limit=10):
    """Load proxies from file"""
    try:
        with open(proxy_file, 'r') as f:
            return [proxy.strip() for proxy in f.readlines()[:limit]]
    except Exception as e:
        log.error(f"Error loading proxies: {e}")
        return []

async def main():
    """Main application loop"""
    log.info("Starting NodePay application")
    
    all_proxies = load_proxies()
    log.info(f"Loaded {len(all_proxies)} proxies")
    
    active_sessions = {}
    
    try:
        # Initialize sessions for active proxies
        for proxy in all_proxies[:10]:  # Start with first 10 proxies
            session = NodePaySession(proxy)
            task = asyncio.create_task(session.initialize())
            active_sessions[task] = session

        while True:
            if not active_sessions:
                if not all_proxies:
                    log.info("No more proxies available. Exiting.")
                    break
                    
                # Add new proxy if available
                proxy = all_proxies.pop(0)
                session = NodePaySession(proxy)
                task = asyncio.create_task(session.initialize())
                active_sessions[task] = session

            done, pending = await asyncio.wait(
                active_sessions.keys(),
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                session = active_sessions.pop(task)
                result = task.result()

                if result is None:
                    log.warning(f"Session failed for proxy {session.proxy}")
                    if all_proxies:
                        # Replace failed proxy with new one
                        new_proxy = all_proxies.pop(0)
                        new_session = NodePaySession(new_proxy)
                        new_task = asyncio.create_task(new_session.initialize())
                        active_sessions[new_task] = new_session

            await asyncio.sleep(3)  # Prevent tight loop

    except asyncio.CancelledError:
        log.info("Application shutdown initiated")
        # Clean up active sessions
        for task in active_sessions.keys():
            task.cancel()
    except Exception as e:
        log.error(f"Unexpected error in main loop: {e}")
    finally:
        log.info("Application shutdown complete")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Program terminated by user")
