from discord.ext import tasks
import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import discord
import datetime

# CREDENTIALS = {
#     "installed":
#     {
#         "client_id":os.environ['CLIENT_ID'],
#         "project_id":os.environ['PROJECT_ID'],
#         "auth_uri":os.environ['AUTH_URI'],
#         "token_uri":os.environ['TOKEN_URI'],
#         "auth_provider_x509_cert_url":os.environ['AUTH_PROVIDER_X509_CERT_URL'],
#         "client_secret":os.environ['CLIENT_SECRET'],
#         "redirect_uris":[os.environ['REDIRECT_URIS'],"http://localhost"]
#     }
# }

# TOKEN = {
#     "token": os.environ['TOEKN'],
#     "refresh_token": os.environ['REFRESH_TOKEN'], 
#     "token_uri": os.environ['TOKEN_URI'], 
#     "client_id": os.environ['CLIENT_ID'], 
#     "client_secret": os.environ['CLIENT_SECRET'],
#     "scopes": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/calendar.readonly"], 
#     "expiry": os.environ['EXPIRY']
# }

CREDENTIALS = os.environ['CREDENTIALS']
TOKEN = os.environ['TOKEN_GOOGLE']
print(CREDENTIALS)
print(TOKEN)

DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/calendar.readonly']
MAX_RESULT = 100

class NotifyClalendarClient(discord.Client):
    def __init__(self, discord_token=DISCORD_TOKEN, scopes=SCOPES, max_result=MAX_RESULT, credentials=CREDENTIALS, token=TOKEN):
        super().__init__()
        self.discord_token = discord_token
        with open('./token_google.json', 'w') as f:
            f.write(str(token).replace("'", '"'))
        with open('./credential_google.json', 'w') as f:
            f.write(str(credentials).replace("'", '"'))
        creds = None
        self.max_result = max_result
        self.user_Id = 'me'
        if os.path.exists('./token_google.json'):
                creds = Credentials.from_authorized_user_file('./token_google.json', scopes)
        if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        './credential_google.json', scopes)
                    creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                with open('./token_google.json', 'w') as token:
                    token.write(creds.to_json())

        self.service_gmail = build('gmail', 'v1', credentials=creds)
        self.service_calendar = build('calendar', 'v3', credentials=creds)

    async def on_ready(self):
        self.get_unread_mail.start()
        for channel in self.get_all_channels():
            if str(channel.category) == 'テキストチャンネル' and channel.name == '一般':
                await channel.send('起動しました')

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith('明日の予定'):
            result = self.get_tomorrow_schedule()
            await message.channel.send(result)

        if message.content.startswith('メール確認'):
            result = self.get_unread_mail()
            await message.channel.send(result)

    def get_tomorrow_schedule(self):
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        result = '明日の予定は、'
        events_result = self.service_calendar.events().list(
            calendarId='primary', timeMin=now, maxResults=self.max_result, 
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = [i['summary'] for i in events_result['items']]
        result += 'と、'.join(events)
        return result

    @tasks.loop(hours=24)
    async def get_unread_mail(self):
        messages = self.service_gmail.users().messages().list(userId=self.user_Id).execute()
        result = []
        channel = None
        for c in self.get_all_channels():
            if str(c.category) == 'テキストチャンネル' and c.name == '一般':
                channel = c
        for i, message in enumerate(messages['messages'][:10]):
            result_message = self.service_gmail.users().messages().get(userId=self.user_Id,id=message['id']).execute()
            labels = result_message['labelIds']
            if 'UNREAD' in labels:
                for header in result_message['payload']['headers']:
                    if header['name'] == 'Subject':
                        result.append(f"・件名: {header['value']}\n")
        if result != []:
            result.insert(0, '@everyone\n以下、未読メールです。\nhttps://mail.google.com/mail/u/1/?ogbl#inbox\n')
            result.insert(1, f'{"="*50}\n')
            await channel.send(f"".join(result))
        else:
            await channel.send('新着メールはありません')

    def run_bot(self):
        self.run(self.discord_token)

if __name__ == "__main__":
    client = NotifyClalendarClient()
    client.run_bot()