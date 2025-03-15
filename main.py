import discord
from discord.ext import commands
import json
import os
import datetime
import shutil
from discord import app_commands
import asyncio

# Backup configuration
BACKUP_DIR = 'backups'
MAX_BACKUPS = 5  # Maximum number of backups to keep
BACKUP_INTERVAL = 24 * 60 * 60  # 24 hours in seconds

# Ensure backup directory exists
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# Backup token data
async def backup_token_data():
    # Create timestamp for filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{BACKUP_DIR}/token_data_backup_{timestamp}.json"
    
    try:
        # Check if original file exists
        if os.path.exists(TOKEN_FILE):
            # Copy the file
            shutil.copy2(TOKEN_FILE, backup_filename)
            
            # Log the backup
            log_transaction("SYSTEM", "AUTO_BACKUP", amount=timestamp)
            print(f"[{timestamp}] Created backup: {backup_filename}")
            
            # Clean up old backups if we have too many
            cleanup_old_backups()
            return True
        else:
            print(f"[{timestamp}] Backup failed: Token file does not exist")
            return False
    except Exception as e:
        print(f"[{timestamp}] Backup failed: {str(e)}")
        return False

# Clean up old backups
def cleanup_old_backups():
    try:
        # List all backup files and sort by creation time
        backup_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("token_data_backup_")]
        backup_files.sort(key=lambda x: os.path.getctime(os.path.join(BACKUP_DIR, x)), reverse=True)
        
        # Remove excess backups
        for old_file in backup_files[MAX_BACKUPS:]:
            os.remove(os.path.join(BACKUP_DIR, old_file))
            print(f"Removed old backup: {old_file}")
    except Exception as e:
        print(f"Error cleaning up old backups: {str(e)}")

# Restore token data from backup
def restore_token_data(backup_filename):
    try:
        # Check if backup file exists
        if os.path.exists(backup_filename):
            # Create a backup of current file before restore
            if os.path.exists(TOKEN_FILE):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_backup = f"{BACKUP_DIR}/pre_restore_backup_{timestamp}.json"
                shutil.copy2(TOKEN_FILE, temp_backup)
            
            # Copy backup to main token file
            shutil.copy2(backup_filename, TOKEN_FILE)
            return True
        else:
            return False
    except Exception as e:
        print(f"Restore failed: {str(e)}")
        return False

# List available backups
def list_available_backups():
    try:
        backup_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("token_data_backup_")]
        backup_files.sort(key=lambda x: os.path.getctime(os.path.join(BACKUP_DIR, x)), reverse=True)
        return backup_files
    except Exception as e:
        print(f"Error listing backups: {str(e)}")
        return []

# Automatic backup task
async def automatic_backup_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await backup_token_data()
        await asyncio.sleep(BACKUP_INTERVAL)  # Wait for the interval period

# Add to your bot startup
@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        
        # Start automatic backup task
        bot.loop.create_task(automatic_backup_task())
        print("Automatic backup system initialized")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Command to manually create a backup (Admin only)
@bot.tree.command(name="create_backup", description="Manually create a backup of token data (Admin only)")
async def create_backup(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return
    
    # Execute backup
    success = await backup_token_data()
    
    if success:
        # Log transaction
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_transaction(interaction.guild.name, "MANUAL_BACKUP", interaction.user)
        
        await interaction.response.send_message(f"✅ Backup created successfully at {timestamp}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to create backup. Check server logs for details.", ephemeral=True)

# Command to list available backups (Admin only)
@bot.tree.command(name="list_backups", description="List available token data backups (Admin only)")
async def list_backups(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return
    
    backups = list_available_backups()
    
    if not backups:
        await interaction.response.send_message("No backups available.", ephemeral=True)
        return
    
    # Create an embed for backups
    embed = discord.Embed(
        title="Available Backups",
        description="Use `/restore_backup filename` to restore a specific backup.",
        color=discord.Color.blue()
    )
    
    for i, backup in enumerate(backups):
        # Get file creation time
        backup_path = os.path.join(BACKUP_DIR, backup)
        creation_time = datetime.datetime.fromtimestamp(os.path.getctime(backup_path))
        formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Get file size
        size_kb = os.path.getsize(backup_path) / 1024
        
        embed.add_field(
            name=f"{i+1}. {backup}",
            value=f"Created: {formatted_time}\nSize: {size_kb:.2f} KB",
            inline=False
        )
    
    # Log transaction
    log_transaction(interaction.guild.name, "LIST_BACKUPS", interaction.user)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Command to restore from backup (Admin only)
@bot.tree.command(name="restore_backup", description="Restore token data from a backup (Admin only)")
@app_commands.describe(backup_number="Backup number from list_backups command")
async def restore_backup(interaction: discord.Interaction, backup_number: int):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return
    
    backups = list_available_backups()
    
    if not backups:
        await interaction.response.send_message("No backups available to restore.", ephemeral=True)
        return
    
    if backup_number < 1 or backup_number > len(backups):
        await interaction.response.send_message(f"❌ Invalid backup number. Please use a number between 1 and {len(backups)}.", ephemeral=True)
        return
    
    # Get the backup file path
    backup_filename = os.path.join(BACKUP_DIR, backups[backup_number-1])
    
    # Confirm restoration
    await interaction.response.send_message(
        f"⚠️ Are you sure you want to restore from backup: {backups[backup_number-1]}?\n"
        f"This will overwrite the current token data. Type `/confirm_restore {backup_number}` to proceed.",
        ephemeral=True
    )

# Command to confirm restoration (Admin only)
@bot.tree.command(name="confirm_restore", description="Confirm restoration from backup (Admin only)")
@app_commands.describe(backup_number="Backup number to confirm restoration")
async def confirm_restore(interaction: discord.Interaction, backup_number: int):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
        return
    
    backups = list_available_backups()
    
    if backup_number < 1 or backup_number > len(backups):
        await interaction.response.send_message(f"❌ Invalid backup number. Please use a number between 1 and {len(backups)}.", ephemeral=True)
        return
    
    # Get the backup file path
    backup_filename = os.path.join(BACKUP_DIR, backups[backup_number-1])
    
    # Perform the restore
    success = restore_token_data(backup_filename)
    
    if success:
        # Log transaction
        log_transaction(interaction.guild.name, "RESTORE_BACKUP", interaction.user, amount=backups[backup_number-1])
        
        await interaction.response.send_message(f"✅ Successfully restored token data from backup: {backups[backup_number-1]}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to restore from backup. Check server logs for details.", ephemeral=True)

# Add a Flask web server
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord bot is running!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Start the Flask server in a background thread
server_thread = Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

# Rest of your bot code remains the same...
# Bot configuration
TOKEN = os.environ.get('BOT_TOKEN')
TOKEN_FILE = 'token_data.json'
LOG_FILE = 'token_transactions.log'
ADMIN_ROLE_NAME = 'Admin'  # Change this to match your server's admin role

# Initialize bot with intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Token data structure
# {
#   "guild_id": {
#     "user_id": token_count
#   }
# }


# Load token data
def load_token_data():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return {}


# Save token data
def save_token_data(data):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(data, f)


# Log transaction
def log_transaction(guild_name, action, admin=None, member=None, amount=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{guild_name}] {action}"

    if admin:
        log_entry += f" | Admin: {admin.name}#{admin.discriminator}"
    if member:
        log_entry += f" | Member: {member.name}#{member.discriminator}"
    if amount is not None:
        log_entry += f" | Amount: {amount}"

    with open(LOG_FILE, 'a') as f:
        f.write(log_entry + '\n')

    return log_entry


# Check if user has admin role
def is_admin(member):
    return discord.utils.get(member.roles, name=ADMIN_ROLE_NAME) is not None


@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


# Command to give tokens to a user (Admin only)
@bot.tree.command(name="give_tokens",
                  description="Give callout tokens to a member (Admin only)")
@app_commands.describe(member="The member to give tokens to",
                       amount="Number of tokens to give (1-3)")
async def give_tokens(interaction: discord.Interaction, member: discord.Member,
                      amount: int):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "❌ Only admins can use this command.", ephemeral=True)
        return

    if amount < 1 or amount > 3:
        await interaction.response.send_message(
            "❌ You can only give 1-3 tokens at a time.", ephemeral=True)
        return

    # Load token data
    token_data = load_token_data()
    guild_id = str(interaction.guild_id)
    user_id = str(member.id)

    # Initialize guild data if not exists
    if guild_id not in token_data:
        token_data[guild_id] = {}

    # Update token count
    current_tokens = token_data[guild_id].get(user_id, 0)
    token_data[guild_id][user_id] = current_tokens + amount

    # Save token data
    save_token_data(token_data)

    # Log transaction
    log_transaction(interaction.guild.name, "GIVE_TOKENS", interaction.user,
                    member, amount)

    await interaction.response.send_message(
        f"✅ Successfully gave {amount} token(s) to {member.mention}. They now have {token_data[guild_id][user_id]} token(s)."
    )


# Command to deposit tokens into the BO7 Bank
@bot.tree.command(name="deposit",
                  description="Deposit your tokens into the BO7 Bank")
@app_commands.describe(amount="Number of tokens to deposit")
async def deposit_tokens(interaction: discord.Interaction, amount: int):
    # Load token data
    token_data = load_token_data()
    guild_id = str(interaction.guild_id)
    user_id = str(interaction.user.id)

    # Check if user has enough tokens
    if guild_id not in token_data or user_id not in token_data[
            guild_id] or token_data[guild_id][user_id] < amount:
        await interaction.response.send_message(
            "❌ You don't have enough tokens to deposit.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message(
            "❌ You must deposit at least 1 token.", ephemeral=True)
        return

    # Update token count
    token_data[guild_id][user_id] -= amount

    # Remove user from data if they have 0 tokens
    if token_data[guild_id][user_id] == 0:
        del token_data[guild_id][user_id]

    # Save token data
    save_token_data(token_data)

    # Log transaction
    log_transaction(interaction.guild.name,
                    "DEPOSIT_TOKENS",
                    member=interaction.user,
                    amount=amount)

    remaining = token_data[guild_id].get(user_id, 0)
    await interaction.response.send_message(
        f"🏦 You have deposited {amount} token(s) into the BO7 Bank. You have {remaining} token(s) remaining."
    )


# Command to check token balances
@bot.tree.command(name="balances",
                  description="Check everyone's token balances")
async def check_balances(interaction: discord.Interaction):
    # Load token data
    token_data = load_token_data()
    guild_id = str(interaction.guild_id)

    if guild_id not in token_data or not token_data[guild_id]:
        await interaction.response.send_message(
            "No one has any tokens at the moment.", ephemeral=True)
        return

    # Create an embed for token balances
    embed = discord.Embed(
        title="🪙 Token Balances",
        description="Current callout token balances for all members:",
        color=discord.Color.gold())

    # Get all members with tokens
    sorted_users = sorted(token_data[guild_id].items(),
                          key=lambda x: x[1],
                          reverse=True)

    for user_id, tokens in sorted_users:
        try:
            member = await interaction.guild.fetch_member(int(user_id))
            embed.add_field(name=member.display_name,
                            value=f"{tokens} token(s)",
                            inline=True)
        except:
            # User might have left the server
            embed.add_field(name=f"Unknown User ({user_id})",
                            value=f"{tokens} token(s)",
                            inline=True)

    # Log transaction
    log_transaction(interaction.guild.name,
                    "CHECK_BALANCES",
                    member=interaction.user)

    await interaction.response.send_message(embed=embed)


# Command to check personal balance
@bot.tree.command(name="balance", description="Check your token balance")
async def check_balance(interaction: discord.Interaction):
    # Load token data
    token_data = load_token_data()
    guild_id = str(interaction.guild_id)
    user_id = str(interaction.user.id)

    # Get token count
    tokens = 0
    if guild_id in token_data and user_id in token_data[guild_id]:
        tokens = token_data[guild_id][user_id]

    # Log transaction
    log_transaction(interaction.guild.name,
                    "CHECK_PERSONAL_BALANCE",
                    member=interaction.user)

    await interaction.response.send_message(
        f"You currently have {tokens} callout token(s).", ephemeral=True)


# Command to view the transaction log (Admin only)
@bot.tree.command(name="log",
                  description="View recent token transactions (Admin only)")
@app_commands.describe(entries="Number of log entries to show (default: 10)")
async def view_log(interaction: discord.Interaction, entries: int = 10):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "❌ Only admins can use this command.", ephemeral=True)
        return

    # Cap entries to avoid message limits
    entries = min(entries, 25)

    if not os.path.exists(LOG_FILE):
        await interaction.response.send_message("No transaction logs found.",
                                                ephemeral=True)
        return

    # Get recent log entries
    with open(LOG_FILE, 'r') as f:
        log_lines = f.readlines()

    recent_logs = log_lines[-entries:] if len(
        log_lines) >= entries else log_lines

    # Format logs for Discord
    log_content = "**Recent Token Transactions:**\n```"
    for line in recent_logs:
        log_content += line.strip() + "\n"
    log_content += "```"

    await interaction.response.send_message(log_content, ephemeral=True)


# Command to remove tokens from a user (Admin only)
@bot.tree.command(
    name="remove_tokens",
    description="Remove callout tokens from a member (Admin only)")
@app_commands.describe(member="The member to remove tokens from",
                       amount="Number of tokens to remove")
async def remove_tokens(interaction: discord.Interaction,
                        member: discord.Member, amount: int):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "❌ Only admins can use this command.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message(
            "❌ Amount must be a positive number.", ephemeral=True)
        return

    # Load token data
    token_data = load_token_data()
    guild_id = str(interaction.guild_id)
    user_id = str(member.id)

    # Check if user has any tokens
    if guild_id not in token_data or user_id not in token_data[guild_id]:
        await interaction.response.send_message(
            f"❌ {member.mention} doesn't have any tokens to remove.",
            ephemeral=True)
        return

    current_tokens = token_data[guild_id][user_id]

    # Check if user has enough tokens
    if current_tokens < amount:
        await interaction.response.send_message(
            f"❌ {member.mention} only has {current_tokens} token(s), but you're trying to remove {amount}.",
            ephemeral=True)
        return

    # Update token count
    token_data[guild_id][user_id] -= amount

    # Remove user from data if they have 0 tokens
    if token_data[guild_id][user_id] == 0:
        del token_data[guild_id][user_id]
        remaining = 0
    else:
        remaining = token_data[guild_id][user_id]

    # Save token data
    save_token_data(token_data)

    # Log transaction
    log_transaction(interaction.guild.name, "REMOVE_TOKENS", interaction.user,
                    member, amount)

    await interaction.response.send_message(
        f"✅ Successfully removed {amount} token(s) from {member.mention}. They now have {remaining} token(s) remaining."
    )


# Command to list all available bank commands
@bot.tree.command(name="bank-help",
                  description="List all available token bank commands")
async def bank_help_command(interaction: discord.Interaction):
    commands_list = bot.tree.get_commands()

    # Create an embed for commands
    embed = discord.Embed(
        title="🏦 Token Bank Commands",
        description="Here are all the commands for the token bank system:",
        color=discord.Color.blue())

    # Sort commands by name
    commands_list = sorted(commands_list, key=lambda x: x.name)

    # Add regular user commands
    user_commands = []
    admin_commands = []

    for cmd in commands_list:
        # Filter to only include token-related commands
        if cmd.name in ["balance", "balances", "deposit", "bank-help"]:
            user_commands.append(f"• `/{cmd.name}` - {cmd.description}")
        elif cmd.name in ["give_tokens", "remove_tokens", "log", "create_backup", "list_backups", "restore_backup", "confirm_restore"]:
            admin_commands.append(f"• `/{cmd.name}` - {cmd.description}")

    # Add sections to embed
    if user_commands:
        embed.add_field(name="User Commands",
                        value="\n".join(user_commands),
                        inline=False)

    if admin_commands and is_admin(interaction.user):
        embed.add_field(name="Admin Commands",
                        value="\n".join(admin_commands),
                        inline=False)

    # Log command usage
    log_transaction(interaction.guild.name,
                    "BANK_HELP_COMMAND",
                    member=interaction.user)

    await interaction.response.send_message(embed=embed)


# Run the bot
bot.run(TOKEN)
