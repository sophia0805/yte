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
discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")  # Channel ID to send emails to

if discord_channel_id:
    email_to_discord_configured = True
    print("Email-to-Discord forwarding configured (via Maileroo webhook)")
else:
    email_to_discord_configured = False
    print("Warning: Discord channel ID not found. Email-to-Discord forwarding will be disabled.")
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix="soph ", intents=intents, case_insensitive=True)

async def isSophia(ctx):
  return ctx.author.id == 704038199776903209 or ctx.author.id == 701792352301350973
 
client.snipes = {}
bot_event_loop = None  # Global variable to store the bot's event loop

@client.event
async def on_ready():
  await client.change_presence(activity=discord.watching(name=" the AI & Data Science Club!"))
  print('Ready!')
  # Store the event loop for use in Flask routes
  global bot_event_loop
  bot_event_loop = asyncio.get_event_loop()

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

async def send_email_to_discord(from_email, subject, body, date=None, attachments=None, 
                                 envelope_sender=None, recipients=None, domain=None, is_spam=False):
    """Send email content to Discord channel"""
    if not email_to_discord_configured:
        return
    
    try:
        channel = client.get_channel(int(discord_channel_id))
        if channel is None:
            print(f"Error: Could not find Discord channel with ID {discord_channel_id}")
            return
        
        # Determine embed color based on spam status
        embed_color = discord.Color.orange() if is_spam else discord.Color.blue()
        
        # Create embed for the email
        embed = discord.Embed(
            title=f"📧 Email from {from_email}",
            description=body[:2000] if len(body) > 2000 else body,  # Discord embed limit
            color=embed_color,
            timestamp=datetime.fromtimestamp(date) if date else datetime.now()
        )
        embed.add_field(name="Subject", value=subject[:1024], inline=False)
        embed.add_field(name="From", value=from_email, inline=True)
        
        # Add recipient info if available
        if recipients and len(recipients) > 0:
            recipient_str = ", ".join(recipients[:3])
            if len(recipients) > 3:
                recipient_str += f" (+{len(recipients) - 3} more)"
            embed.add_field(name="To", value=recipient_str[:1024], inline=True)
        
        # Add domain info
        if domain:
            embed.add_field(name="Domain", value=domain, inline=True)
        
        # Add spam indicator
        if is_spam:
            embed.add_field(name="⚠️ Spam Status", value="This email was flagged as spam", inline=False)
        
        # Add attachment info if present
        if attachments and len(attachments) > 0:
            attachment_info = "\n".join([
                f"• {att.get('filename', 'Unknown')} ({att.get('size', 0)} bytes)" 
                for att in attachments[:5]
            ])
            if len(attachments) > 5:
                attachment_info += f"\n... and {len(attachments) - 5} more"
            embed.add_field(name="Attachments", value=attachment_info[:1024], inline=False)
        
        # If body is too long, send it as a separate message
        if len(body) > 2000:
            await channel.send(embed=embed)
            # Send remaining content as a code block
            remaining = body[2000:]
            chunks = [remaining[i:i+1900] for i in range(0, len(remaining), 1900)]
            for chunk in chunks:
                await channel.send(f"```\n{chunk}\n```")
        else:
            await channel.send(embed=embed)
        
        print(f"Email from {from_email} forwarded to Discord channel {discord_channel_id}")
    except Exception as e:
        print(f"Error sending email to Discord: {e}")
        import traceback
        traceback.print_exc()

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
        await ctx.send("❌ Email-to-Discord forwarding is not configured. Set DISCORD_CHANNEL_ID in your .env file.")
        return
    
    channel = client.get_channel(int(discord_channel_id))
    if not channel:
        await ctx.send(f"⚠️ Email-to-Discord is configured but channel {discord_channel_id} not found.")
        return
    
    # Get webhook URL (try to get from env or construct it)
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "https://your-domain.com")
    webhook_url = f"{webhook_base_url}/email-webhook"
    
    embed = discord.Embed(
        title="📧 Email-to-Discord Status",
        color=discord.Color.green()
    )
    embed.add_field(
        name="✅ Status",
        value=f"Active! Emails will be sent to {channel.mention}",
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
    
    await ctx.send(embed=embed)

@client.command()
@commands.check(isSophia)
async def webhookurl(ctx):
    """Get the webhook URL for Maileroo Inbound Routing configuration"""
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL")
    webhook_url = f"{webhook_base_url}/email-webhook"
    
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
            # Include spam status in the message
            spam_note = ""
            if is_spam or spam_status_header == 'Yes':
                spam_note = " ⚠️ **SPAM**"
            
            # Use the stored bot event loop
            global bot_event_loop
            if bot_event_loop:
                asyncio.run_coroutine_threadsafe(
                    send_email_to_discord(
                        from_email=from_header,
                        subject=subject_header + spam_note,
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
            else:
                print("Error: Bot event loop not available. Bot may not be fully started yet.")
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