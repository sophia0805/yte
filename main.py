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

maileroo_api_key = os.getenv("MAILEROO_API_KEY")
maileroo_from_email = os.getenv("MAILEROO_FROM_EMAIL")
maileroo_from_name = os.getenv("MAILEROO_FROM_NAME", "Discord Bot")
maileroo_to_email = os.getenv("MAILEROO_TO_EMAIL")
maileroo_api_url = os.getenv("MAILEROO_API_URL", "https://smtp.maileroo.com/api/v2/emails")

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
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix="soph ", intents=intents, case_insensitive=True)

async def isSophia(ctx):
  return ctx.author.id == 704038199776903209 or ctx.author.id == 701792352301350973

# Sophia's user IDs (primary and secondary)
SOPHIA_USER_IDS = [704038199776903209, 701792352301350973]
PRIMARY_SOPHIA_ID = 704038199776903209  # Primary user ID for webhook avatar
 
client.snipes = {}
bot_event_loop = None  # Global variable to store the bot's event loop
bot_ready = False  # Flag to track if bot is ready

@client.event
async def on_ready():
  await client.change_presence(activity=discord.watching(name=" the AI & Data Science Club!"))
  print('=' * 50)
  print('✅ Discord Bot Connected and Ready!')
  print(f'Logged in as: {client.user.name} (ID: {client.user.id})')
  print(f'Connected to {len(client.guilds)} guild(s)')
  print('=' * 50)
  
  # Store the event loop for use in Flask routes
  global bot_event_loop, bot_ready
  bot_event_loop = asyncio.get_event_loop()
  bot_ready = True
  print(f"✅ Bot ready flag set to True")
  print(f"✅ Event loop stored: {bot_event_loop is not None}")
  print(f"✅ Client.is_ready(): {client.is_ready()}")

async def send_email(subject, message_content):
    """Send email notification using Maileroo API"""
    if not email_configured:
        print("Email not configured - skipping email send")
        return
    
    try:
        payload = {
            "from": {
                "address": maileroo_from_email,
                "display_name": maileroo_from_name
            },
            "to": {
                "address": maileroo_to_email
            },
            "subject": subject,
            "plain": message_content
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
    # Remove "Re:" or "RE:" prefix if present
    subject_clean = re.sub(r'^(Re|RE):\s*', '', subject, flags=re.IGNORECASE).strip()
    
    # Look for pattern: [Discord] #channel-name - author-name
    # Match: [Discord] #channel-name
    match = re.search(r'\[Discord\]\s*#([^\s-]+)', subject_clean, re.IGNORECASE)
    if match:
        channel_name = match.group(1)
        # Find the channel in the guild
        guild = client.get_guild(int(discord_guild_id))
        if guild:
            # Try to find channel by name (case-insensitive)
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                print(f"Found channel '{channel_name}' from subject: {subject}")
                return channel
            else:
                print(f"Channel '{channel_name}' not found in guild. Subject: {subject}")
        else:
            print(f"Guild {discord_guild_id} not found")
    
    # Fallback: try to find channel by ID if configured
    if discord_channel_id:
        channel = client.get_channel(int(discord_channel_id))
        if channel:
            print(f"Using fallback channel {discord_channel_id} (could not parse channel from subject)")
            return channel
    
    return None

async def get_or_create_sophia_webhook(channel):
    """Get or create a webhook named 'sophia' in the channel"""
    try:
        # Try to find existing webhook named "sophia"
        # Get webhooks from the channel (returns async iterator)
        webhooks = [webhook async for webhook in channel.webhooks()]
        sophia_webhook = discord.utils.get(webhooks, name="sophia")
        
        if sophia_webhook:
            print(f"Found existing webhook 'sophia' in channel {channel.name}")
            return sophia_webhook
        
        # Webhook doesn't exist, create one with Sophia's name and avatar
        print(f"Creating new webhook 'sophia' in channel {channel.name}")
        
        # Get Sophia's user info for avatar
        guild = channel.guild
        sophia_user = guild.get_member(PRIMARY_SOPHIA_ID)
        
        if sophia_user:
            username = sophia_user.display_name or sophia_user.name
            avatar_url = sophia_user.display_avatar.url
        else:
            # Fallback if user not found in guild
            username = "Sophia"
            avatar_url = None
        
        # Create the webhook
        webhook = await channel.create_webhook(
            name="sophia",
            avatar=avatar_url,
            reason="Created for email-to-Discord forwarding"
        )
        
        print(f"Created webhook 'sophia' with avatar: {avatar_url if avatar_url else 'default'}")
        return webhook
        
    except discord.errors.Forbidden:
        print(f"Error: Bot doesn't have permission to manage webhooks in channel {channel.name}")
        return None
    except Exception as e:
        print(f"Error getting/creating webhook: {e}")
        import traceback
        traceback.print_exc()
        return None

async def send_email_to_discord(from_email, subject, body, date=None, attachments=None, 
                                 envelope_sender=None, recipients=None, domain=None, is_spam=False):
    """Send email content to Discord channel based on subject line"""
    print(f"[send_email_to_discord] Called with subject: {subject}")
    
    if not email_to_discord_configured:
        print("[send_email_to_discord] Email-to-Discord not configured, returning")
        return
    
    try:
        # Find channel from subject line
        print(f"[send_email_to_discord] Looking for channel from subject: {subject}")
        channel = find_channel_from_subject(subject)
        
        if channel is None:
            print(f"[send_email_to_discord] ERROR: Could not find Discord channel from subject '{subject}' and no fallback channel configured")
            return
        
        print(f"[send_email_to_discord] Found channel: {channel.name} ({channel.id})")
        
        # Build plain text message
        message_parts = []
        
        # Add body
        message_parts.append(body)
        
        # Add "sent from my email" note
        message_parts.append("\n\n> sent from my email")
        
        # Combine into message
        full_message = "".join(message_parts)
        
        # Get or create the "sophia" webhook
        print(f"[send_email_to_discord] Getting/creating webhook for channel {channel.name}")
        webhook = await get_or_create_sophia_webhook(channel)
        
        if webhook:
            print(f"[send_email_to_discord] Webhook ready: {webhook.name} ({webhook.id})")
            # Send using webhook
            # Discord message limit is 2000 characters
            if len(full_message) > 2000:
                # Send in chunks
                chunks = []
                current_chunk = ""
                
                # Split by lines to avoid breaking mid-word
                lines = full_message.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= 1900:
                        current_chunk += line + '\n'
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Send first chunk
                await webhook.send(content=chunks[0])
                # Send remaining chunks
                for chunk in chunks[1:]:
                    await webhook.send(content=chunk)
            else:
                await webhook.send(content=full_message)
            print(f"[send_email_to_discord] SUCCESS: Email from {from_email} sent via webhook to Discord channel {channel.name} ({channel.id})")
        else:
            # Fallback: send as bot if webhook creation fails
            print(f"[send_email_to_discord] WARNING: Could not use webhook, sending as bot instead")
            if len(full_message) > 2000:
                # Send in chunks
                chunks = []
                current_chunk = ""
                
                lines = full_message.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= 1900:
                        current_chunk += line + '\n'
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                await channel.send(content=chunks[0])
                for chunk in chunks[1:]:
                    await channel.send(content=chunk)
            else:
                await channel.send(content=full_message)
            print(f"Email from {from_email} forwarded to Discord channel {channel.name} ({channel.id})")
    except Exception as e:
        print(f"[send_email_to_discord] ERROR: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise to be caught by the future callback

@client.event
async def on_message(message):
  if message.author == client.user:
    return
  # Check if message is in the specific guild
  if message.guild and message.guild.id == 1405628370301091860:
    print(message.content, message.channel.name, message.author.name)
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

@client.command()
@commands.check(isSophia)
async def checkmail(ctx):
    """Check email forwarding status and show setup instructions"""
    if not email_to_discord_configured:
        await ctx.send("❌ Email-to-Discord forwarding is not configured. Set DISCORD_GUILD_ID in your .env file.")
        return
    
    guild = client.get_guild(int(discord_guild_id))
    if not guild:
        await ctx.send(f"⚠️ Email-to-Discord is configured but guild {discord_guild_id} not found.")
        return
    
    # Get webhook URL (try to get from env or construct it)
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "https://your-domain.com")
    # If URL already includes /email-webhook, use it as-is, otherwise append it
    if webhook_base_url.endswith("/email-webhook"):
        webhook_url = webhook_base_url
    else:
        webhook_url = f"{webhook_base_url.rstrip('/')}/email-webhook"
    
    embed = discord.Embed(
        title="📧 Email-to-Discord Status",
        color=discord.Color.green()
    )
    embed.add_field(
        name="✅ Status",
        value=f"Active! Emails will be routed to channels based on subject line.\nGuild: {guild.name}",
        inline=False
    )
    embed.add_field(
        name="🔗 Webhook URL",
        value=f"`{webhook_url}`",
        inline=False
    )
    embed.add_field(
        name="⚙️ Maileroo Setup Required",
        value=(
            "**To fix '503 No routes found' error:**\n"
            "1. Go to Maileroo Dashboard → Your Domain → Sending → Inbound Routing\n"
            "2. Click 'Create New Route'\n"
            "3. Set Expression Type to 'Match Recipient'\n"
            "4. Enter your email (e.g., `bot@9b6d05a69dadf0d2.maileroo.org`)\n"
            "5. Choose 'Send to Webhook'\n"
            "6. Paste the webhook URL above\n"
            "7. Save the route\n\n"
            "**For catch-all:** Use `*@your-domain.com` as the recipient pattern"
        ),
        inline=False
    )
    embed.add_field(
        name="📝 How It Works",
        value=(
            "Emails are routed to Discord channels based on the subject line.\n"
            "The bot looks for: `[Discord] #channel-name` in the subject.\n"
            "If the channel can't be found, it falls back to the configured channel."
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

@client.command()
@commands.check(isSophia)
async def webhookurl(ctx):
    """Get the webhook URL for Maileroo Inbound Routing configuration"""
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "https://your-domain.com")
    # If URL already includes /email-webhook, use it as-is, otherwise append it
    if webhook_base_url.endswith("/email-webhook"):
        webhook_url = webhook_base_url
    else:
        webhook_url = f"{webhook_base_url.rstrip('/')}/email-webhook"
    
    embed = discord.Embed(
        title="🔗 Webhook URL for Maileroo",
        description=f"Use this URL when setting up Inbound Routing in Maileroo:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Webhook URL",
        value=f"```\n{webhook_url}\n```",
        inline=False
    )
    embed.add_field(
        name="Instructions",
        value=(
            "1. Copy the URL above\n"
            "2. Go to Maileroo Dashboard → Your Domain → Inbound Routing\n"
            "3. Create a route and paste this URL in the webhook field"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

# Flask for keeping the bot alive
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
    try:
        data = request.get_json()
        
        if not data:
            return {"status": "error", "message": "No data received"}, 400
        
        # Validate webhook using Maileroo's validation URL
        validation_url = data.get('validation_url')
        if validation_url:
            try:
                # Validate the webhook asynchronously
                async def validate_webhook():
                    async with aiohttp.ClientSession() as session:
                        async with session.get(validation_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                if result.get('success') == True:
                                    print("Webhook validated successfully")
                                    return True
                            print(f"Validation failed: HTTP {resp.status}")
                    return False
                
                # Use a temporary event loop for validation (independent of Discord bot)
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    validation_result = loop.run_until_complete(validate_webhook())
                    loop.close()
                except Exception as e:
                    print(f"Error in validation loop: {e}")
                    validation_result = False
                
                if not validation_result:
                    print("Warning: Webhook validation failed - processing anyway")
                    # Note: We continue processing even if validation fails to avoid blocking legitimate emails
                    # You can change this to return an error if you want stricter validation
            except Exception as e:
                print(f"Error validating webhook: {e}")
        
        # Parse Maileroo webhook payload according to their schema
        headers = data.get('headers', {})
        
        # Headers are arrays, get first value
        def get_header_value(header_name, default='Unknown'):
            header_values = headers.get(header_name, [])
            if isinstance(header_values, list) and len(header_values) > 0:
                return header_values[0]
            elif isinstance(header_values, str):
                return header_values
            return default
        
        from_header = get_header_value('From', 'Unknown')
        subject_header = get_header_value('Subject', 'No Subject')
        
        print(f"[email_webhook] Extracted subject from webhook: '{subject_header}'")
        print(f"[email_webhook] Extracted from: '{from_header}'")
        
        # Check spam status
        is_spam = data.get('is_spam', False)
        spam_status_header = get_header_value('X-Spam-Status', '')
        
        # Extract email body (prefer stripped_plaintext for replies, fallback to plaintext)
        body_data = data.get('body', {})
        body = body_data.get('stripped_plaintext') or body_data.get('plaintext', '')
        
        # If no plaintext, try HTML stripped version
        if not body:
            html_body = body_data.get('stripped_html') or body_data.get('html', '')
            if html_body:
                # Simple HTML stripping (you might want to use a library for better results)
                body = re.sub('<[^<]+?>', '', html_body)
        
        # Get date from processed_at timestamp (Unix timestamp)
        processed_at = data.get('processed_at')
        date = processed_at if processed_at else None
        
        # Get attachments
        attachments = data.get('attachments', [])
        
        # Get additional info
        envelope_sender = data.get('envelope_sender', 'Unknown')
        recipients = data.get('recipients', [])
        domain = data.get('domain', 'Unknown')
        
        # Forward to Discord asynchronously
        if email_to_discord_configured:
            
            # Use the stored bot event loop
            global bot_event_loop, bot_ready
            
            # Check if bot is actually ready (check both flag and client state)
            # Use client.is_ready() as the source of truth since bot can send messages
            if not bot_event_loop:
                print(f"Error: Bot event loop not available.")
                return {"status": "error", "message": "Bot event loop not available"}, 503
            
            # Wait for bot to be ready (check both flag and client state)
            import time
            max_wait = 15  # seconds
            waited = 0
            while waited < max_wait:
                # Check both the flag and the client's actual ready state
                is_actually_ready = bot_ready or (hasattr(client, 'is_ready') and client.is_ready())
                if is_actually_ready and bot_event_loop:
                    break
                time.sleep(0.5)
                waited += 0.5
            
            is_actually_ready = bot_ready or (hasattr(client, 'is_ready') and client.is_ready())
            
            if bot_event_loop and is_actually_ready:
                print(f"Processing email webhook: from={from_header}, subject={subject_header}")
                
                def handle_result(future):
                    """Handle the result of the coroutine"""
                    try:
                        result = future.result()
                        print(f"Email successfully processed and sent to Discord")
                    except Exception as e:
                        print(f"Error sending email to Discord: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Schedule the coroutine and attach error handler
                future = asyncio.run_coroutine_threadsafe(
                    send_email_to_discord(
                        from_email=from_header,
                        subject=subject_header,
                        body=body,
                        date=date,
                        attachments=attachments,
                        envelope_sender=envelope_sender,
                        recipients=recipients,
                        domain=domain,
                        is_spam=is_spam
                    ),
                    bot_event_loop
                )
                future.add_done_callback(handle_result)
            else:
                is_actually_ready = bot_ready or (hasattr(client, 'is_ready') and client.is_ready())
                print(f"Error: Bot not ready. bot_ready={bot_ready}, client.is_ready()={client.is_ready() if hasattr(client, 'is_ready') else 'N/A'}, bot_event_loop={bot_event_loop is not None}")
                # If bot can send messages, it's probably ready - force it
                if bot_event_loop:
                    print("Warning: Bot appears not ready but has event loop. Attempting to send anyway...")
                    # Try anyway if we have the event loop
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            send_email_to_discord(
                                from_email=from_header,
                                subject=subject_header,
                                body=body,
                                date=date,
                                attachments=attachments,
                                envelope_sender=envelope_sender,
                                recipients=recipients,
                                domain=domain,
                                is_spam=is_spam
                            ),
                            bot_event_loop
                        )
                        future.add_done_callback(lambda f: print("Email processing completed") if f.exception() is None else print(f"Error: {f.exception()}"))
                    except Exception as e:
                        print(f"Error scheduling email: {e}")
                        return {"status": "error", "message": f"Error scheduling email: {str(e)}"}, 500
                else:
                    return {"status": "error", "message": "Bot not ready"}, 503
            
            # Optionally delete the email after processing (uncomment if desired)
            # deletion_url = data.get('deletion_url')
            # if deletion_url:
            #     async def delete_email():
            #         async with aiohttp.ClientSession() as session:
            #             async with session.delete(deletion_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            #                 if resp.status == 200:
            #                     print("Email deleted from Maileroo storage")
            #     asyncio.run_coroutine_threadsafe(delete_email(), client.loop)
            
            return {"status": "success", "message": "Email forwarded to Discord"}, 200
        else:
            return {"status": "error", "message": "Email-to-Discord not configured"}, 400
            
    except Exception as e:
        print(f"Error processing email webhook: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}, 500

@app.errorhandler(404)
def not_found(e):
    return {"error": "Not Found", "message": "Route not found. Available routes: /, /health, /test, /email-webhook"}, 404

def run_bot():
    """Run Discord bot in background thread"""
    import time
    time.sleep(2)
    
    global bot_event_loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_event_loop = loop  # Store the loop globally
        print(f"Bot thread: Event loop stored: {bot_event_loop is not None}")
        
        async def bot_main():
            async with client:
                await client.start(token)
        
        loop.run_until_complete(bot_main())
    except Exception as e:
        print(f"Error starting Discord bot: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            if loop:
                loop.close()
        except:
            pass

def start_bot_thread():
    if token:
        bot_thread = threading.Thread(target=run_bot, daemon=True, name="DiscordBot")
        bot_thread.start()
        print("Discord bot thread started")
    else:
        print("Warning: No Discord token found, bot will not start")

start_bot_thread()

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    print(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)