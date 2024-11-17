import re
from urllib.parse import urlparse

def parse_proxy_url(proxy_url):
    """Convert proxy URL to format username:password@host:port"""
    try:
        parsed = urlparse(proxy_url)
        # Extract username and password from netloc
        auth, host_port = parsed.netloc.split('@')
        return f"{auth}@{host_port}"
    except Exception as e:
        return None

def format_proxy_list(proxy_file):
    """Read and format proxy list from file"""
    formatted_proxies = []
    try:
        with open(proxy_file, 'r') as f:
            proxy_urls = f.read().splitlines()
        
        for url in proxy_urls:
            if proxy := parse_proxy_url(url):
                formatted_proxies.append(proxy)
    
        # Save formatted proxies
        with open('formatted_proxy.txt', 'w') as f:
            f.write('\n'.join(formatted_proxies))
            
        return formatted_proxies
    except Exception as e:
        print(f"Error formatting proxies: {e}")
        return []

# Example usage
if __name__ == "__main__":
    proxies = format_proxy_list('proxy.txt')
    for proxy in proxies:
        print(proxy)
