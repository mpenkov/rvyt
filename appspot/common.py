import os
import os.path as P

import gdata.youtube
import gdata.youtube.service
import gdata.service
from gdata.auth import OAuthToken, OAuthInputParams

from oauth2client.appengine import oauth2decorator_from_clientsecrets

# CLIENT_SECRETS, name of a file containing the OAuth 2.0 information for this
# application, including client_id and client_secret, which are found
# on the API Access tab on the Google APIs
# Console <http://code.google.com/apis/console>
CLIENT_SECRETS = P.join(P.dirname(__file__), 'client_secrets.json')
# Helpful message to display in the browser if the CLIENT_SECRETS file
# is missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
<h1>Warning: Please configure OAuth 2.0</h1>
<p>
To make this sample run you will need to populate the client_secrets.json file
found at:
</p>
<p>
<code>%s</code>.
</p>
<p>with information found on the <a
href="https://code.google.com/apis/console">APIs Console</a>.
</p>
""" % CLIENT_SECRETS

OAUTH_METHOD = gdata.oauth.OAuthSignatureMethod_HMAC_SHA1
GDATA_URL = 'http://gdata.youtube.com' 

USER_AGENT = 'http://rvytpl.appspot.com'
YOUTUBE_DEVELOPER_KEY = 'AI39si4TTIXb-M4G0rhm4kG1eYowjK2tlHZlrxGS4vOegXEK0oS3LRrmx-PMbrMRVtfHqpJ6gG60qQ2U4w6X_DnqfmkuqtTDvA'

def create_decorator():
    decorator = oauth2decorator_from_clientsecrets(
        CLIENT_SECRETS,
        GDATA_URL,
        MISSING_CLIENT_SECRETS_MESSAGE)
    return decorator

class MyOAuthToken(OAuthToken):
    """This is a an ugly hack to make the old 1.0 API work with OAuth2."""
    def __init__(self, *args):
        OAuthToken.__init__(self, *args)

    def GetAuthHeader(self, http_method, http_url, realm=''):
        #
        # http://code.google.com/apis/youtube/2.0/developers_guide_protocol_oauth2.html#OAuth2_Client_Libraries
        #
        return { 'Authorization' : 'Bearer %s' % self.key }

def credentials_to_oauth_token(credentials):
    """
    Create an OAuthToken that can be used with the GData 1.0 API from a
    Credentials object.
    """
    params = OAuthInputParams(
            OAUTH_METHOD,
            credentials.client_id,
            credentials.client_secret)
    token = MyOAuthToken(
            credentials.access_token, 
            credentials.client_secret, 
            GDATA_URL,
            params)    
    return token

def youtube_login(token):
    """Login to YouTube using an OAuth2 token."""
    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.SetOAuthToken(token)
    yt_service.developer_key = YOUTUBE_DEVELOPER_KEY
    yt_service.source = USER_AGENT
    return yt_service


