import discord
from discord.ext import commands
import os
import asyncio
import threading
from dotenv import load_dotenv
from flask import Flask, request
import aiohttp
import json
import re
from datetime import datetime

load_dotenv()
token = os.getenv("token")

# Maileroo API configuration
maileroo_api_key = os.getenv("MAILEROO_API_KEY")
maileroo_from_email = os.getenv("MAILEROO_FROM_EMAIL")
maileroo_from_name = os.getenv("MAILEROO_FROM_NAME", "Discord Bot")
maileroo_to_email = os.getenv("MAILEROO_TO_EMAIL")
maileroo_api_url = os.getenv("MAILEROO_API_URL", "https://smtp.maileroo.com/api/v2/emails")

# Check if Maileroo credentials are configured
if maileroo_api_key and maileroo_from_email and maileroo_to_email:
    email_configured = True
    print("Maileroo API configured")
else:
    email_configured = False
    print("Warning: Maileroo API credentials not found. Email functionality will be disabled.")

# Discord channel configuration for receiving emails via Maileroo webhook
discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")  # Fallback channel ID if subject parsing fails
discord_guild_id = os.getenv("DISCORD_GUILD_ID", "1405628370301091860")  # Guild ID to search channels in

if discord_guild_id:
    email_to_discord_configured = True
    print("Email-to-Discord forwarding configured (via Maileroo webhook, routing by subject)")
else:
    email_to_discord_configured = False
    print("Warning: Discord guild ID not found. Email-to-Discord forwarding will be disabled.")

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content and process commands

# Configure Discord client
client = commands.Bot(command_prefix="soph ", intents=intents, case_insensitive=True)

async def isSophia(ctx):
  return ctx.author.id == 704038199776903209 or ctx.author.id == 701792352301350973

# Sophia's user IDs (primary and secondary)
SOPHIA_USER_IDS = [704038199776903209, 701792352301350973]
PRIMARY_SOPHIA_ID = 704038199776903209  # Primary user ID for webhook avatar

# Store bot's event loop for use in Flask routes
bot_loop = None
 
client.snipes = {}

@client.event
async def on_ready():
  global bot_loop
  # Ensure bot_loop is set (it should already be set in run_bot, but just in case)
  if bot_loop is None:
    bot_loop = asyncio.get_running_loop()
    print(f'[on_ready] Bot loop was None, setting it now: {bot_loop}')
  print(f'[on_ready] Bot is ready!')
  print(f'[on_ready] Bot user: {client.user} (ID: {client.user.id})')
  print(f'[on_ready] Bot loop stored: {bot_loop is not None}')
  print(f'[on_ready] Bot loop: {bot_loop}')
  print(f'[on_ready] Bot loop closed: {bot_loop.is_closed() if bot_loop else "N/A"}')
  print(f'[on_ready] Connected to {len(client.guilds)} guild(s)')
  for guild in client.guilds:
    print(f'[on_ready]   - {guild.name} (ID: {guild.id})')
  await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=" the AI & Data Science Club!"))
  print(f'[on_ready] Presence updated successfully')

async def send_email(subject, message_content):
    """Send email notification using Maileroo API"""
    if not email_configured:
        print("Email not configured - skipping email send")
        return
    
    try:
        # Prepare Maileroo API payload according to their API format
        payload = {
            "from": {
                "address": maileroo_from_email,
                "display_name": maileroo_from_name
            },
            "to": {
                "address": maileroo_to_email
            },
            "subject": subject or "Discord Message Notification",
            "plain": message_content  # Using plain text format
        }
        
        headers = {
            "Authorization": f"Bearer {maileroo_api_key}",
            "Content-Type": "application/json"
        }
        
        # Send email via Maileroo API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                maileroo_api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_data = await response.json()
                
                if response.status == 200 and response_data.get("success"):
                    reference_id = response_data.get("data", {}).get("reference_id", "N/A")
                    print(f"Email sent successfully via Maileroo. Reference ID: {reference_id}")
                    return True
                else:
                    error_msg = response_data.get("message", "Unknown error")
                    print(f"Maileroo API error: {response.status} - {error_msg}")
                    return False
            
    except aiohttp.ClientError as e:
        print(f"Network error sending email via Maileroo: {e}")
        return False
    except Exception as e:
        print(f"Error sending email via Maileroo: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_channel_from_subject(subject):
    """Parse email subject to find the Discord channel name and return the channel"""
    print(f'[find_channel_from_subject] Looking for channel from subject: {subject}')
    # Remove "Re:" or "RE:" prefix if present
    subject_clean = re.sub(r'^(Re|RE):\s*', '', subject, flags=re.IGNORECASE).strip()
    print(f'[find_channel_from_subject] Cleaned subject: {subject_clean}')
    
    # Look for pattern: [Discord] #channel-name - author-name
    match = re.search(r'\[Discord\]\s*#([^\s-]+)', subject_clean, re.IGNORECASE)
    if match:
        channel_name = match.group(1)
        print(f'[find_channel_from_subject] Found channel name from pattern: {channel_name}')
        # Find the channel in the guild
        guild = client.get_guild(int(discord_guild_id))
        if guild:
            print(f'[find_channel_from_subject] Guild found: {guild.name} (ID: {guild.id})')
            print(f'[find_channel_from_subject] Searching in {len(guild.text_channels)} text channels')
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                print(f'[find_channel_from_subject] Channel found: {channel.name} (ID: {channel.id})')
                return channel
            else:
                print(f'[find_channel_from_subject] Channel \'{channel_name}\' not found in guild')
                print(f'[find_channel_from_subject] Available channels: {[c.name for c in guild.text_channels]}')
        else:
            print(f'[find_channel_from_subject] Guild not found for ID: {discord_guild_id}')
    else:
        print(f'[find_channel_from_subject] No channel pattern found in subject')
    
    # Fallback: try to find channel by ID if configured
    if discord_channel_id:
        print(f'[find_channel_from_subject] Trying fallback channel ID: {discord_channel_id}')
        channel = client.get_channel(int(discord_channel_id))
        if channel:
            print(f'[find_channel_from_subject] Fallback channel found: {channel.name} (ID: {channel.id})')
            return channel
        else:
            print(f'[find_channel_from_subject] Fallback channel ID not found')
    
    print(f'[find_channel_from_subject] No channel found for subject: {subject}')
    return None

async def get_or_create_sophia_webhook(channel):
    """Get or create a webhook named 'sophia' in the channel"""
    print(f'[get_or_create_sophia_webhook] Starting for channel: {channel.name} (ID: {channel.id})')
    try:
        # Try to find existing webhook named "sophia"
        print(f'[get_or_create_sophia_webhook] Fetching webhooks from channel...')
        webhooks = [webhook async for webhook in channel.webhooks]
        print(f'[get_or_create_sophia_webhook] Found {len(webhooks)} webhook(s) in channel')
        for webhook in webhooks:
            print(f'[get_or_create_sophia_webhook]   - Webhook: {webhook.name} (ID: {webhook.id})')
        
        sophia_webhook = discord.utils.get(webhooks, name="sophia")
        
        if sophia_webhook:
            print(f'[get_or_create_sophia_webhook] Found existing "sophia" webhook: {sophia_webhook.id}')
            return sophia_webhook
        
        print(f'[get_or_create_sophia_webhook] "sophia" webhook not found, creating new one...')
        # Webhook doesn't exist, create one with Sophia's name and avatar
        guild = channel.guild
        print(f'[get_or_create_sophia_webhook] Guild: {guild.name} (ID: {guild.id})')
        
        sophia_user = guild.get_member(PRIMARY_SOPHIA_ID)
        print(f'[get_or_create_sophia_webhook] Looking for Sophia user (ID: {PRIMARY_SOPHIA_ID})')
        
        if sophia_user:
            avatar_url = sophia_user.display_avatar.url
            print(f'[get_or_create_sophia_webhook] Sophia user found: {sophia_user.name}, avatar URL: {avatar_url}')
        else:
            avatar_url = None
            print(f'[get_or_create_sophia_webhook] Sophia user not found in guild, using no avatar')
        
        # Create the webhook
        print(f'[get_or_create_sophia_webhook] Creating webhook...')
        webhook = await channel.create_webhook(
            name="sophia",
            avatar=avatar_url,
            reason="Created for email-to-Discord forwarding"
        )
        print(f'[get_or_create_sophia_webhook] Webhook created successfully: {webhook.id}')
        return webhook
        
    except discord.errors.Forbidden:
        print(f'[get_or_create_sophia_webhook] ERROR: Bot doesn\'t have permission to manage webhooks in channel {channel.name}')
        import traceback
        traceback.print_exc()
        return None
    except Exception as e:
        print(f'[get_or_create_sophia_webhook] ERROR: {e}')
        import traceback
        traceback.print_exc()
        return None

async def send_email_to_discord(from_email, subject, body, date=None, attachments=None, 
                                 envelope_sender=None, recipients=None, domain=None, is_spam=False):
    """Send email content to Discord channel based on subject line"""
    print(f'[send_email_to_discord] ===== FUNCTION CALLED =====')
    print(f'[send_email_to_discord] Called with subject: {subject}')
    print(f'[send_email_to_discord] From: {from_email}')
    print(f'[send_email_to_discord] Body length: {len(body) if body else 0} chars')
    print(f'[send_email_to_discord] Date: {date}')
    print(f'[send_email_to_discord] Attachments: {len(attachments) if attachments else 0}')
    print(f'[send_email_to_discord] Is spam: {is_spam}')
    print(f'[send_email_to_discord] Email-to-Discord configured: {email_to_discord_configured}')
    print(f'[send_email_to_discord] Client ready: {client.is_ready()}')
    
    if not email_to_discord_configured:
        print(f'[send_email_to_discord] ERROR: Email-to-Discord not configured')
        return
    
    try:
        # Find channel from subject line
        print(f'[send_email_to_discord] Looking for channel from subject: {subject}')
        channel = find_channel_from_subject(subject)
        
        if channel is None:
            print(f'[send_email_to_discord] ERROR: Could not find Discord channel from subject \'{subject}\'')
            return
        
        print(f'[send_email_to_discord] Found channel: {channel.name} (ID: {channel.id})')
        
        # Build plain text message
        message_parts = [body, "\n\n> sent from my email"]
        full_message = "".join(message_parts)
        print(f'[send_email_to_discord] Full message length: {len(full_message)} chars')
        
        # Get or create the "sophia" webhook
        print(f'[send_email_to_discord] Getting/creating webhook for channel {channel.name}')
        webhook = await get_or_create_sophia_webhook(channel)
        
        if webhook:
            print(f'[send_email_to_discord] Using webhook: {webhook.name} (ID: {webhook.id})')
            # Discord message limit is 2000 characters
            if len(full_message) > 2000:
                print(f'[send_email_to_discord] Message too long, splitting into chunks...')
                # Split into chunks
                chunks = []
                current_chunk = ""
                for line in full_message.split('\n'):
                    if len(current_chunk) + len(line) + 1 <= 1900:
                        current_chunk += line + '\n'
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                if current_chunk:
                    chunks.append(current_chunk.strip())
                print(f'[send_email_to_discord] Split into {len(chunks)} chunk(s)')
                
                print(f'[send_email_to_discord] Sending first chunk ({len(chunks[0])} chars)...')
                await webhook.send(content=chunks[0])
                for i, chunk in enumerate(chunks[1:], 1):
                    print(f'[send_email_to_discord] Sending chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...')
                    await webhook.send(content=chunk)
            else:
                print(f'[send_email_to_discord] Sending single message...')
                await webhook.send(content=full_message)
            print(f'[send_email_to_discord] Message sent successfully via webhook')
        else:
            print(f'[send_email_to_discord] WARNING: Could not use webhook, sending as bot instead')
            # Fallback: send as bot if webhook creation fails
            if len(full_message) > 2000:
                print(f'[send_email_to_discord] Message too long, splitting into chunks (bot fallback)...')
                chunks = []
                current_chunk = ""
                for line in full_message.split('\n'):
                    if len(current_chunk) + len(line) + 1 <= 1900:
                        current_chunk += line + '\n'
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                if current_chunk:
                    chunks.append(current_chunk.strip())
                print(f'[send_email_to_discord] Split into {len(chunks)} chunk(s)')
                
                print(f'[send_email_to_discord] Sending first chunk as bot ({len(chunks[0])} chars)...')
                await channel.send(content=chunks[0])
                for i, chunk in enumerate(chunks[1:], 1):
                    print(f'[send_email_to_discord] Sending chunk {i+1}/{len(chunks)} as bot ({len(chunk)} chars)...')
                    await channel.send(content=chunk)
            else:
                print(f'[send_email_to_discord] Sending single message as bot...')
                await channel.send(content=full_message)
            print(f'[send_email_to_discord] Message sent successfully as bot')
        
        print(f'[send_email_to_discord] Email from {from_email} forwarded to Discord channel {channel.name} (ID: {channel.id})')
    except Exception as e:
        print(f'[send_email_to_discord] ERROR sending email to Discord: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        raise  # Re-raise so the future callback can catch it

@client.event
async def on_message(message):
  if message.author == client.user:
    return
  # Check if message is in the specific guild
  if message.guild and message.guild.id == 1405628370301091860:
    print(message.content, message.channel.name, message.author.name)

    # Build a nicely formatted email
    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    subject = f"[Discord] #{message.channel.name} - {message.author.name}"
    email_message = (
      f"{message.content}\n"
      "-------------------\n"
      f"Channel: #{message.channel.name} (ID: {message.channel.id})\n"
      f"Author : {message.author} (ID: {message.author.id})\n"
      f"Time   : {timestamp}\n"
      f"Link   : {message.jump_url}\n"
      "\n"
    )
    await send_email(subject, email_message)
  await client.process_commands(message)

@client.event
async def on_command_error(ctx, error):
    print("ERROR:")
    print(error)
    if isinstance(error, discord.ext.commands.UnexpectedQuoteError) or isinstance(error, discord.ext.commands.InvalidEndOfQuotedStringError):
        return await ctx.send("Sorry, it appears that your quotation marks are misaligned, and I can't read your query.")
    if isinstance(error, discord.ext.commands.ExpectedClosingQuoteError):
        return await ctx.send("Oh. I was expecting you were going to close out your command with a quote somewhere, but never found it!")
    if isinstance(error, discord.ext.commands.MissingRequiredArgument):
        return await ctx.send("Oops, you are missing a required argument in the command.")
    if isinstance(error, discord.ext.commands.ArgumentParsingError):
        return await ctx.send("Sorry, I had trouble parsing one of your arguments.")
    if isinstance(error, discord.ext.commands.TooManyArguments):
        return await ctx.send("Woahhh!! Too many arguments for this command!")
    if isinstance(error, discord.ext.commands.BadArgument) or isinstance(error, discord.ext.commands.BadUnionArgument):
        return await ctx.send("Sorry, I'm having trouble reading one of the arguments you just used. Try again!")
    if isinstance(error, discord.ext.commands.CheckAnyFailure):
        return await ctx.send("It looks like you aren't able to run this command, sorry.")
    if isinstance(error, discord.ext.commands.PrivateMessageOnly):
        return await ctx.send("Pssttt. You're going to have to DM me to run this command!")
    if isinstance(error, discord.ext.commands.NoPrivateMessage):
        return await ctx.send("Ope. You can't run this command in the DM's!")
    if isinstance(error, discord.ext.commands.NotOwner):
        return await ctx.send("Oof. You have to be the bot's master to run that command!")
    if isinstance(error, discord.ext.commands.MissingPermissions) or isinstance(error, discord.ext.commands.BotMissingPermissions):
        return await ctx.send("Er, you don't have the permissions to run this command.")
    if isinstance(error, discord.ext.commands.MissingRole) or isinstance(error, discord.ext.commands.BotMissingRole):
        return await ctx.send("Oh no... you don't have the required role to run this command.")
    if isinstance(error, discord.ext.commands.MissingAnyRole) or isinstance(error, discord.ext.commands.BotMissingAnyRole):
        return await ctx.send("Oh no... you don't have the required role to run this command.")
    if isinstance(error, discord.ext.commands.NSFWChannelRequired):
        return await ctx.send("Uh... this channel can only be run in a NSFW channel... sorry to disappoint.")
    if isinstance(error, discord.ext.commands.ConversionError):
        return await ctx.send("Oops, there was a bot error here, sorry about that.")
    if isinstance(error, discord.ext.commands.UserInputError):
        return await ctx.send("Hmmm... I'm having trouble reading what you're trying to tell me.")
    if isinstance(error, discord.ext.commands.CommandNotFound):
        return await ctx.send("Sorry, I couldn't find that command.")
    if isinstance(error, discord.ext.commands.CheckFailure):
        return await ctx.send("Sorry, but I don't think you can run that command.")
    if isinstance(error, discord.ext.commands.DisabledCommand):
        return await ctx.send("Sorry, but this command is disabled.")
    if isinstance(error, discord.ext.commands.CommandInvokeError):
        return await ctx.send("Sorry, but an error incurred when the command was invoked.")
    if isinstance(error, discord.ext.commands.CommandOnCooldown):
        return await ctx.send(f"Slow down! This command's on cooldown. Wait {error.retry_after} seconds!")
    if isinstance(error, discord.ext.commands.MaxConcurrencyReached):
        return await ctx.send("Uh oh. This command has reached MAXIMUM CONCURRENCY. *lightning flash*. Try again later.")
    if isinstance(error, discord.ext.commands.ExtensionError):
        return await ctx.send("Oh no. There's an extension error. Please ping a developer about this one.")
    if isinstance(error, discord.ext.commands.CommandRegistrationError):
        return await ctx.send("Oh boy. Command registration error. Please ping a developer about this.")
    if isinstance(error, discord.ext.commands.CommandError):
        return await ctx.send("Oops, there was a command error. Try again.")
    return

@client.event
async def on_message_delete(message):
   client.snipes[message.channel.id] = message
   return

@client.command()
async def ping(ctx):
    embed = discord.Embed(
      title = f'Pong! Catch that :ping_pong:! {round(client.latency * 1000)}ms ',
      description = "",
      colour = discord.Colour.teal()
      )
    await ctx.send(embed=embed)


@client.command()
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, nick):
    await member.edit(nick=nick)
    embed = discord.Embed(
        description=f" :white_check_mark: | Nickname changed. ",
        colour=0x224B8B)
    await ctx.send(embed=embed) 

@client.command()   
async def purge(ctx, amount = 10000):
    await ctx.message.delete()
    authorperms = ctx.author.permissions_in(ctx.channel)
    if authorperms.manage_messages:
      await ctx.channel.purge(limit=amount)

@client.group(invoke_without_command=True)
@commands.has_permissions(manage_messages=True)
async def embed(ctx, *, text):
    embed = discord.Embed(
      description=text,
    )
    await ctx.send(embed=embed)

@client.command()
async def snipe(ctx):
    channel_id = ctx.channel.id
    match = client.snipes.get(channel_id)
    if match is None:
      await ctx.send(f"{ctx.author.name}, there's nothing to snipe!")
    else:
      embed = discord.Embed(
        title=f'Snipe:',
        description=f'**Last Deleted Message:** \n{match.content} \n - {match.author}', 
        color = discord.Color.purple()
      )
      embed.set_footer(text= f"Snipe requested by {ctx.author.name}")
      await ctx.send(embed=embed)

# Flask app for keeping the bot alive (works on Deta, Render, PythonAnywhere, etc.)
app = Flask(__name__)

@app.route('/', methods=['GET', 'HEAD'])
def home():
    return "Bot is running!"

@app.route('/health', methods=['GET', 'HEAD'])
def health():
    return {"status": "ok", "bot": "online"}, 200

@app.route('/test', methods=['GET', 'HEAD'])
def test():
    return {"message": "Flask is working!", "app": "main"}, 200

@app.route('/email-webhook', methods=['POST'])
def email_webhook():
    """Webhook endpoint for receiving emails from Maileroo Inbound Routing"""
    print(f'[email_webhook] Received webhook request')
    print(f'[email_webhook] Request method: {request.method}')
    print(f'[email_webhook] Request headers: {dict(request.headers)}')
    print(f'[email_webhook] Content-Type: {request.content_type}')
    print(f'[email_webhook] Content-Length: {request.content_length}')
    
    try:
        print(f'[email_webhook] Parsing JSON data...')
        data = request.get_json()
        
        if not data:
            print(f'[email_webhook] ERROR: No data received')
            return {"status": "error", "message": "No data received"}, 400
        
        print(f'[email_webhook] Data keys: {list(data.keys())}')
        
        # Parse Maileroo webhook payload
        headers = data.get('headers', {})
        print(f'[email_webhook] Headers received: {list(headers.keys())}')
        
        def get_header_value(header_name, default='Unknown'):
            header_values = headers.get(header_name, [])
            if isinstance(header_values, list) and len(header_values) > 0:
                return header_values[0]
            elif isinstance(header_values, str):
                return header_values
            return default
        
        from_header = get_header_value('From', 'Unknown')
        subject_header = get_header_value('Subject', 'No Subject')
        print(f'[email_webhook] Extracted subject from webhook: \'{subject_header}\'')
        print(f'[email_webhook] Extracted from: \'{from_header}\'')
        
        # Extract email body
        body_data = data.get('body', {})
        print(f'[email_webhook] Body data keys: {list(body_data.keys()) if isinstance(body_data, dict) else "Not a dict"}')
        body = body_data.get('stripped_plaintext') or body_data.get('plaintext', '')
        print(f'[email_webhook] Plaintext body length: {len(body)} chars')
        
        # If no plaintext, try HTML stripped version
        if not body:
            print(f'[email_webhook] No plaintext found, trying HTML...')
            html_body = body_data.get('stripped_html') or body_data.get('html', '')
            if html_body:
                print(f'[email_webhook] Found HTML body ({len(html_body)} chars), stripping HTML...')
                body = re.sub('<[^<]+?>', '', html_body)
                print(f'[email_webhook] Stripped HTML body length: {len(body)} chars')
        
        # Get date from processed_at timestamp
        processed_at = data.get('processed_at')
        date = processed_at if processed_at else None
        print(f'[email_webhook] Date: {date}')
        
        # Get attachments (ensure it's always a list, even if None)
        attachments = data.get('attachments') or []
        print(f'[email_webhook] Attachments: {len(attachments)}')
        
        # Get additional info
        envelope_sender = data.get('envelope_sender', 'Unknown')
        recipients = data.get('recipients', [])
        domain = data.get('domain', 'Unknown')
        is_spam = data.get('is_spam', False)
        print(f'[email_webhook] Envelope sender: {envelope_sender}')
        print(f'[email_webhook] Recipients: {recipients}')
        print(f'[email_webhook] Domain: {domain}')
        print(f'[email_webhook] Is spam: {is_spam}')
        
        print(f'[email_webhook] Processing email webhook: from={from_header}, subject={subject_header}')
        
        # Forward to Discord asynchronously
        if email_to_discord_configured:
            print(f'[email_webhook] Email-to-Discord is configured, forwarding...')
            # Wait for bot to be ready
            import time
            max_wait = 15
            waited = 0
            print(f'[email_webhook] Waiting for bot to be ready (max {max_wait}s)...')
            print(f'[email_webhook] Initial state: is_ready={client.is_ready()}, bot_loop={bot_loop}, loop_closed={bot_loop.is_closed() if bot_loop else "N/A"}')
            
            while waited < max_wait:
                if client.is_ready() and bot_loop and not bot_loop.is_closed():
                    print(f'[email_webhook] Bot is ready! (waited {waited}s)')
                    break
                time.sleep(0.5)
                waited += 0.5
                if waited % 2 == 0:  # Log every 2 seconds
                    print(f'[email_webhook] Still waiting... ({waited}s) is_ready={client.is_ready()}, bot_loop={bot_loop is not None}, loop_closed={bot_loop.is_closed() if bot_loop else "N/A"}')
            
            if not client.is_ready() or not bot_loop or bot_loop.is_closed():
                print(f'[email_webhook] ERROR: Bot not ready after {waited}s')
                print(f'[email_webhook] DEBUG: is_ready={client.is_ready()}, bot_loop={bot_loop}, closed={bot_loop.is_closed() if bot_loop else "N/A"}')
                return {"status": "error", "message": "Bot not ready yet"}, 503
            
            print(f'[email_webhook] Scheduling Discord send coroutine...')
            print(f'[email_webhook] Creating coroutine function...')
            
            # Create the coroutine first to ensure it's valid
            coro = send_email_to_discord(
                from_email=from_header,
                subject=subject_header,
                body=body,
                date=date,
                attachments=attachments,
                envelope_sender=envelope_sender,
                recipients=recipients,
                domain=domain,
                is_spam=is_spam
            )
            print(f'[email_webhook] Coroutine created: {coro}')
            print(f'[email_webhook] Scheduling coroutine with bot_loop: {bot_loop}')
            print(f'[email_webhook] Bot loop running: {bot_loop.is_running() if bot_loop else "N/A"}')
            print(f'[email_webhook] Bot loop closed: {bot_loop.is_closed() if bot_loop else "N/A"}')

            # DEBUG: Test if the loop handles a simple print immediately
            def debug_print():
                print(f'[email_webhook] DEBUG: Loop is processing events! Time: {datetime.now()}')
            
            try:
                bot_loop.call_soon_threadsafe(debug_print)
                print(f'[email_webhook] DEBUG: Scheduled simple debug print')
            except Exception as e:
                print(f'[email_webhook] DEBUG: Failed to schedule debug print: {e}')
            
            # Schedule the coroutine using the bot's event loop
            def handle_result(future):
                print(f'[email_webhook] handle_result callback called')
                print(f'[email_webhook] Future done: {future.done()}')
                print(f'[email_webhook] Future cancelled: {future.cancelled()}')
                try:
                    if future.exception():
                        print(f'[email_webhook] Future has exception: {future.exception()}')
                        raise future.exception()
                    result = future.result()
                    print(f'[email_webhook] Discord send completed successfully, result: {result}')
                except Exception as e:
                    print(f'[email_webhook] ERROR in Discord send callback: {type(e).__name__}: {e}')
                    import traceback
                    traceback.print_exc()
            
            try:
                future = asyncio.run_coroutine_threadsafe(coro, bot_loop)
                print(f'[email_webhook] Coroutine scheduled, future: {future}')
                print(f'[email_webhook] Future done: {future.done()}')
                print(f'[email_webhook] Future cancelled: {future.cancelled()}')
                future.add_done_callback(handle_result)
                print(f'[email_webhook] Done callback added to future')
            except Exception as e:
                print(f'[email_webhook] ERROR scheduling coroutine: {type(e).__name__}: {e}')
                import traceback
                traceback.print_exc()
                return {"status": "error", "message": f"Failed to schedule coroutine: {e}"}, 500
            
            print(f'[email_webhook] Email processing queued, returning success response')
            return {"status": "success", "message": "Email forwarded to Discord"}, 200
        else:
            print(f'[email_webhook] ERROR: Email-to-Discord not configured')
            return {"status": "error", "message": "Email-to-Discord not configured"}, 400
            
    except Exception as e:
        print(f'[email_webhook] ERROR processing email webhook: {e}')
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}, 500

@app.errorhandler(404)
def not_found(e):
    return {"error": "Not Found", "message": "Route not found. Available routes: /, /health, /test, /email-webhook"}, 404

def run_bot():
    """Run Discord bot in background thread"""
    global bot_loop
    print(f'[run_bot] Starting Discord bot...')
    print(f'[run_bot] Thread: {threading.current_thread().name}')
    print(f'[run_bot] Token present: {bool(token)}')
    
    loop = None
    try:
        if not token:
            print("[run_bot] ERROR: Discord token not found, bot will not start")
            return
        
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_loop = loop
        
        print(f'[run_bot] Event loop created: {loop}')
        print(f'[run_bot] Bot loop stored globally: {bot_loop is not None}')
        
        # Create an async function to start the bot and handle errors
        async def start_bot():
            try:
                print(f'[run_bot] Inside start_bot() coroutine')
                print(f'[run_bot] Starting client.start(token)...')
                await client.start(token)
                print(f'[run_bot] client.start() completed (unexpected)')
            except Exception as e:
                print(f'[run_bot] ERROR in client.start(): {type(e).__name__}: {e}')
                import traceback
                traceback.print_exc()
                # Don't raise - we want the loop to keep running

        async def heartbeat():
            while True:
                print(f'[Heartbeat] Bot loop is alive. Time: {datetime.now()}')
                await asyncio.sleep(5)
        
        # Schedule client.start() as a task, then run the loop forever
        # This allows run_coroutine_threadsafe to work
        print(f'[run_bot] Creating client.start() task...')
        task = loop.create_task(start_bot())
        loop.create_task(heartbeat())
        print(f'[run_bot] client.start() task created: {task}')
        print(f'[run_bot] Task done: {task.done()}, cancelled: {task.cancelled()}')
        print(f'[run_bot] Running loop forever...')
        loop.run_forever()
        
    except Exception as e:
        print(f"[run_bot] ERROR starting Discord bot: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if loop and not loop.is_closed():
            print(f'[run_bot] Closing event loop...')
            loop.close()

def start_bot_thread():
    print(f'[start_bot_thread] Starting bot thread...')
    print(f'[start_bot_thread] Token present: {bool(token)}')
    if token:
        bot_thread = threading.Thread(target=run_bot, daemon=True, name="DiscordBot")
        print(f'[start_bot_thread] Created thread: {bot_thread.name}')
        bot_thread.start()
        print(f'[start_bot_thread] Thread started: {bot_thread.is_alive()}')
        print(f'[start_bot_thread] Thread ID: {bot_thread.ident}')
    else:
        print("[start_bot_thread] WARNING: No Discord token found, bot will not start")

# Start bot thread when module loads (but after Flask routes are registered)
start_bot_thread()

# For local development
# Note: Deta automatically runs the app, so this is only for local testing
if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))  # Deta uses 8080 by default
    print(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
