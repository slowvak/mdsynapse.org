from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file(
      './n8n/noted-sled-489022-a2-2d59b1c03f2f.json',
      scopes=['https://www.googleapis.com/auth/drive.readonly']
)
creds.refresh(__import__('google.auth.transport.requests', fromlist=['Request']).Request())
print(creds.token)


