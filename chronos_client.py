"""
Chronos API Client for authentication and data fetching
"""
import requests
import re
from typing import Optional, Dict
from datetime import datetime
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


class ChronosClient:
    def __init__(self, username: str, password: str, base_url: str, auth_url: str):
        self.username = username
        self.password = password
        self.base_url = base_url
        self.auth_url = auth_url
        self.session = requests.Session()
        self.bearer_token: Optional[str] = None
        self.cookies: Dict[str, str] = {}
        
    def authenticate(self) -> bool:
        """
        Authenticate with Chronos system using headless browser
        Returns True if authentication successful
        """
        try:
            logger.info("Starting headless browser authentication...")
            
            with sync_playwright() as p:
                # Launch headless browser
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = context.new_page()
                
                # Intercept network requests to capture the bearer token
                captured_token = {'value': None}
                
                def handle_response(response):
                    """Capture token from OAuth2 token endpoint response"""
                    try:
                        if 'token' in response.url and response.status == 200:
                            try:
                                data = response.json()
                                if 'access_token' in data:
                                    captured_token['value'] = data['access_token']
                                    logger.info("Captured access_token from network request")
                            except:
                                pass
                    except:
                        pass
                
                page.on('response', handle_response)
                
                try:
                    # Navigate to Chronos login page
                    logger.info(f"Navigating to {self.base_url}...")
                    page.goto(self.base_url, wait_until='networkidle', timeout=30000)
                    
                    # Wait for login form to appear (Keycloak)
                    logger.info("Waiting for login form...")
                    page.wait_for_selector('input[name="username"], input#username', timeout=10000)
                    
                    # Fill in credentials
                    logger.info("Filling in credentials...")
                    page.fill('input[name="username"], input#username', self.username)
                    page.fill('input[name="password"], input#password', self.password)
                    
                    # Submit the form
                    logger.info("Submitting login form...")
                    page.click('input[type="submit"], button[type="submit"]')
                    
                    # Wait for navigation after login (check for successful redirect)
                    logger.info("Waiting for authentication to complete...")
                    page.wait_for_url(f"{self.base_url}/**", timeout=15000)
                    
                    # Wait for the application to load
                    page.wait_for_timeout(2000)
                    
                    # Extract cookies from browser
                    browser_cookies = context.cookies()
                    logger.info(f"Extracted {len(browser_cookies)} cookies from browser")
                    
                    # Convert to session cookies
                    for cookie in browser_cookies:
                        self.session.cookies.set(
                            cookie['name'],
                            cookie['value'],
                            domain=cookie.get('domain', ''),
                            path=cookie.get('path', '/')
                        )
                        self.cookies[cookie['name']] = cookie['value']
                    
                    # Extract bearer token by intercepting the OAuth2 token request
                    # The token is obtained from Keycloak's token endpoint after login
                    try:
                        # Wait a bit more for token to be stored
                        page.wait_for_timeout(1000)
                        
                        # Check localStorage for token first
                        token = page.evaluate("""() => {
                            // Try various possible storage keys
                            const keys = [
                                'token', 'access_token', 'bearer_token', 'accessToken',
                                'auth_token', 'authToken', 'jwt', 'jwtToken'
                            ];
                            
                            // Check localStorage
                            for (const key of keys) {
                                const val = localStorage.getItem(key);
                                if (val) return val;
                            }
                            
                            // Check sessionStorage
                            for (const key of keys) {
                                const val = sessionStorage.getItem(key);
                                if (val) return val;
                            }
                            
                            // Try to find token in any localStorage/sessionStorage value
                            for (let i = 0; i < localStorage.length; i++) {
                                const key = localStorage.key(i);
                                const val = localStorage.getItem(key);
                                if (val && val.includes('eyJ')) {  // JWT tokens start with eyJ
                                    try {
                                        const obj = JSON.parse(val);
                                        if (obj.access_token) return obj.access_token;
                                        if (obj.token) return obj.token;
                                    } catch(e) {
                                        // If value contains eyJ, it might be the token itself
                                        if (val.startsWith('eyJ')) return val;
                                    }
                                }
                            }
                            
                            return null;
                        }""")
                        
                        if token:
                            self.bearer_token = token
                            logger.info("Bearer token extracted from storage")
                        else:
                            logger.info("Token not in storage, checking captured network token")
                            
                    except Exception as e:
                        logger.debug(f"Could not extract token from storage: {e}")
                    
                    # Use captured token from network if available
                    if captured_token['value'] and not self.bearer_token:
                        self.bearer_token = captured_token['value']
                        logger.info("Using token captured from network request")
                    
                    # Verify we have session cookies
                    if self.cookies:
                        logger.info("Authentication successful - cookies extracted")
                        return True
                    else:
                        logger.error("No cookies extracted after login")
                        return False
                        
                except PlaywrightTimeout as e:
                    logger.error(f"Timeout during authentication: {e}")
                    return False
                except Exception as e:
                    logger.error(f"Error during browser authentication: {e}")
                    return False
                finally:
                    browser.close()
                    
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid session, re-authenticate if needed"""
        if not self.cookies:
            return self.authenticate()
        return True
    
    def fetch_schedule(self, start_date: datetime, end_date: datetime) -> Optional[str]:
        """
        Fetch working hours schedule (HORAIRE) from Chronos
        Returns XML response as string
        """
        if not self._ensure_authenticated():
            logger.error("Cannot fetch schedule - authentication failed")
            return None
        
        try:
            start_str = start_date.strftime('%d/%m/%Y')
            end_str = end_date.strftime('%d/%m/%Y')
            
            url = f"{self.base_url}/chronos.wsc/asical.html"
            params = {
                'infos': 'PLG',
                'mat': self.username,
                'usr': self.username,
                'lstabsprf': '*',
                'items': 'HORAIRE',
                'start': start_str,
                'end': end_str
            }
            
            headers = {
                'Accept': 'application/xml, text/xml, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            # Add bearer token if available
            if self.bearer_token:
                headers['Authorization'] = f'Bearer {self.bearer_token}'
            
            response = self.session.get(url, params=params, headers=headers, cookies=self.cookies)
            response.raise_for_status()
            
            logger.info(f"Fetched schedule from {start_str} to {end_str}")
            return response.text
            
        except Exception as e:
            logger.error(f"Error fetching schedule: {e}")
            return None
    
    def fetch_absences(self, start_date: datetime, end_date: datetime) -> Optional[str]:
        """
        Fetch absences (RTT, CA, etc.) from Chronos
        Returns XML response as string
        """
        if not self._ensure_authenticated():
            logger.error("Cannot fetch absences - authentication failed")
            return None
        
        try:
            start_str = start_date.strftime('%d/%m/%Y')
            end_str = end_date.strftime('%d/%m/%Y')
            
            url = f"{self.base_url}/chronos.wsc/asical.html"
            params = {
                'infos': 'COD',
                'mat': self.username,
                'usr': self.username,
                'lstabsprf': 'CAP,CPA,CRM,CTJ,DC,DEL,DS,EM,MAL,RCA,RCF,RCH,RCJ,RCN,RHS,AA,AAQ,ANJ,ASA,AT,CA,CAM,CAR,CDC,CEM,CET,CTH,CF,CHS,CM,CMA,CME,COB,CP,CPE,CPP,CSF,CSS,DON,EXC,F,FO,GNR,JNT,MAT,NE,OAJ,OAT,PAT,RCD,RF,RH,RTT',
                'items': 'ABSENCEJ',
                'start': start_str,
                'end': end_str
            }
            
            headers = {
                'Accept': 'application/xml, text/xml, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            # Add bearer token if available
            if self.bearer_token:
                headers['Authorization'] = f'Bearer {self.bearer_token}'
            
            response = self.session.get(url, params=params, headers=headers, cookies=self.cookies)
            response.raise_for_status()
            
            logger.info(f"Fetched absences from {start_str} to {end_str}")
            return response.text
            
        except Exception as e:
            logger.error(f"Error fetching absences: {e}")
            return None
    
    def fetch_activities(self, start_date: datetime, end_date: datetime) -> Optional[str]:
        """
        Fetch activities from Chronos
        Returns XML response as string
        """
        if not self._ensure_authenticated():
            logger.error("Cannot fetch activities - authentication failed")
            return None
        
        try:
            start_str = start_date.strftime('%d/%m/%Y')
            end_str = end_date.strftime('%d/%m/%Y')
            
            url = f"{self.base_url}/chronos.wsc/asical.html"
            params = {
                'infos': 'COD',
                'mat': self.username,
                'usr': self.username,
                'lstabsprf': '*',
                'items': 'ACTIVITES',
                'start': start_str,
                'end': end_str
            }
            
            headers = {
                'Accept': 'application/xml, text/xml, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            # Add bearer token if available
            if self.bearer_token:
                headers['Authorization'] = f'Bearer {self.bearer_token}'
            
            response = self.session.get(url, params=params, headers=headers, cookies=self.cookies)
            response.raise_for_status()
            
            logger.info(f"Fetched activities from {start_str} to {end_str}")
            return response.text
            
        except Exception as e:
            logger.error(f"Error fetching activities: {e}")
            return None
