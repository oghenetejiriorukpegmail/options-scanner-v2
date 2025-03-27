import requests
import json

def test_fmp_api():
    # Get API key from config
    with open('config.json') as f:
        config = json.load(f)
        api_key = config['fmp_api_key']
    
    print(f"Testing FMP API with key: {api_key[:4]}...")
    
    # Try different FMP endpoints
    endpoints = [
        "https://financialmodelingprep.com/api/v3/nasdaq_constituent?apikey={api_key}",
        "https://financialmodelingprep.com/api/v3/historical/nasdaq_constituent?apikey={api_key}",
        "https://financialmodelingprep.com/api/v3/symbol/NASDAQ?apikey={api_key}"
    ]
    
    for url_template in endpoints:
        url = url_template.format(api_key=api_key)
        print(f"\nTrying endpoint: {url}")
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                symbols = [item["symbol"] if isinstance(item, dict) else item for item in data]
                print(f"Success! Retrieved {len(symbols)} symbols")
                print("First 5 symbols:", symbols[:5])
                return True
            else:
                print("Unexpected response format:", data)
                
        except Exception as e:
            print(f"API Error: {e}")
    
    return False

if __name__ == "__main__":
    test_fmp_api()