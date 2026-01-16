#!/usr/bin/env python3
"""
Test script to simulate Maileroo webhook payload locally
Run this while your bot is running to test the email webhook endpoint
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
WEBHOOK_URL = "http://localhost:8081/email-webhook"  # Change port if needed

def test_email(channel_name="general"):
    """Test sending an email reply to a Discord channel"""
    
    # Format subject like the bot sends: [Discord] #channel-name - author-name
    subject = f"Re: [Discord] #{channel_name} - sophi_a"
    
    # Sample Maileroo webhook payload
    payload = {
        "_id": "677730adac1b7a32de362ccd",
        "message_id": "test123@example.com",
        "domain": "mail.maileroo.com",
        "envelope_sender": "test@example.com",
        "recipients": [
            "bot@9b6d05a69dadf0d2.maileroo.org"
        ],
        "headers": {
            "Content-Type": [
                "text/plain; charset=UTF-8"
            ],
            "Date": [
                datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
            ],
            "From": [
                "Sophia Wang <swang@student.fsaps.org>"
            ],
            "Message-Id": [
                "<test123@example.com>"
            ],
            "Mime-Version": [
                "1.0"
            ],
            "Subject": [
                subject
            ],
            "To": [
                "bot@9b6d05a69dadf0d2.maileroo.org"
            ]
        },
        "body": {
            "plaintext": "This is a test email reply! It should appear in the #{} channel with the 'sophia' webhook.\n\nTesting the email-to-Discord forwarding feature.".format(channel_name),
            "stripped_plaintext": "This is a test email reply! It should appear in the #{} channel with the 'sophia' webhook.\n\nTesting the email-to-Discord forwarding feature.".format(channel_name),
            "html": "<p>This is a test email reply!</p>",
            "stripped_html": "<p>This is a test email reply!</p>",
            "other_parts": None,
            "raw_mime": {
                "url": "https://example.com/raw.mime",
                "size": 1024
            }
        },
        "attachments": [],
        "spf_result": "pass",
        "dkim_result": True,
        "is_dmarc_aligned": True,
        "is_spam": False,
        "deletion_url": "https://inbound-api.maileroo.net/email/test123/delete",
        "validation_url": "https://inbound-api.maileroo.net/validate-callback/test123/validation",
        "processed_at": int(datetime.now().timestamp())
    }
    
    print(f"🧪 Testing email webhook...")
    print(f"   URL: {WEBHOOK_URL}")
    print(f"   Subject: {subject}")
    print(f"   Expected Channel: #{channel_name}")
    print()
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        print(f"📊 Response Status: {response.status_code}")
        try:
            response_data = response.json()
            print(f"📊 Response Body: {json.dumps(response_data, indent=2)}")
        except:
            print(f"📊 Response Body: {response.text}")
        
        if response.status_code == 200:
            print(f"\n✅ SUCCESS! Check your Discord #{channel_name} channel.")
            print(f"   The message should appear from the 'sophia' webhook with '*sent from my email'")
        elif response.status_code == 503:
            print(f"\n⚠️  Bot not ready yet. Wait a few seconds and try again.")
        else:
            print(f"\n❌ ERROR: Received status code {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Could not connect to {WEBHOOK_URL}")
        print("   Make sure your bot is running: python main.py")
    except requests.exceptions.Timeout:
        print(f"\n⏱️  Timeout: Request took too long")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Get channel name from command line or use default
    channel = "test"
    
    print("=" * 60)
    print("Email Webhook Test Script")
    print("=" * 60)
    print()
    print("This script simulates a Maileroo webhook for testing.")
    print()
    
    test_email(channel)
    
    print()
    print("=" * 60)
    if len(sys.argv) == 1:
        print("Usage: python test_webhook.py [channel-name]")
        print("Example: python test_webhook.py general")
        print("=" * 60)
