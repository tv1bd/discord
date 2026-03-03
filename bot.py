import os
import json
import logging
import time
import asyncio
from datetime import datetime
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = os.environ.get("GUILD_ID")
ADMIN_ID = os.environ.get("ADMIN_ID")

API_TEMPLATE = "https://fflikeapi.up.railway.app//like?uid={uid}&server_name=bd"
LIKE_COOLDOWN = 60
like_cooldowns = {}
LIKES_DB_FILE = "likes_db.json"
AUTOLIKE_DB_FILE = "autolike_db.json"
PREMIUM_DB_FILE = "premium_db.json"

# ==================== Database Functions ====================
def is_admin(user_id):
    if not ADMIN_ID:
        return False
    return str(user_id) == str(ADMIN_ID)

def load_likes_db():
    try:
        if os.path.exists(LIKES_DB_FILE):
            with open(LIKES_DB_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading likes database: {e}")
    return {"likes": {}}

def save_likes_db(data):
    try:
        with open(LIKES_DB_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving likes database: {e}")

def has_liked_today(uid):
    db = load_likes_db()
    today = datetime.now().strftime("%Y-%m-%d")
    if uid in db["likes"]:
        if db["likes"][uid] == today:
            return True
    return False

def record_like(uid):
    db = load_likes_db()
    today = datetime.now().strftime("%Y-%m-%d")
    db["likes"][uid] = today
    save_likes_db(db)

def load_autolike_db():
    try:
        if os.path.exists(AUTOLIKE_DB_FILE):
            with open(AUTOLIKE_DB_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading autolike database: {e}")
    return {"auto_uids": []}

def save_autolike_db(data):
    try:
        with open(AUTOLIKE_DB_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving autolike database: {e}")

def add_autolike_uid(uid):
    db = load_autolike_db()
    if uid not in db["auto_uids"]:
        db["auto_uids"].append(uid)
        save_autolike_db(db)
        return True
    return False

def remove_autolike_uid(uid):
    db = load_autolike_db()
    if uid in db["auto_uids"]:
        db["auto_uids"].remove(uid)
        save_autolike_db(db)
        return True
    return False

def get_autolike_uids():
    db = load_autolike_db()
    return db["auto_uids"]

def load_premium_db():
    try:
        if os.path.exists(PREMIUM_DB_FILE):
            with open(PREMIUM_DB_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading premium database: {e}")
    return {"premium_users": {}}

def save_premium_db(data):
    try:
        with open(PREMIUM_DB_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving premium database: {e}")

def add_premium_user(user_id, uid):
    db = load_premium_db()
    db["premium_users"][str(user_id)] = uid
    save_premium_db(db)
    return True

def remove_premium_user(user_id):
    db = load_premium_db()
    if str(user_id) in db["premium_users"]:
        del db["premium_users"][str(user_id)]
        save_premium_db(db)
        return True
    return False

def is_premium_user(user_id):
    db = load_premium_db()
    return db["premium_users"].get(str(user_id))

def get_all_premium_users():
    db = load_premium_db()
    return db["premium_users"]

# ==================== Bot Setup ====================
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
bot.intents.message_content = True
bot.intents.members = True
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    await bot.tree.sync()
    print("Synced slash commands globally")
    print("Bot is ready to receive commands!")
    
    if not auto_like_task.is_running():
        auto_like_task.start()
        print("Auto-like task started - Runs daily at 8 AM")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❓ Command Not Found",
            description="That command doesn't exist.",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="💡 Tip",
            value="Use `/help` or `!help` to see all available commands",
            inline=False
        )
        await ctx.send(embed=embed, delete_after=10)

# ==================== PING COMMAND ====================
@bot.tree.command(name="ping", description="Test if bot is working")
async def ping_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏓 Pong!",
        description="Bot is online and working perfectly!",
        color=discord.Color.green()
    )
    embed.add_field(name="Status", value="✅ Active", inline=True)
    embed.add_field(name="Response Time", value="Fast", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="ping", help="Test if bot is working")
async def ping_prefix(ctx):
    embed = discord.Embed(
        title="🏓 Pong!",
        description="Bot is online and working perfectly!",
        color=discord.Color.green()
    )
    embed.add_field(name="Status", value="✅ Active", inline=True)
    embed.add_field(name="Response Time", value="Fast", inline=True)
    await ctx.send(embed=embed)

# ==================== LIKE COMMAND ====================
@bot.tree.command(name="like", description="Send a like to a Free Fire UID")
@app_commands.describe(uid="Target UID to like (BD server)")
async def like_slash(interaction: discord.Interaction, uid: str):
    try:
        if has_liked_today(uid):
            embed = discord.Embed(
                title="⏰ Already Liked Today",
                description=f"UID `{uid}` has already been liked today.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="⏳ Wait Time",
                value="You can like again after 24 hours",
                inline=False
            )
            embed.add_field(
                name="💎 Want More Likes?",
                value="Get **Premium** for 100 automatic daily likes!\nContact admin to upgrade your account.",
                inline=False
            )
            embed.set_footer(text="Next like available tomorrow")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        remaining = check_cooldown(uid, LIKE_COOLDOWN)
        if remaining:
            embed = discord.Embed(
                title="⏱️ Cooldown Active",
                description=f"Please wait before trying again.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="⏳ Time Remaining",
                value=f"{remaining:.0f} seconds",
                inline=False
            )
            embed.set_footer(text="This prevents API spam")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        url = API_TEMPLATE.format(uid=uid)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                text = await resp.text()
                status = resp.status

        like_cooldowns[uid] = time.time()
        
        if status == 200:
            try:
                data = json.loads(text)
                likes_given = data.get('LikesGivenByAPI', 0)
                
                if likes_given > 0:
                    record_like(uid)
                    embed = discord.Embed(
                        title="✅ Like Sent Successfully!",
                        description=f"**Player:** {data.get('PlayerNickname', 'Unknown')}",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="🆔 UID", value=f"`{data.get('UID', 'N/A')}`", inline=True)
                    embed.add_field(name="❤️ Likes By API", value=f"{likes_given}", inline=True)
                    embed.add_field(name="📊 Status", value="✓ Success", inline=True)
                    embed.add_field(name="📈 Likes After", value=f"{data.get('LikesafterCommand', 0)}", inline=True)
                    embed.add_field(name="📉 Likes Before", value=f"{data.get('LikesbeforeCommand', 0)}", inline=True)
                    embed.add_field(name="➕ Net Likes", value=f"{likes_given}", inline=True)
                    
                    # Premium promotion
                    embed.add_field(
                        name="💎 Want More Likes?",
                        value="Get **Premium** for 100 automatic daily likes!\n" +
                              "Contact admin to upgrade your account.",
                        inline=False
                    )
                    
                    embed.set_footer(text="Next like available in 24 hours")
                    await interaction.followup.send(embed=embed)
                else:
                    # Check if it's invalid UID or wrong server
                    player_name = data.get('PlayerNickname', 'Unknown')
                    if player_name == "N/A" or player_name == "Unknown":
                        embed = discord.Embed(
                            title="❌ Invalid UID",
                            description="This UID is not valid or from another server.",
                            color=discord.Color.red()
                        )
                        embed.add_field(
                            name="🆔 UID",
                            value=f"`{uid}`",
                            inline=True
                        )
                        embed.add_field(
                            name="⚠️ Error",
                            value="UID not found",
                            inline=True
                        )
                        embed.add_field(
                            name="💡 Solution",
                            value="Please provide a valid BD server UID.\nMake sure the UID is from Bangladesh server.",
                            inline=False
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Like Failed",
                            description="Unable to send like to this UID",
                            color=discord.Color.red()
                        )
                        embed.add_field(
                            name="🆔 UID",
                            value=f"`{uid}`",
                            inline=True
                        )
                        embed.add_field(
                            name="⚠️ Error Type",
                            value="Already Liked Today",
                            inline=True
                        )
                        embed.add_field(
                            name="💡 Solution",
                            value="You can like again after 24 hours.",
                            inline=False
                        )
                        embed.add_field(
                            name="💎 Get Premium",
                            value="Want 100 automatic daily likes? Contact admin for Premium!",
                            inline=False
                        )
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except json.JSONDecodeError:
                record_like(uid)
                await interaction.followup.send(f"Like sent to UID {uid}")
        else:
            embed = discord.Embed(
                title="⚠️ API Error",
                description=f"The API returned an error",
                color=discord.Color.red()
            )
            embed.add_field(name="Status Code", value=f"`{status}`", inline=True)
            embed.add_field(name="Action", value="Try again later", inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    except asyncio.TimeoutError:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=False)
        embed = discord.Embed(
            title="⏱️ Request Timeout",
            description="The API is taking too long to respond",
            color=discord.Color.orange()
        )
        embed.add_field(name="Action", value="Please try again in a moment", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in like_slash: {e}")
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=False)
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)[:100]}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.command(name="like", help="Send a like to a Free Fire UID")
async def like_prefix(ctx, uid: str = None):
    try:
        if not uid:
            await ctx.send("Usage: `!like <uid>`", delete_after=5)
            return

        if has_liked_today(uid):
            embed = discord.Embed(
                title="⏰ Already Liked Today",
                description=f"UID `{uid}` has already been liked today.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="⏳ Wait Time",
                value="You can like again after 24 hours",
                inline=False
            )
            embed.add_field(
                name="💎 Want More Likes?",
                value="Get **Premium** for 100 automatic daily likes!\nContact admin to upgrade your account.",
                inline=False
            )
            embed.set_footer(text="Next like available tomorrow")
            await ctx.send(embed=embed, delete_after=15)
            return
        
        url = API_TEMPLATE.format(uid=uid)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                text = await resp.text()
                status = resp.status

        like_cooldowns[uid] = time.time()
        
        if status == 200:
            try:
                data = json.loads(text)
                likes_given = data.get('LikesGivenByAPI', 0)
                
                if likes_given > 0:
                    record_like(uid)
                    embed = discord.Embed(
                        title="✅ Like Sent Successfully!",
                        description=f"**Player:** {data.get('PlayerNickname', 'Unknown')}",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="🆔 UID", value=f"`{data.get('UID', 'N/A')}`", inline=True)
                    embed.add_field(name="❤️ Likes By API", value=f"{likes_given}", inline=True)
                    embed.add_field(name="📊 Status", value="✓ Success", inline=True)
                    embed.add_field(name="📈 Likes After", value=f"{data.get('LikesafterCommand', 0)}", inline=True)
                    embed.add_field(name="📉 Likes Before", value=f"{data.get('LikesbeforeCommand', 0)}", inline=True)
                    embed.add_field(name="➕ Net Likes", value=f"{likes_given}", inline=True)
                    
                    # Premium promotion
                    embed.add_field(
                        name="💎 Want More Likes?",
                        value="Get **Premium** for 100 automatic daily likes!\n" +
                              "Contact admin to upgrade your account.",
                        inline=False
                    )
                    
                    embed.set_footer(text="Next like available in 24 hours")
                    await ctx.send(embed=embed)
                else:
                    # Check if it's invalid UID or wrong server
                    player_name = data.get('PlayerNickname', 'Unknown')
                    if player_name == "N/A" or player_name == "Unknown":
                        embed = discord.Embed(
                            title="❌ Invalid UID",
                            description="This UID is not valid or from another server.",
                            color=discord.Color.red()
                        )
                        embed.add_field(
                            name="🆔 UID",
                            value=f"`{uid}`",
                            inline=True
                        )
                        embed.add_field(
                            name="⚠️ Error",
                            value="UID not found",
                            inline=True
                        )
                        embed.add_field(
                            name="💡 Solution",
                            value="Please provide a valid BD server UID.\nMake sure the UID is from Bangladesh server.",
                            inline=False
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Like Failed",
                            description="Unable to send like to this UID",
                            color=discord.Color.red()
                        )
                        embed.add_field(
                            name="🆔 UID",
                            value=f"`{uid}`",
                            inline=True
                        )
                        embed.add_field(
                            name="⚠️ Error Type",
                            value="Already Liked Today",
                            inline=True
                        )
                        embed.add_field(
                            name="💡 Solution",
                            value="You can like again after 24 hours.",
                            inline=False
                        )
                        embed.add_field(
                            name="💎 Get Premium",
                            value="Want 100 automatic daily likes? Contact admin for Premium!",
                            inline=False
                        )
                    await ctx.send(embed=embed, delete_after=15)
            except json.JSONDecodeError:
                record_like(uid)
                await ctx.send(f"Like sent to UID {uid}")
        else:
            embed = discord.Embed(
                title="⚠️ API Error",
                description=f"The API returned an error",
                color=discord.Color.red()
            )
            embed.add_field(name="Status Code", value=f"`{status}`", inline=True)
            embed.add_field(name="Action", value="Try again later", inline=True)
            await ctx.send(embed=embed, delete_after=10)
    
    except asyncio.TimeoutError:
        embed = discord.Embed(
            title="⏱️ Request Timeout",
            description="The API is taking too long to respond",
            color=discord.Color.orange()
        )
        embed.add_field(name="Action", value="Please try again in a moment", inline=False)
        await ctx.send(embed=embed, delete_after=10)
    except Exception as e:
        logging.error(f"Error in like_prefix: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)[:100]}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

# ==================== SUBSCRIBE COMMAND ====================
@bot.tree.command(name="subscribe", description="Subscribe to premium for auto-likes at 8 AM")
@app_commands.describe(uid="Your Free Fire UID")
async def subscribe_slash(interaction: discord.Interaction, uid: str):
    try:
        existing_uid = is_premium_user(interaction.user.id)
        if existing_uid:
            embed = discord.Embed(
                title="ℹ️ Already Subscribed",
                description=f"You already have an active premium subscription!",
                color=discord.Color.orange()
            )
            embed.add_field(name="🆔 Your UID", value=f"`{existing_uid}`", inline=True)
            embed.add_field(name="📊 Status", value="✅ Active", inline=True)
            embed.set_footer(text="Use /premium cancel to remove subscription")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        add_premium_user(interaction.user.id, uid)
        embed = discord.Embed(
            title="🎉 Premium Activated!",
            description="Welcome to Premium! Your subscription is now active.",
            color=discord.Color.gold()
        )
        embed.add_field(name="🆔 Your UID", value=f"`{uid}`", inline=True)
        embed.add_field(name="❤️ Daily Likes", value="100 automatic", inline=True)
        embed.add_field(name="⏰ Schedule", value="Every day at 8 AM", inline=True)
        embed.add_field(
            name="✨ Premium Features",
            value="✓ 100 automatic daily likes\n✓ Detailed daily report\n✓ No cooldown restrictions\n✓ Priority support",
            inline=False
        )
        embed.set_footer(text="Thank you for subscribing!")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logging.error(f"Error in subscribe_slash: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to activate premium: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="subscribe", help="Subscribe to premium")
async def subscribe_prefix(ctx, uid: str = None):
    try:
        if not uid:
            embed = discord.Embed(
                title="⚠️ Missing UID",
                description="Please provide your Free Fire UID",
                color=discord.Color.orange()
            )
            embed.add_field(name="Usage", value="`!subscribe <your_uid>`", inline=False)
            embed.add_field(name="Example", value="`!subscribe 123456789`", inline=False)
            await ctx.send(embed=embed, delete_after=10)
            return

        existing_uid = is_premium_user(ctx.author.id)
        if existing_uid:
            embed = discord.Embed(
                title="ℹ️ Already Subscribed",
                description=f"You already have an active premium subscription!",
                color=discord.Color.orange()
            )
            embed.add_field(name="🆔 Your UID", value=f"`{existing_uid}`", inline=True)
            embed.add_field(name="📊 Status", value="✅ Active", inline=True)
            embed.set_footer(text="Use !premium cancel to remove subscription")
            await ctx.send(embed=embed, delete_after=15)
            return
        
        add_premium_user(ctx.author.id, uid)
        embed = discord.Embed(
            title="🎉 Premium Activated!",
            description="Welcome to Premium! Your subscription is now active.",
            color=discord.Color.gold()
        )
        embed.add_field(name="🆔 Your UID", value=f"`{uid}`", inline=True)
        embed.add_field(name="❤️ Daily Likes", value="100 automatic", inline=True)
        embed.add_field(name="⏰ Schedule", value="Every day at 8 AM", inline=True)
        embed.add_field(
            name="✨ Premium Features",
            value="✓ 100 automatic daily likes\n✓ Detailed daily report\n✓ No cooldown restrictions\n✓ Priority support",
            inline=False
        )
        embed.set_footer(text="Thank you for subscribing!")
        await ctx.send(embed=embed)
    except Exception as e:
        logging.error(f"Error in subscribe_prefix: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to activate premium: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

# ==================== PREMIUM COMMAND ====================
@bot.tree.command(name="premium", description="Manage your premium subscription")
@app_commands.describe(action="view - Check status | cancel - Remove subscription")
async def premium_slash(interaction: discord.Interaction, action: str = "view"):
    try:
        action = action.lower()
        
        if action == "view":
            premium_uid = is_premium_user(interaction.user.id)
            if premium_uid:
                embed = discord.Embed(
                    title="💎 Premium Status",
                    description="Your premium subscription is active!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="🆔 UID", value=f"`{premium_uid}`", inline=True)
                embed.add_field(name="❤️ Daily Likes", value="100", inline=True)
                embed.add_field(name="📊 Status", value="✅ Active", inline=True)
                embed.add_field(name="⏰ Next Run", value="Tomorrow at 8 AM", inline=False)
                embed.set_footer(text="Use /premium cancel to remove subscription")
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ No Premium",
                    description="You don't have an active premium subscription.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="💎 Get Premium",
                    value="Use `/subscribe <uid>` to activate premium!\n\n" +
                          "**Benefits:**\n" +
                          "✓ 100 automatic daily likes\n" +
                          "✓ No cooldown restrictions\n" +
                          "✓ Daily detailed report\n" +
                          "✓ Priority support",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif action == "cancel":
            if remove_premium_user(interaction.user.id):
                embed = discord.Embed(
                    title="✅ Premium Cancelled",
                    description="Your premium subscription has been removed.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Status", value="❌ Inactive", inline=True)
                embed.set_footer(text="You can resubscribe anytime with /subscribe")
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ No Active Subscription",
                    description="You don't have a premium subscription to cancel.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="⚠️ Invalid Action",
                description="Please use a valid action.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Valid Actions", value="`/premium view` or `/premium cancel`", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in premium_slash: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="premium", help="Manage premium subscription")
async def premium_prefix(ctx, action: str = "view"):
    try:
        action = action.lower()
        
        if action == "view":
            premium_uid = is_premium_user(ctx.author.id)
            if premium_uid:
                embed = discord.Embed(
                    title="💎 Premium Status",
                    description="Your premium subscription is active!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="🆔 UID", value=f"`{premium_uid}`", inline=True)
                embed.add_field(name="❤️ Daily Likes", value="100", inline=True)
                embed.add_field(name="📊 Status", value="✅ Active", inline=True)
                embed.add_field(name="⏰ Next Run", value="Tomorrow at 8 AM", inline=False)
                embed.set_footer(text="Use !premium cancel to remove subscription")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ No Premium",
                    description="You don't have an active premium subscription.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="💎 Get Premium",
                    value="Use `!subscribe <uid>` to activate premium!\n\n" +
                          "**Benefits:**\n" +
                          "✓ 100 automatic daily likes\n" +
                          "✓ No cooldown restrictions\n" +
                          "✓ Daily detailed report\n" +
                          "✓ Priority support",
                    inline=False
                )
                await ctx.send(embed=embed, delete_after=15)
        
        elif action == "cancel":
            if remove_premium_user(ctx.author.id):
                embed = discord.Embed(
                    title="✅ Premium Cancelled",
                    description="Your premium subscription has been removed.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Status", value="❌ Inactive", inline=True)
                embed.set_footer(text="You can resubscribe anytime with !subscribe")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ No Active Subscription",
                    description="You don't have a premium subscription to cancel.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed, delete_after=10)
        else:
            embed = discord.Embed(
                title="⚠️ Invalid Action",
                description="Please use a valid action.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Valid Actions", value="`!premium view` or `!premium cancel`", inline=False)
            await ctx.send(embed=embed, delete_after=10)
    except Exception as e:
        logging.error(f"Error in premium_prefix: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

# ==================== AUTOLIKE COMMAND ====================
@bot.tree.command(name="autolike", description="Manage auto-like UIDs")
@app_commands.describe(
    action="list - View all | add - Add UID | remove - Remove UID",
    uid="UID to add/remove (required for add/remove)"
)
async def autolike_slash(interaction: discord.Interaction, action: str = "list", uid: str = None):
    try:
        action = action.lower()
        
        if action == "list":
            uids = get_autolike_uids()
            if uids:
                uid_list = "\n".join([f"• `{u}`" for u in uids])
                embed = discord.Embed(
                    title=f"📋 Auto-Like UIDs",
                    description=f"Total: {len(uids)} UIDs",
                    color=discord.Color.blue()
                )
                embed.add_field(name="🆔 UID List", value=uid_list, inline=False)
                embed.set_footer(text="These UIDs receive automatic likes daily at 8 AM")
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="📋 Auto-Like UIDs",
                    description="No UIDs in auto-like list.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="ℹ️ How to Add",
                    value="Use `/autolike add <uid>` to add a UID\n(Admin only)",
                    inline=False
                )
                await interaction.response.send_message(embed=embed)
        
        elif action == "add":
            if not is_admin(interaction.user.id):
                embed = discord.Embed(
                    title="🔒 Admin Only",
                    description="This command is restricted to administrators.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if not uid:
                embed = discord.Embed(
                    title="⚠️ Missing UID",
                    description="Please provide a UID to add.",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Usage", value="`/autolike add <uid>`", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if add_autolike_uid(uid):
                embed = discord.Embed(
                    title="✅ UID Added",
                    description=f"UID `{uid}` has been added to auto-like list.",
                    color=discord.Color.green()
                )
                embed.add_field(name="⏰ Schedule", value="Will receive likes daily at 8 AM", inline=False)
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Already Exists",
                    description=f"UID `{uid}` is already in the auto-like list!",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif action == "remove":
            if not is_admin(interaction.user.id):
                embed = discord.Embed(
                    title="🔒 Admin Only",
                    description="This command is restricted to administrators.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if not uid:
                embed = discord.Embed(
                    title="⚠️ Missing UID",
                    description="Please provide a UID to remove.",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Usage", value="`/autolike remove <uid>`", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if remove_autolike_uid(uid):
                embed = discord.Embed(
                    title="✅ UID Removed",
                    description=f"UID `{uid}` has been removed from auto-like list.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Not Found",
                    description=f"UID `{uid}` is not in the auto-like list!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        
        else:
            embed = discord.Embed(
                title="⚠️ Invalid Action",
                description="Please use a valid action.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Valid Actions", value="`/autolike list|add|remove`", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Error in autolike_slash: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="autolike", help="Manage auto-like UIDs")
async def autolike_prefix(ctx, action: str = "list", uid: str = None):
    try:
        action = action.lower()
        
        if action == "list":
            uids = get_autolike_uids()
            if uids:
                uid_list = "\n".join([f"• `{u}`" for u in uids])
                embed = discord.Embed(
                    title=f"📋 Auto-Like UIDs",
                    description=f"Total: {len(uids)} UIDs",
                    color=discord.Color.blue()
                )
                embed.add_field(name="🆔 UID List", value=uid_list, inline=False)
                embed.set_footer(text="These UIDs receive automatic likes daily at 8 AM")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="📋 Auto-Like UIDs",
                    description="No UIDs in auto-like list.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="ℹ️ How to Add",
                    value="Use `!autolike add <uid>` to add a UID\n(Admin only)",
                    inline=False
                )
                await ctx.send(embed=embed)
        
        elif action == "add":
            if not is_admin(ctx.author.id):
                embed = discord.Embed(
                    title="🔒 Admin Only",
                    description="This command is restricted to administrators.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
                return
            if not uid:
                embed = discord.Embed(
                    title="⚠️ Missing UID",
                    description="Please provide a UID to add.",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Usage", value="`!autolike add <uid>`", inline=False)
                await ctx.send(embed=embed, delete_after=10)
                return
            if add_autolike_uid(uid):
                embed = discord.Embed(
                    title="✅ UID Added",
                    description=f"UID `{uid}` has been added to auto-like list.",
                    color=discord.Color.green()
                )
                embed.add_field(name="⏰ Schedule", value="Will receive likes daily at 8 AM", inline=False)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="⚠️ Already Exists",
                    description=f"UID `{uid}` is already in the auto-like list!",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed, delete_after=10)
        
        elif action == "remove":
            if not is_admin(ctx.author.id):
                embed = discord.Embed(
                    title="🔒 Admin Only",
                    description="This command is restricted to administrators.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
                return
            if not uid:
                embed = discord.Embed(
                    title="⚠️ Missing UID",
                    description="Please provide a UID to remove.",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Usage", value="`!autolike remove <uid>`", inline=False)
                await ctx.send(embed=embed, delete_after=10)
                return
            if remove_autolike_uid(uid):
                embed = discord.Embed(
                    title="✅ UID Removed",
                    description=f"UID `{uid}` has been removed from auto-like list.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Not Found",
                    description=f"UID `{uid}` is not in the auto-like list!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=10)
        
        else:
            embed = discord.Embed(
                title="⚠️ Invalid Action",
                description="Please use a valid action.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Valid Actions", value="`!autolike list|add|remove`", inline=False)
            await ctx.send(embed=embed, delete_after=10)
    except Exception as e:
        logging.error(f"Error in autolike_prefix: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

# ==================== HELP COMMAND ====================
@bot.tree.command(name="help", description="Show all available commands")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 Bot Commands Help",
        description="Here are all available commands for the Free Fire Like Bot",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="❤️ Like Commands",
        value="`/like <uid>` - Send a like to a Free Fire UID\n`!like <uid>` - Same as above (prefix version)",
        inline=False
    )
    
    # Show admin commands only to admin
    if is_admin(interaction.user.id):
        embed.add_field(
            name="💎 Premium Management (Admin Only)",
            value="`/subscribe <uid>` - Add user to premium\n" +
                  "`/premium view` - Check premium status\n" +
                  "`/premium cancel` - Remove premium subscription",
            inline=False
        )
        embed.add_field(
            name="📋 Auto-Like Management (Admin Only)",
            value="`/autolike list` - View all auto-like UIDs\n" +
                  "`/autolike add <uid>` - Add UID to auto-like\n" +
                  "`/autolike remove <uid>` - Remove UID from auto-like",
            inline=False
        )
    
    embed.add_field(
        name="🔧 Utility",
        value="`/ping` - Test if bot is online\n`/help` - Show this help message",
        inline=False
    )
    embed.add_field(
        name="⏰ Auto-Like Schedule",
        value="Premium users and auto-like UIDs receive 100 automatic likes daily at 8 AM",
        inline=False
    )
    embed.set_footer(text="Use / for slash commands or ! for prefix commands")
    await interaction.response.send_message(embed=embed)

@bot.command(name="help", help="Show all commands")
async def help_prefix(ctx):
    embed = discord.Embed(
        title="📚 Bot Commands Help",
        description="Here are all available commands for the Free Fire Like Bot",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="❤️ Like Commands",
        value="`/like <uid>` - Send a like to a Free Fire UID\n`!like <uid>` - Same as above (prefix version)",
        inline=False
    )
    
    # Show admin commands only to admin
    if is_admin(ctx.author.id):
        embed.add_field(
            name="💎 Premium Management (Admin Only)",
            value="`/subscribe <uid>` - Add user to premium\n" +
                  "`!subscribe <uid>` - Same as above (prefix version)\n" +
                  "`/premium view` - Check premium status\n" +
                  "`/premium cancel` - Remove premium subscription",
            inline=False
        )
        embed.add_field(
            name="� Auto-Like Management (Admin Only)",
            value="`/autolike list` - View all auto-like UIDs\n" +
                  "`/autolike add <uid>` - Add UID to auto-like\n" +
                  "`/autolike remove <uid>` - Remove UID from auto-like",
            inline=False
        )
    
    embed.add_field(
        name="🔧 Utility",
        value="`/ping` - Test if bot is online\n`!help` - Show this help message",
        inline=False
    )
    embed.add_field(
        name="⏰ Auto-Like Schedule",
        value="Premium users and auto-like UIDs receive 100 automatic likes daily at 8 AM",
        inline=False
    )
    embed.set_footer(text="Use / for slash commands or ! for prefix commands")
    await ctx.send(embed=embed)

# ==================== HELPER FUNCTIONS ====================
def check_cooldown(uid, cooldown_seconds=60):
    if uid in like_cooldowns:
        elapsed = time.time() - like_cooldowns[uid]
        remaining = cooldown_seconds - elapsed
        if remaining > 0:
            return remaining
    return None

# ==================== AUTO-LIKE TASK ====================
@tasks.loop(hours=1)
async def auto_like_task():
    """Background task to auto-like all saved UIDs daily at 8 AM."""
    current_time = datetime.now()
    
    if current_time.hour != 8:
        return
    
    logging.info(f"Running daily auto-like at {current_time.strftime('%H:%M:%S')}")
    
    reset_db = {"likes": {}}
    save_likes_db(reset_db)
    logging.info("Likes database reset for new day")
    
    auto_uids = get_autolike_uids()
    premium_users = get_all_premium_users()
    premium_uids = list(premium_users.values())
    
    all_uids = list(set(auto_uids + premium_uids))
    
    if not all_uids:
        logging.info("No UIDs to auto-like")
        return
    
    logging.info(f"Auto-liking {len(all_uids)} UIDs ({len(auto_uids)} auto + {len(premium_uids)} premium)")
    
    results = {
        "success": [],
        "failed": [],
        "auto_uids": set(auto_uids),
        "premium_uids": set(premium_uids)
    }
    
    for uid in all_uids:
        url = API_TEMPLATE.format(uid=uid)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    text = await resp.text()
                    status = resp.status
                    
                    if status == 200:
                        try:
                            data = json.loads(text)
                            likes_given = data.get('LikesGivenByAPI', 0)
                            player_name = data.get('PlayerNickname', 'Unknown')
                            error_type = data.get('ErrorType', '')
                            
                            if likes_given > 0:
                                record_like(uid)
                                results["success"].append({
                                    "uid": uid,
                                    "player": player_name,
                                    "likes_given": likes_given,
                                    "total_likes": data.get('LikesafterCommand', 0),
                                    "type": "auto" if uid in results["auto_uids"] else "premium"
                                })
                                logging.info(f"[OK] Auto-liked {uid} - {player_name}")
                            else:
                                # Check if already liked
                                if error_type == "Already Liked Today" or "already liked" in text.lower():
                                    results["failed"].append({
                                        "uid": uid,
                                        "player": player_name,
                                        "reason": "Already Liked Today"
                                    })
                                    logging.info(f"[SKIP] {uid} ({player_name}) - Already liked today")
                                else:
                                    results["failed"].append({
                                        "uid": uid,
                                        "player": player_name,
                                        "reason": "No likes given"
                                    })
                        except json.JSONDecodeError:
                            record_like(uid)
                            results["success"].append({
                                "uid": uid,
                                "player": "Unknown",
                                "likes_given": 1,
                                "total_likes": 0,
                                "type": "auto" if uid in results["auto_uids"] else "premium"
                            })
                    else:
                        results["failed"].append({"uid": uid, "reason": f"API Error {status}"})
        except Exception as e:
            results["failed"].append({"uid": uid, "reason": str(e)})
            logging.error(f"[ERROR] Auto-like error for {uid}: {e}")
        
        await asyncio.sleep(1)
    
    # Send daily report
    try:
        channels = bot.get_all_channels()
        admin_channels = [ch for ch in channels if "admin" in ch.name.lower() or "bot" in ch.name.lower()]
        
        if admin_channels:
            channel = admin_channels[0]
            await send_daily_report(channel, results)
    except Exception as e:
        logging.error(f"Failed to send daily report: {e}")
    
    logging.info(f"Auto-like task completed - {len(results['success'])} success, {len(results['failed'])} failed")

async def send_daily_report(channel, results):
    """Send daily auto-like report to channel."""
    success_count = len(results["success"])
    failed_count = len(results["failed"])
    
    embed = discord.Embed(
        title="📊 Daily Auto-Like Report",
        description=f"**Report Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        color=discord.Color.green() if success_count > 0 else discord.Color.red()
    )
    
    if results["success"]:
        success_text = ""
        auto_count = 0
        premium_count = 0
        total_likes = 0
        
        for item in results["success"]:
            success_text += f"✅ `{item['uid']}` - {item['player']} (+{item['likes_given']} likes)\n"
            if item["type"] == "auto":
                auto_count += 1
            else:
                premium_count += 1
            total_likes += item["likes_given"]
        
        embed.add_field(
            name="✅ Successfully Liked",
            value=success_text[:1024] if len(success_text) <= 1024 else success_text[:1000] + "...",
            inline=False
        )
        embed.add_field(
            name="📈 Statistics",
            value=f"📋 Auto-Like UIDs: {auto_count}\n💎 Premium UIDs: {premium_count}\n❤️ Total Likes Given: {total_likes}",
            inline=False
        )
    
    if results["failed"]:
        failed_text = ""
        for item in results["failed"]:
            player_info = f" - {item.get('player', 'Unknown')}" if item.get('player') else ""
            failed_text += f"❌ `{item['uid']}`{player_info}\n   Reason: {item['reason']}\n"
        
        embed.add_field(
            name="❌ Failed Attempts",
            value=failed_text[:512] if len(failed_text) <= 512 else failed_text[:500] + "...",
            inline=False
        )
    
    embed.set_footer(text=f"Summary: {success_count} successful • {failed_count} failed")
    await channel.send(embed=embed)

# ==================== MAIN ====================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("ERROR: Set DISCORD_TOKEN in .env file")
    bot.run(DISCORD_TOKEN)
