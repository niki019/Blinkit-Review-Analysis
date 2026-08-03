import os
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Define scopes required for Docs and Gmail APIs
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose'
]

class GoogleWorkspaceClient:
    def __init__(self, credentials_path=None, token_path=None):
        # Resolve paths relative to the script directory if not provided
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.credentials_path = credentials_path or os.path.join(current_dir, 'credentials.json')
        self.token_path = token_path or os.path.join(current_dir, 'token.json')
        
        self.creds = self._authenticate()
        self.docs_service = build('docs', 'v1', credentials=self.creds)
        self.gmail_service = build('gmail', 'v1', credentials=self.creds)

    def _authenticate(self):
        creds = None
        
        # 1. Try to load token from environment variable (Vercel)
        if 'GOOGLE_TOKEN_JSON' in os.environ:
            import json
            token_info = json.loads(os.environ['GOOGLE_TOKEN_JSON'])
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        # 2. Try to load token from file system
        elif os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    # Token invalid or expired refresh token; delete and re-auth
                    if os.path.exists(self.token_path):
                        os.remove(self.token_path)
                    creds = self._trigger_new_flow()
            else:
                creds = self._trigger_new_flow()
                
            # Save the credentials for next time (if filesystem is writable)
            try:
                with open(self.token_path, 'w') as token_file:
                    token_file.write(creds.to_json())
            except OSError:
                # Read-only filesystem (like Vercel), ignore saving
                pass
                
        return creds

    def _trigger_new_flow(self):
        # On Vercel, we can't run the interactive flow. We must crash if token is missing.
        if 'VERCEL' in os.environ or os.environ.get('ENVIRONMENT') == 'production':
            raise RuntimeError("Missing valid GOOGLE_TOKEN_JSON environment variable in production. Cannot run interactive OAuth flow.")
            
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Google OAuth credentials file not found at {self.credentials_path}.\n"
                f"Please verify credentials.json is placed in mcp_server folder."
            )
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)
        return creds

    def append_markdown_to_doc(self, doc_id: str, title: str, markdown_content: str) -> str:
        """
        Appends formatted content to a Google Doc using a single batchUpdate.
        Converts headings, bullet lists, blockquotes, and normal paragraphs.
        Returns the direct browser heading anchor URL.
        """
        # 1. Fetch document metadata to find the end index
        doc = self.docs_service.documents().get(documentId=doc_id).execute()
        body = doc.get('body', {})
        content = body.get('content', [])
        # The body ends at the endIndex of the last element - 1 (to preserve final newline)
        end_index = content[-1].get('endIndex', 1) - 1
        
        # 2. Parse markdown into sections and track character ranges relative to end_index
        full_text = ""
        requests = []
        
        # We start by appending the section title (dated header)
        dated_title = f"\n\n{title}\n"
        full_text += dated_title
        title_start = end_index + 2  # Skip leading newlines
        title_end = end_index + len(dated_title)
        
        # Style the main title heading
        requests.append({
            'updateParagraphStyle': {
                'range': {'startIndex': title_start, 'endIndex': title_end},
                'paragraphStyle': {'namedStyleType': 'HEADING_2'},
                'fields': 'namedStyleType'
            }
        })
        
        current_idx = end_index + len(dated_title)
        lines = markdown_content.split('\n')
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
                
            # Handle Headings (e.g. ### Section)
            if line_str.startswith('### '):
                text = line_str[4:] + "\n"
                full_text += text
                start, end = current_idx, current_idx + len(text)
                requests.append({
                    'updateParagraphStyle': {
                        'range': {'startIndex': start, 'endIndex': end},
                        'paragraphStyle': {'namedStyleType': 'HEADING_3'},
                        'fields': 'namedStyleType'
                    }
                })
                current_idx = end
                
            # Handle Bullet points (e.g. * Item or - Item)
            elif line_str.startswith('* ') or line_str.startswith('- '):
                text = line_str[2:] + "\n"
                full_text += text
                start, end = current_idx, current_idx + len(text)
                requests.append({
                    'createParagraphBullets': {
                        'range': {'startIndex': start, 'endIndex': end},
                        'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                    }
                })
                current_idx = end
                
            # Handle Quotes (e.g. > Quote or "Quote")
            elif line_str.startswith('> ') or (line_str.startswith('“') and line_str.endswith('”')) or (line_str.startswith('"') and line_str.endswith('"')):
                text = (line_str[2:] if line_str.startswith('> ') else line_str) + "\n"
                full_text += text
                start, end = current_idx, current_idx + len(text)
                requests.append({
                    'updateTextStyle': {
                        'range': {'startIndex': start, 'endIndex': end},
                        'textStyle': {'italic': True, 'foregroundColor': {'color': {'rgbColor': {'red': 0.4, 'green': 0.4, 'blue': 0.4}}}},
                        'fields': 'italic,foregroundColor'
                    }
                })
                current_idx = end
                
            # Regular paragraph
            else:
                text = line_str + "\n"
                full_text += text
                start, end = current_idx, current_idx + len(text)
                requests.append({
                    'updateParagraphStyle': {
                        'range': {'startIndex': start, 'endIndex': end},
                        'paragraphStyle': {'namedStyleType': 'NORMAL_TEXT'},
                        'fields': 'namedStyleType'
                    }
                })
                current_idx = end

        # Insert the accumulated string at the end of the document first
        insert_request = {
            'insertText': {
                'location': {'index': end_index},
                'text': full_text
            }
        }
        
        # Prepend the insertRequest so it runs before styling requests
        requests.insert(0, insert_request)
        
        # Execute all formatting in a single batchUpdate
        self.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        # 3. Retrieve the document again to extract the Google Doc heading h.ID for deep linking
        doc = self.docs_service.documents().get(documentId=doc_id).execute()
        body_elements = doc.get('body', {}).get('content', [])
        
        heading_id = None
        for element in body_elements:
            paragraph = element.get('paragraph')
            if paragraph:
                style = paragraph.get('paragraphStyle', {})
                # Match heading h.ID if style matches HEADING_2 and contains our title
                if style.get('namedStyleType') == 'HEADING_2':
                    raw_text = "".join([run.get('textRun', {}).get('content', '') 
                                       for run in paragraph.get('elements', [])]).strip()
                    if title in raw_text:
                        heading_id = style.get('headingId')
                        break
                        
        if heading_id:
            return f"https://docs.google.com/document/d/{doc_id}/edit#heading=h.{heading_id}"
        else:
            return f"https://docs.google.com/document/d/{doc_id}/edit"

    def send_gmail_message(self, recipient: str, subject: str, body_html: str) -> str:
        """
        Sends an HTML email message via the Gmail API.
        Returns the Gmail Message ID.
        """
        message = MIMEMultipart('alternative')
        message['to'] = recipient
        message['from'] = 'me'
        message['subject'] = subject
        
        # Create text fallback from HTML
        text_fallback = re.sub('<[^<]+?>', '', body_html)
        
        part1 = MIMEText(text_fallback, 'plain')
        part2 = MIMEText(body_html, 'html')
        
        message.attach(part1)
        message.attach(part2)
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw_message}
        
        result = self.gmail_service.users().messages().send(userId='me', body=body).execute()
        return result.get('id', '')
