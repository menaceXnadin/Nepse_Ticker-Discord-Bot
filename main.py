"""just for pylint"""
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import discord
import regex
from discord.ext import commands, tasks
from discord import app_commands
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend to prevent threading warnings
import mplfinance as mpf

load_dotenv()
MY_BOT_TOKEN = str(os.getenv("DISCORD_BOT_TOK"))
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

# dict style: user_alerts = {'user_id': {'stock_name': [target_price1, target_price2]}}
user_alerts = {}

# ============================================
# Number Formatting Utilities
# ============================================

def format_number(num):
    """Format large numbers with K, M, B suffixes"""
    try:
        num = float(str(num).replace(',', ''))
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.2f}K"
        else:
            return f"{num:.2f}"
    except (ValueError, AttributeError):
        return str(num)

def format_rupees(amount):
    """Format amount as rupees with proper comma placement"""
    try:
        amount = float(str(amount).replace(',', ''))
        return f"Rs. {amount:,.2f}"
    except (ValueError, AttributeError):
        return f"Rs. {amount}"

def get_relative_time(timestamp_str):
    """Convert timestamp to relative time (e.g., '2 minutes ago')"""
    try:
        # This is a simple implementation, can be enhanced based on timestamp format
        return timestamp_str  # For now, return as-is
    except:
        return timestamp_str


class MarketDataCache:
    """In-memory cache for market data with TTL (Time To Live)"""
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        # Cache durations in seconds for different data types
        self.cache_duration = {
            'stock_details': 20,      # 20 seconds - fresher stock data for better accuracy
            'market_summary': 60,     # 1 minute - market summary changes slowly
            'nepse_indices': 60,      # 1 minute - NEPSE indices
            'sub_indices': 120,       # 2 minutes - sub-indices change less frequently
            'top_gainers_losers': 60, # 1 minute - top G/L rankings
            'company_logo': 3600,     # 1 hour - logos rarely change
            'stock_symbols': 3600     # 1 hour - stock symbols list changes rarely
        }
    
    def get(self, key: str, category: str) -> Optional[Any]:
        """Retrieve cached data if still valid"""
        cache_key = f"{category}:{key}"
        if cache_key in self.cache:
            data = self.cache[cache_key]['data']
            timestamp = self.cache[cache_key]['timestamp']
            duration = self.cache_duration.get(category, 60)
            
            # Check if cache is still valid
            if datetime.now() - timestamp < timedelta(seconds=duration):
                return data
            # Cache expired, remove it
            del self.cache[cache_key]
        return None
    
    def set(self, key: str, category: str, data: Any) -> None:
        """Store data in cache with timestamp"""
        cache_key = f"{category}:{key}"
        self.cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def clear(self, category: Optional[str] = None) -> None:
        """Clear cache for a specific category or all"""
        if category:
            keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{category}:")]
            for key in keys_to_delete:
                del self.cache[key]
        else:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        stats = {}
        for category in self.cache_duration.keys():
            count = len([k for k in self.cache.keys() if k.startswith(f"{category}:")])
            stats[category] = count
        stats['total'] = len(self.cache)
        return stats


# Initialize cache
market_cache = MarketDataCache()


# ============================================
# Stock Symbols Fetching for Autocomplete
# ============================================

def fetch_stock_symbols():
    """Fetch all stock symbols from ShareHub Nepal API"""
    # Try to get from cache first (cached for 1 hour)
    cached_symbols = market_cache.get('all_symbols', 'stock_symbols')
    if cached_symbols:
        return cached_symbols
    
    try:
        response = requests.get(
            "https://sharehubnepal.com/live/api/v2/nepselive/home-page-data",
            timeout=10
        )
        data = response.json()
        
        symbols = []
        live_data = data.get('liveCompanyData', [])
        if isinstance(live_data, list):
            for item in live_data:
                if isinstance(item, dict) and 'symbol' in item:
                    symbols.append(item['symbol'])
        
        # Cache the symbols for 1 hour
        market_cache.set('all_symbols', 'stock_symbols', symbols)
        return symbols
    except Exception as e:
        print(f"Error fetching stock symbols: {e}")
        return []


# ============================================
# Candlestick Chart Functions
# ============================================

def fetch_chart_data(symbol, page_size, page=1):
	"""Fetch a single page of data from the ShareHub Nepal API"""
	url = f"https://sharehubnepal.com/data/api/v1/price-history?pageSize={page_size}&symbol={symbol}&page={page}"
	resp = requests.get(url, timeout=10)
	resp.raise_for_status()
	return resp.json()


def fetch_all_chart_data(symbol, days_needed):
	"""Fetch multiple pages if needed to get the required number of days"""
	all_items = []
	page = 1
	page_size = min(days_needed, 100)
	
	while len(all_items) < days_needed:
		try:
			payload = fetch_chart_data(symbol, page_size, page)
			
			if 'data' in payload and 'content' in payload['data']:
				items = payload['data']['content']
				if not items:
					break
				all_items.extend(items)
				
				has_next = payload['data'].get('hasNext', False)
				if not has_next or len(all_items) >= days_needed:
					break
					
				page += 1
			else:
				break
		except Exception as e:
			print(f"Error fetching page {page}: {e}")
			break
	
	result_payload = {'data': {'content': all_items[:days_needed]}}
	return result_payload


def make_df_from_payload(payload):
	"""Convert API payload to pandas DataFrame"""
	df = pd.DataFrame(payload['data']['content'])
	df['date'] = pd.to_datetime(df['date'])
	df = df.sort_values('date')
	df.set_index('date', inplace=True)
	return df


def plot_candlestick(df, symbol, days, filename):
	"""Generate candlestick chart and save to file"""
	# Custom market colors (Yahoo Finance style)
	mc = mpf.make_marketcolors(
		up='#26a69a',
		down='#ef5350',
		edge='inherit',
		volume='in',
		wick='inherit'
	)
	
	# Create custom style
	s = mpf.make_mpf_style(
		marketcolors=mc,
		y_on_right=False
	)
	
	# Plot with volume
	fig, axes = mpf.plot(
		df,
		type='candle',
		volume=True,
		style=s,
		title='',
		ylabel='Price (Rs.)',
		ylabel_lower='Volume',
		figsize=(10, 6),
		returnfig=True,
		scale_padding={'left': 0.05, 'right': 0.8, 'top': 0.1, 'bottom': 0.3}
	)
	
	# Save with tight layout
	fig.savefig(filename, bbox_inches='tight', pad_inches=0.1, dpi=100)
	return filename


def generate_candlestick_chart(symbol, days):
	"""Main function to generate candlestick chart"""
	try:
		print(f"Fetching {days} days of data for {symbol}...")
		payload = fetch_all_chart_data(symbol, days)
		
		if not payload['data']['content']:
			return None, "No data found for this symbol"
		
		df = make_df_from_payload(payload)
		actual_days = len(df)
		
		filename = f"{symbol.lower()}_{actual_days}days_chart.png"
		plot_candlestick(df, symbol, actual_days, filename)
		
		return filename, actual_days
		
	except Exception as e:
		return None, str(e)


@client.hybrid_command(name='sync', description='Syncs the application commands.')
async def sync(ctx):
    await ctx.defer()
    """just for pylint"""
    # Check if command is used in a guild (not DM)
    if ctx.guild is None:
        await ctx.send('❌ This command can only be used in a server, not in DMs.')
        return
    
    # Check if the user has Administrator permission
    if ctx.author.guild_permissions.administrator:
        await client.tree.sync()  # Syncs commands globally or to the current guild
        await ctx.send('Command tree synced successfully.')
    else:
        await ctx.send('You do not have permission to use this command.')


def get_latest_time():
    response = requests.get(
        "https://www.sharesansar.com/live-trading", timeout=10)
    soup = BeautifulSoup(response.text, "lxml")
    time_stamp = soup.find(id="dDate")
    if time_stamp is not None:
        last_updated = time_stamp.text
    else:
        last_updated = "Date not Found"
    return last_updated


def extract_stock_name(stock_info):
    return regex.sub(r"\s*\(\s*.*?\s*\)", "", stock_info).strip()


def fetch_and_extract_image(url: str):
    """Fetches the company logo from ShareHub Nepal"""
    # Try to get from cache first (extract symbol from URL)
    symbol = url.split('/')[-1].upper() if '/' in url else 'unknown'
    cached_data = market_cache.get(symbol, 'company_logo')
    if cached_data:
        return cached_data
    
    # Cache miss - fetch the logo
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print("Request failed:", e)
        return None

    html = resp.text
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find('meta', attrs={'name': 'twitter:image'})
    if not meta:
        print("Meta tag 'twitter:image' not found")
        return None

    content = meta.get('content')
    # Store in cache before returning (1 hour TTL)
    if content:
        market_cache.set(symbol, 'company_logo', content)
    return content


@client.hybrid_command(name='nepse', description='get details on nepse')
async def nepse(ctx):
    """
    Retrieves the latest NEPSE indices data and sends it as an embed message.
    """
    await ctx.defer()
    # Fetch the webpage content
    url = "https://www.sharesansar.com/market"  # URL to scrape
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "lxml")

    # Find the table that contains the indices data
    all_tables = soup.find_all(
        "table", class_="table table-bordered table-striped table-hover"
    )
    # Assuming the first table is the main indices
    main_indices = all_tables[0]

    # Extract all the rows (skipping the header)
    main_indices_rows = main_indices.find_all("tr")[1:]

    # Create an embed object with better formatting
    embed = discord.Embed(
        title="📊 NEPSE Index Data",
        description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        color=discord.Color.blue()
    )

    # Iterate through each row and extract the data
    for idx, tr in enumerate(main_indices_rows):
        tds = tr.find_all("td")
        index_name = tds[0].text.strip()
        open_val = tds[1].text.strip()
        high_val = tds[2].text.strip()
        low_val = tds[3].text.strip()
        close_val = tds[4].text.strip()
        point_change = tds[5].text.strip()
        pct_change = tds[6].text.strip()
        turnover = tds[7].text.strip()
        
        # Determine trend emoji
        try:
            pct_float = float(pct_change.replace('%', '').replace('+', ''))
            trend_emoji = "📈" if pct_float > 0 else "📉" if pct_float < 0 else "➡️"
            color_indicator = "🟢" if pct_float > 0 else "🔴" if pct_float < 0 else "⚪"
        except:
            trend_emoji = "📊"
            color_indicator = "⚪"
        
        # Add each index's data as a field in the embed
        embed.add_field(
            name=f"{color_indicator} {index_name}",
            value=(
                f"**Close:** {close_val} {trend_emoji}\n"
                f"**Change:** {point_change} ({pct_change})\n"
                f"**Range:** {low_val} - {high_val}\n"
                f"**Turnover:** {format_number(turnover)}"
            ),
            inline=True
        )
        
        # Add separator after every 2 indices for better readability
        if (idx + 1) % 2 == 0 and idx < len(main_indices_rows) - 1:
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                value="",
                inline=False
            )

    embed.set_footer(
        text=f"As of: {get_ss_time()} • Data from ShareSansar",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    # Send the embed to the channel
    await ctx.reply(embed=embed)


def get_ss_time():
    response3 = requests.get(
        "https://www.sharesansar.com/market-summary", timeout=10)
    soup3 = BeautifulSoup(response3.text, "lxml")
    summary_cont = soup3.find("div", id="market_symmary_data")
    last_mktsum = ""
    if summary_cont is not None:
        msdate = summary_cont.find("h5").find("span")
        if msdate is not None:
            last_mktsum = msdate.text
    return last_mktsum


def get_sub_index_details(subindex_name):
    subindex_name = subindex_name.upper()
    
    # Try to get from cache first
    cached_data = market_cache.get(subindex_name, 'sub_indices')
    if cached_data:
        return cached_data
    
    # Cache miss - scrape the data
    response4 = requests.get("https://www.sharesansar.com/market", timeout=10)
    soup4 = BeautifulSoup(response4.text, "lxml")
    alltable = soup4.find_all(
        "table", class_="table table-bordered table-striped table-hover"
    )
    sub_indices = alltable[3]
    sub_indices_rows = sub_indices.find_all("tr")
    for tr in sub_indices_rows[1:]:
        tds = tr.find_all("td")
        sub_index_mapping = {
            "BANKING": "Banking SubIndex",
            "DEVBANK": "Development Bank Index",
            "FINANCE": "Finance Index",
            "HOTELS AND TOURISM": "Hotels And Tourism",
            "HYDROPOWER": "HydroPower Index",
            "INVESTMENT": "Investment",
            "LIFE INSURANCE": "Life Insurance",
            "MANUFACTURING AND PROCESSING": "Manufacturing And Processing",
            "MICROFINANCE": "Microfinance Index",
            "MUTUAL FUND": "Mutual Fund",
            "NONLIFE INSURANCE": "Non Life Insurance",
            "OTHERS": "Others Index",
            "TRADING": "Trading Index",
        }
        subindex_name = sub_index_mapping.get(subindex_name, subindex_name)
        if tds[0].text.upper() == subindex_name.upper():
            sub_index_details = {
                "Sub Index": tds[0].text,
                "Open": tds[1].text,
                "High": tds[2].text,
                "Low": tds[3].text,
                "close": tds[4].text,
                "Pt.Change": tds[5].text,
                "% change": tds[6].text,
                "Turnover": tds[7].text,
            }
            # Store in cache before returning
            market_cache.set(subindex_name, 'sub_indices', sub_index_details)
            return sub_index_details
    return None


# Define your subindex options with only keys for autocomplete
subindex_options = [
    "BANKING",
    "DEVBANK",
    "FINANCE",
    "HOTELS AND TOURISM",
    "HYDROPOWER",
    "INVESTMENT",
    "LIFE INSURANCE",
    "MANUFACTURING AND PROCESSING",
    "MICROFINANCE",
    "MUTUAL FUND",
    "NONLIFE INSURANCE",
    "OTHERS",
    "TRADING"
]


@client.hybrid_command(name='subidx', description='Get subindex details')
@app_commands.describe(subindex_name='The name of the subindex')
async def subidx(ctx, *, subindex_name: str):
    await ctx.defer()
    sub_index_details = get_sub_index_details(subindex_name)
    if sub_index_details is None:
        await ctx.reply(f"The particular subindex : `{subindex_name}` doesn't exist or there might be a typo.🤔\nPlease use `!helpntb` to see the correct format! 📜")
        return
    o = round(float(sub_index_details["Open"].replace(",", "")), 2)
    h = round(float(sub_index_details["High"].replace(",", "")), 2)
    c = round(float(sub_index_details["close"].replace(",", "")), 2)
    embedcolor = discord.Color.red() if o > c or o > h else discord.Color.green()
    embed = discord.Embed(
        title=f"Data for {sub_index_details['Sub Index']}", color=embedcolor
    )
    for key in list(sub_index_details.keys())[1:]:

        embed.add_field(
            name=key,
            value=sub_index_details[key],
            inline=True,
        )
    embed.set_footer(text=f"As of: {get_ss_time()}")
    await ctx.reply(embed=embed)


@subidx.autocomplete('subindex_name')
async def subindex_autocomplete(interaction: discord.Interaction, current: str):
    options = [key for key in subindex_options if current.lower()
                in key.lower()]

    return [app_commands.Choice(name=key, value=key) for key in options]


async def stock_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete function for stock symbols"""
    # Fetch all available stock symbols
    symbols = fetch_stock_symbols()
    
    # Filter symbols based on user input (case-insensitive)
    current_upper = current.upper()
    filtered = [s for s in symbols if current_upper in s.upper()]
    
    # Discord allows max 25 choices, so limit results
    filtered = filtered[:25]
    
    # Return as Choice objects
    return [app_commands.Choice(name=symbol, value=symbol) for symbol in filtered]


# ============================================
# View Chart Button and Enhanced Action Buttons
# ============================================

class StockActionButtons(discord.ui.View):
    """Enhanced view with multiple action buttons for stock details"""
    def __init__(self, symbol: str, current_price: float = None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.symbol = symbol
        self.current_price = current_price
    
    @discord.ui.button(label="📊 View Chart", style=discord.ButtonStyle.primary)
    async def view_chart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle chart button click"""
        await interaction.response.defer(ephemeral=False)
        
        # Generate chart with default 90 days
        days = 90
        loop = interaction.client.loop
        filename, result = await loop.run_in_executor(None, generate_candlestick_chart, self.symbol.upper(), days)
        
        if filename is None:
            # Error occurred
            error_embed = discord.Embed(
                title="❌ Chart Generation Failed",
                description=f"**Error:** {result}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        
        try:
            # Get latest price info from the data
            payload = fetch_all_chart_data(self.symbol.upper(), 1)
            latest = payload['data']['content'][0] if payload['data']['content'] else {}
            
            current_price = latest.get('close', 'N/A')
            change = latest.get('change', 'N/A')
            change_percent = latest.get('changePercent', 'N/A')
            volume = latest.get('volume', 'N/A')
            
            # Fetch company logo
            company_url = f"https://sharehubnepal.com/company/{self.symbol.strip().upper()}"
            img_url = await loop.run_in_executor(None, fetch_and_extract_image, company_url)
            
            # Format change color
            if isinstance(change, (int, float)):
                change_color = discord.Color.green() if change >= 0 else discord.Color.red()
                change_emoji = "📈" if change >= 0 else "📉"
                change_text = f"{change_emoji} **{change:+.2f}** ({change_percent:+.2f}%)"
            else:
                change_color = discord.Color.blue()
                change_text = "N/A"
            
            # Create embed
            embed = discord.Embed(
                title=f"📊 {self.symbol.upper()} - {result} Days Chart",
                description=change_text,
                color=change_color,
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(name="💰 Current Price", value=f"Rs. {current_price}", inline=True)
            embed.add_field(name="📊 Volume", value=f"{volume:,}" if isinstance(volume, int) else volume, inline=True)
            embed.add_field(name="📅 Period", value=f"{result} trading days", inline=True)
            
            # Set company logo as thumbnail if available
            if img_url:
                embed.set_thumbnail(url=img_url)
            
            embed.set_footer(text=f"Requested by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            # Send chart as file with embed
            file = discord.File(filename, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            
            await interaction.followup.send(embed=embed, file=file)
            
            # Clean up the file after sending
            if os.path.exists(filename):
                os.remove(filename)
                
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error Sending Chart",
                description=f"Chart generated but failed to send: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            
            # Still try to clean up
            if os.path.exists(filename):
                os.remove(filename)
    
    @discord.ui.button(label="🔔 Set Alert", style=discord.ButtonStyle.success)
    async def set_alert_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle set alert button click"""
        await interaction.response.send_modal(SetAlertModal(self.symbol, self.current_price))
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle refresh button click"""
        await interaction.response.defer()
        # Clear cache for this stock
        market_cache.clear('stock_details')
        await interaction.followup.send(f"🔄 Refreshing data for **{self.symbol}**...", ephemeral=True)


class SetAlertModal(discord.ui.Modal, title="Set Price Alert"):
    """Modal for setting price alerts"""
    def __init__(self, symbol: str, current_price: float = None):
        super().__init__()
        self.symbol = symbol
        self.current_price = current_price
        
        # Add input field
        self.target_price = discord.ui.TextInput(
            label="Target Price (Rs.)",
            placeholder=f"Current: {current_price if current_price else 'N/A'}" if current_price else "Enter target price",
            required=True,
            min_length=1,
            max_length=10
        )
        self.add_item(self.target_price)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = float(self.target_price.value)
            user_id = interaction.user.id
            
            if user_id not in user_alerts:
                user_alerts[user_id] = {}
            if self.symbol not in user_alerts[user_id]:
                user_alerts[user_id][self.symbol] = []
            
            user_alerts[user_id][self.symbol].append(target)
            
            # Calculate distance to target
            distance_text = ""
            if self.current_price:
                diff = target - self.current_price
                percent = (diff / self.current_price) * 100
                distance_text = f"\n📊 **Distance:** {diff:+.2f} ({percent:+.2f}%) to reach target"
            
            embed = discord.Embed(
                title="🔔 Alert Created Successfully",
                description=f"📌 **Stock:** {self.symbol}\n🎯 **Target:** Rs. {target:,.2f}{distance_text}",
                color=discord.Color.green()
            )
            embed.set_footer(text="You'll receive a DM when the target is reached")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid price! Please enter a valid number.",
                ephemeral=True
            )


class ViewChartButton(discord.ui.View):
    """Simple view with a button to display stock chart (for backward compatibility)"""
    def __init__(self, symbol: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.symbol = symbol
    
    @discord.ui.button(label="📊 View Chart", style=discord.ButtonStyle.primary)
    async def view_chart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle chart button click"""
        await interaction.response.defer(ephemeral=False)
        
        # Generate chart with default 90 days
        days = 90
        loop = interaction.client.loop
        filename, result = await loop.run_in_executor(None, generate_candlestick_chart, self.symbol.upper(), days)
        
        if filename is None:
            # Error occurred
            error_embed = discord.Embed(
                title="❌ Chart Generation Failed",
                description=f"**Error:** {result}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        
        try:
            # Get latest price info from the data
            payload = fetch_all_chart_data(self.symbol.upper(), 1)
            latest = payload['data']['content'][0] if payload['data']['content'] else {}
            
            current_price = latest.get('close', 'N/A')
            change = latest.get('change', 'N/A')
            change_percent = latest.get('changePercent', 'N/A')
            volume = latest.get('volume', 'N/A')
            
            # Fetch company logo
            company_url = f"https://sharehubnepal.com/company/{self.symbol.strip().upper()}"
            img_url = await loop.run_in_executor(None, fetch_and_extract_image, company_url)
            
            # Format change color
            if isinstance(change, (int, float)):
                change_color = discord.Color.green() if change >= 0 else discord.Color.red()
                change_emoji = "📈" if change >= 0 else "📉"
                change_text = f"{change_emoji} **{change:+.2f}** ({change_percent:+.2f}%)"
            else:
                change_color = discord.Color.blue()
                change_text = "N/A"
            
            # Create embed
            embed = discord.Embed(
                title=f"📊 {self.symbol.upper()} - {result} Days Chart",
                description=change_text,
                color=change_color,
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(name="💰 Current Price", value=f"Rs. {current_price}", inline=True)
            embed.add_field(name="📊 Volume", value=f"{volume:,}" if isinstance(volume, int) else volume, inline=True)
            embed.add_field(name="📅 Period", value=f"{result} trading days", inline=True)
            
            # Set company logo as thumbnail if available
            if img_url:
                embed.set_thumbnail(url=img_url)
            
            embed.set_footer(text=f"Requested by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            # Send chart as file with embed
            file = discord.File(filename, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            
            await interaction.followup.send(embed=embed, file=file)
            
            # Clean up the file after sending
            if os.path.exists(filename):
                os.remove(filename)
                
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error Sending Chart",
                description=f"Chart generated but failed to send: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            
            # Still try to clean up
            if os.path.exists(filename):
                os.remove(filename)


def get_stock_details(stock_name):
    # if stock_name.upper()=="NEPSE":
    #     return None
    
    # Try to get from cache first
    cached_data = market_cache.get(stock_name.upper(), 'stock_details')
    if cached_data:
        return cached_data
    
    # Cache miss - scrape the data
    response = requests.get(
        "https://www.sharesansar.com/live-trading", timeout=10)
    response2 = requests.get(
        f"https://www.sharesansar.com/company/{stock_name}", timeout=10)

    soup = BeautifulSoup(response.text, "lxml")
    soup2 = BeautifulSoup(response2.text, "lxml")

    # Check if the response for the stock details page was successful
    if response2.status_code != 200:
        return None  # Stock not found

    all_rows = soup2.find_all("div", class_="row")
    if len(all_rows) < 6:  # If there's not enough data
        return None

    info_row = all_rows[5]
    second_row = info_row.find_all("div", class_="col-md-12")
    shareinfo = second_row[1]
    heading_list = shareinfo.find_all("h4")
    company_full_form_tag = soup2.find(
        "h1", style="color: #333;font-size: 20px;font-weight: 600;"
    )
    company_fullform = ""
    if company_full_form_tag is not None:
        company_fullform = company_full_form_tag.text
    else:
        print("NO details Found")

    company_details = {
        "sector": heading_list[1].find("span", class_="text-org").text,
        "share registrar": heading_list[2].find("span", class_="text-org").text,
        "company fullform": company_fullform,
    }
    stock_rows = soup.find_all("tr")
    time_stamp = soup.find(id="dDate")
    if time_stamp is not None:
        last_updated = time_stamp.text
    else:
        last_updated = "Date not Found"

    upper_stonk = stock_name.upper()

    for row in stock_rows[1:]:
        row_data = row.find_all("td")

        if row_data[1].text.strip() == upper_stonk:
            stock_details = {
                "Symbol": row_data[1].text.strip(),
                "Last Traded Price": row_data[2].text.strip(),
                "Pt Change": row_data[3].text.strip(),
                "% Change": row_data[4].text.strip(),
                "Open": row_data[5].text.strip(),
                "High": row_data[6].text.strip(),
                "Low": row_data[7].text.strip(),
                "Volume": row_data[8].text.strip(),
                "Prev.Closing": row_data[9].text.strip(),
                "As of": last_updated,
                "Sector": company_details["sector"],
                "Share Registrar": company_details["share registrar"],
                "Company fullform": company_details["company fullform"],
            }
            # Store in cache before returning
            market_cache.set(stock_name.upper(), 'stock_details', stock_details)
            return stock_details

    return None  # Return None if the stock was not found


@client.event
async def on_ready():
    # Only start the background task if it's not already running
    if not check_stock_alerts.is_running():
        check_stock_alerts.start()
    print(f"Logged in as {client.user}")
    print("Our Bot is Ready to use")
    print("-----------------------")


def get_market_summary():
    # Try to get from cache first
    cached_data = market_cache.get('market_summary', 'market_summary')
    if cached_data:
        return cached_data
    
    # Cache miss - scrape the data
    response3 = requests.get(
        "https://www.sharesansar.com/market-summary", timeout=10)
    soup3 = BeautifulSoup(response3.text, "lxml")
    summary_cont = soup3.find("div", id="market_symmary_data")
    last_mktsum = ""
    if summary_cont is not None:
        msdate = summary_cont.find("h5").find("span")
        if msdate is not None:
            last_mktsum = msdate.text
    data_sum = soup3.find_all("td")
    market_summary = {
        "As of": last_mktsum,
        f"{data_sum[0].text}": f"{data_sum[1].text}",
        f"{data_sum[2].text}": f"{data_sum[3].text}",
        f"{data_sum[4].text}": f"{data_sum[5].text}",
        f"{data_sum[6].text}": f"{data_sum[7].text}",
        f"{data_sum[8].text}": f"{data_sum[9].text}",
        f"{data_sum[10].text}": f"{data_sum[11].text}",
    }
    # Store in cache before returning
    market_cache.set('market_summary', 'market_summary', market_summary)
    return market_summary


@client.hybrid_command(name='mktsum', description='Get market summary')
async def mktsum(ctx):
    await ctx.defer()
    market_summary = get_market_summary()

    if not market_summary:
        embed = discord.Embed(
            title="❌ Data Unavailable",
            description="No market summary data found.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)
        return

    # Create enhanced embed with better structure
    embed = discord.Embed(
        title="📊 NEPSE Market Summary",
        description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        color=discord.Color.blue()
    )

    # Parse and format values
    try:
        turnover = market_summary["Total Turnovers (Rs.)"]
        shares = market_summary["Total Traded Shares "]
        transactions = market_summary["Total Transaction "]
        scrips = market_summary["Total Scrips Traded "]
        market_cap = market_summary["Total Market Cap (Rs.)"]
        float_cap = market_summary["Floated Market Cap (Rs.)"]
        
        # Trading Activity Section
        embed.add_field(
            name="💰 TRADING ACTIVITY",
            value=(
                f"**💵 Turnover:** {format_number(turnover)}\n"
                f"**📊 Volume:** {format_number(shares)}\n"
                f"**🔄 Transactions:** {transactions:,}\n"
                f"**📈 Scrips Traded:** {scrips}"
            ),
            inline=False
        )
        
        # Market Capitalization Section
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            value="",
            inline=False
        )
        
        embed.add_field(
            name="💎 MARKET CAPITALIZATION",
            value=(
                f"**🏦 Total Market Cap:** {format_number(market_cap)}\n"
                f"**🌊 Floated Market Cap:** {format_number(float_cap)}"
            ),
            inline=False
        )
        
        # Calculate float ratio if possible
        try:
            mc_val = float(market_cap.replace(',', ''))
            fc_val = float(float_cap.replace(',', ''))
            float_ratio = (fc_val / mc_val) * 100
            embed.add_field(
                name="📊 Float Ratio",
                value=f"{float_ratio:.2f}%",
                inline=False
            )
        except:
            pass
            
    except:
        # Fallback to simple display if parsing fails
        embed.add_field(
            name="Total Turnovers (Rs.)",
            value=market_summary["Total Turnovers (Rs.)"],
            inline=True,
        )
        embed.add_field(
            name="Total Traded Shares",
            value=market_summary["Total Traded Shares "],
            inline=True,
        )
        embed.add_field(
            name="Total Transactions",
            value=market_summary["Total Transaction "],
            inline=True,
        )
        embed.add_field(
            name="Total Scrips Traded",
            value=market_summary["Total Scrips Traded "],
            inline=True,
        )
        embed.add_field(
            name="Total Market Cap (Rs.)",
            value=market_summary["Total Market Cap (Rs.)"],
            inline=True,
        )
        embed.add_field(
            name="Floated Market Cap (Rs.)",
            value=market_summary["Floated Market Cap (Rs.)"],
            inline=True,
        )
    
    embed.set_footer(
        text=f"As of: {market_summary['As of']} • Data from ShareSansar",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    await ctx.reply(embed=embed)


@client.hybrid_command(name='stonk', description='get info about a stock')
@app_commands.describe(stock_name='Enter stock symbol (e.g., NABIL, NICA)')
@app_commands.autocomplete(stock_name=stock_autocomplete)
async def stonk(ctx, *, stock_name: str):
    """
    this command retreives data for a specific stock
    """
    await ctx.defer()
    if stock_name.upper() == "NEPSE":
        await ctx.reply("📊 For details on NEPSE, use `!nepse` or use `!mktsum` to get the market summary. 📈")
        return
    stock_details = get_stock_details(stock_name)
    Embedcolor = discord.Color.default()
    ud_emoji = ""
    pt_prefix = ""
    
    # Fetch company logo
    company_url = f"https://sharehubnepal.com/company/{stock_name.strip().upper()}"
    loop = ctx.bot.loop
    img_url = await loop.run_in_executor(None, fetch_and_extract_image, company_url)

    # Check if stock details were found
    if stock_details is None:
        await ctx.reply(f"⚠️ Stock '{stock_name.upper()}' not found. Please ensure the stock name is correct.")
        return

    company_name = extract_stock_name(stock_details["Company fullform"])
    try:
        last_traded_price = round(
            float(stock_details["Last Traded Price"].replace(",", "")), 2)
        prev_closing = round(
            float(stock_details["Prev.Closing"].replace(",", "")), 2)
        open_price = round(float(stock_details["Open"].replace(",", "")), 2)
        high_price = round(float(stock_details["High"].replace(",", "")), 2)
        low_price = round(float(stock_details["Low"].replace(",", "")), 2)
        volume = stock_details["Volume"].replace(",", "")
        pt_change = float(stock_details["Pt Change"].replace(",", ""))
        pct_change = stock_details["% Change"]

        if last_traded_price > prev_closing:
            ud_emoji = "📈"
            pt_prefix = "+"
            Embedcolor = discord.Color.green()
        elif last_traded_price==prev_closing:
            ud_emoji = "🟰"
            Embedcolor = discord.Color.light_grey()
        else:
            ud_emoji = "📉"
            Embedcolor = discord.Color.red()
    except (KeyError, ValueError) as e:
        await ctx.reply("Error processing stock data. Please ensure the stock name is correct.", e)
        return

    embed = discord.Embed(
        title=f"Details of {stock_name.upper()} (*Click for more info*)",
        description=f"**Company**: {company_name}\n**Sector**: {stock_details['Sector']}\n**Share Registrar**: {stock_details['Share Registrar']}\n*[Click here to view technical chart](https://nepsealpha.com/trading/chart?symbol={stock_details['Symbol']})*",
        color=Embedcolor,
        url=f"https://merolagani.com/CompanyDetail.aspx?symbol={stock_details['Symbol']}",
    )
    embed.add_field(
        name=list(stock_details.keys())[0],
        value=stock_details["Symbol"],
        inline=True,
    )
    embed.add_field(
        name=list(stock_details.keys())[1],
        value=f"{stock_details['Last Traded Price']} {ud_emoji}",
        inline=True,
    )
    embed.add_field(
        name=list(stock_details.keys())[2],
        value=f"{pt_prefix}{stock_details['Pt Change']}",
        inline=True,
    )
    embed.add_field(
        name=list(stock_details.keys())[
            4], value=stock_details["Open"], inline=True
    )
    embed.add_field(
        name=list(stock_details.keys())[
            5], value=stock_details["High"], inline=True
    )
    embed.add_field(
        name=list(stock_details.keys())[
            6], value=stock_details["Low"], inline=True
    )
    embed.add_field(
        name=list(stock_details.keys())[3],
        value=stock_details["% Change"],
        inline=True,
    )
    embed.add_field(
        name=list(stock_details.keys())[7],
        value=stock_details["Volume"],
        inline=True,
    )
    embed.add_field(
        name=list(stock_details.keys())[8],
        value=stock_details["Prev.Closing"],
        inline=True,
    )
    
    # Set company logo as thumbnail if available
    if img_url:
        embed.set_thumbnail(url=img_url)
    
    embed.set_footer(text=f"Last updated: {stock_details['As of']}")

    # Create view with enhanced action buttons
    view = StockActionButtons(stock_name.upper(), last_traded_price)
    await ctx.reply(embed=embed, view=view)


@client.hybrid_command(name='chart', description='Generate a candlestick chart for a stock symbol')
@app_commands.describe(
    symbol='Stock ticker symbol (e.g., PRIN, NABIL, NICA)',
    days='Number of trading days (1-365, default: 90)'
)
@app_commands.autocomplete(symbol=stock_autocomplete)
async def chart(ctx, symbol: str = None, days: int = 90):
	"""
	Generate and send a candlestick chart
	Usage: !chart PRIN 30 or /chart PRIN 30
	"""
	await ctx.defer()
	
	# Validate symbol
	if symbol is None:
		embed = discord.Embed(
			title="❌ Missing Symbol",
			description="Please provide a stock symbol!\n\n**Usage:** `!chart PRIN 30` or `/chart PRIN 30`",
			color=discord.Color.red()
		)
		await ctx.reply(embed=embed)
		return
	
	# Validate days
	if days < 1 or days > 365:
		embed = discord.Embed(
			title="❌ Invalid Days",
			description="Days must be between 1 and 365!",
			color=discord.Color.red()
		)
		await ctx.reply(embed=embed)
		return
	
	# Check bot permissions in guild channels
	if ctx.guild is not None:
		bot_member = ctx.guild.get_member(ctx.bot.user.id)
		permissions = ctx.channel.permissions_for(bot_member)
		
		if not permissions.send_messages:
			try:
				await ctx.author.send("❌ I don't have permission to send messages in that channel!")
			except:
				pass
			return
		
		if not permissions.embed_links:
			try:
				await ctx.reply("❌ I need **Embed Links** permission to send charts! Please contact a server admin.")
			except:
				pass
			return
		
		if not permissions.attach_files:
			try:
				embed = discord.Embed(
					title="❌ Missing Permissions",
					description="I need **Attach Files** permission to send charts!\nPlease contact a server admin.",
					color=discord.Color.red()
				)
				await ctx.reply(embed=embed)
			except:
				pass
			return
	
	# Send processing message
	try:
		processing_embed = discord.Embed(
			title="⏳ Generating Chart...",
			description=f"Fetching {days} days of data for **{symbol.upper()}**...",
			color=discord.Color.blue()
		)
		processing_msg = await ctx.reply(embed=processing_embed)
	except discord.Forbidden:
		await ctx.reply(f"⏳ Generating {days}-day chart for {symbol.upper()}...")
		processing_msg = None
	
	# Generate chart in executor to avoid blocking
	loop = ctx.bot.loop
	filename, result = await loop.run_in_executor(None, generate_candlestick_chart, symbol.upper(), days)
	
	if filename is None:
		# Error occurred
		try:
			error_embed = discord.Embed(
				title="❌ Chart Generation Failed",
				description=f"**Error:** {result}",
				color=discord.Color.red()
			)
			if processing_msg:
				await processing_msg.edit(embed=error_embed)
			else:
				await ctx.reply(f"❌ Chart generation failed: {result}")
		except discord.Forbidden:
			await ctx.reply(f"❌ Chart generation failed: {result}")
		return
	
	# Chart generated successfully
	try:
		# Get latest price info from the data
		payload = fetch_all_chart_data(symbol.upper(), 1)
		latest = payload['data']['content'][0] if payload['data']['content'] else {}
		
		current_price = latest.get('close', 'N/A')
		change = latest.get('change', 'N/A')
		change_percent = latest.get('changePercent', 'N/A')
		volume = latest.get('volume', 'N/A')
		
		# Fetch company logo (same logic as in stonk command)
		company_url = f"https://sharehubnepal.com/company/{symbol.strip().upper()}"
		loop = ctx.bot.loop
		img_url = await loop.run_in_executor(None, fetch_and_extract_image, company_url)
		
		# Format change color
		if isinstance(change, (int, float)):
			change_color = discord.Color.green() if change >= 0 else discord.Color.red()
			change_emoji = "📈" if change >= 0 else "📉"
			change_text = f"{change_emoji} **{change:+.2f}** ({change_percent:+.2f}%)"
		else:
			change_color = discord.Color.blue()
			change_text = "N/A"
		
		# Create embed
		embed = discord.Embed(
			title=f"📊 {symbol.upper()} - {result} Days Chart",
			description=change_text,
			color=change_color,
			timestamp=datetime.now(timezone.utc)
		)
		
		embed.add_field(name="💰 Current Price", value=f"Rs. {current_price}", inline=True)
		embed.add_field(name="📊 Volume", value=f"{volume:,}" if isinstance(volume, int) else volume, inline=True)
		embed.add_field(name="📅 Period", value=f"{result} trading days", inline=True)
		
		# Set company logo as thumbnail if available (same as stonk command)
		if img_url:
			embed.set_thumbnail(url=img_url)
		
		# embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
		embed.set_footer(text=f"As of: {get_ss_time()}")
		# Send chart as file with embed
		file = discord.File(filename, filename=filename)
		embed.set_image(url=f"attachment://{filename}")
		
		# Delete processing message if it exists
		if processing_msg:
			try:
				await processing_msg.delete()
			except:
				pass
		
		await ctx.reply(embed=embed, file=file)
		
		# Clean up the file after sending
		if os.path.exists(filename):
			os.remove(filename)
			
	except discord.Forbidden:
		# Permission error - send plain text
		try:
			await ctx.reply(f"❌ Missing permissions! I need 'Embed Links' and 'Attach Files' permissions to send charts.")
		except:
			pass
		# Clean up
		if os.path.exists(filename):
			os.remove(filename)
	except Exception as e:
		try:
			error_embed = discord.Embed(
				title="❌ Error Sending Chart",
				description=f"Chart generated but failed to send: {str(e)}",
				color=discord.Color.red()
			)
			if processing_msg:
				await processing_msg.edit(embed=error_embed)
			else:
				await ctx.reply(f"❌ Error: {str(e)}")
		except:
			await ctx.reply(f"❌ Error: {str(e)}")
		
		# Still try to clean up
		if os.path.exists(filename):
			os.remove(filename)


@client.hybrid_command(name='charthelp', description='Show help for the chart command')
async def charthelp(ctx):
	"""Show help for the chart command"""
	await ctx.defer()
	embed = discord.Embed(
		title="📊 Candlestick Chart Command Help",
		description="Generate beautiful candlestick charts for Nepal stock market",
		color=discord.Color.blue()
	)
	
	embed.add_field(
		name="📝 Usage",
		value="`!chart <SYMBOL> [DAYS]` or `/chart <SYMBOL> [DAYS]`",
		inline=False
	)
	
	embed.add_field(
		name="📋 Examples",
        value=(
            "`!chart PRIN` or `/chart PRIN` - 90 days chart (default)\n"
            "`!chart PRIN 30` or `/chart PRIN 30` - 30 days chart\n"
            "`!chart NABIL 90` or `/chart NABIL 90` - 90 days chart"
        ),
		inline=False
	)
	
	embed.add_field(
		name="ℹ️ Parameters",
		value=(
            "**SYMBOL** - Stock ticker symbol (e.g., PRIN, NABIL, NICA)\n"
            "**DAYS** - Number of trading days (1-365, default: 90)"
		),
		inline=False
	)
	
	embed.add_field(
		name="📈 Chart Features",
		value=(
			"• OHLC (Open, High, Low, Close) candlestick chart\n"
			"• Volume bars\n"
			"• Current price and change percentage\n"
			"• Yahoo Finance style theme"
		),
		inline=False
	)
	
	await ctx.reply(embed=embed)


@client.hybrid_command(name='helpntb', description='Get help and information about available commands.')
async def helpntb(ctx):
    await ctx.defer()

    embed = discord.Embed(
        title="📚 NEPSE Bot Command Guide",
        description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nComprehensive guide to all available commands",
        color=discord.Color(0x00FFFF)
    )

    # !nepse command
    embed.add_field(
        name="1. !nepse or /nepse",
        value=(
            "**Description:** Retrieves the latest NEPSE indices data.\n"
            "**Data Provided:** NEPSE Index, Sensitive Index, Float Index, Sensitive Float Index.\n"
            "**Usage:** Type `!nepse` or `/nepse`."
        ),
        inline=False
    )

    # !stonk command
    embed.add_field(
        name="2. !stonk <stock_symbol> or /stonk <stock_symbol>",
        value=(
            "**Description:** Provides detailed info about a specific stock listed on NEPSE.\n"
            "**Usage:** Type `!stonk <stock_symbol>` or `/stonk <stock_symbol>` (e.g., `!stonk UNL` or `/stonk UNL`).\n"
            "**Note:** stock_symbols are case-insensitive."
        ),
        inline=False
    )

    # !subidx command
    embed.add_field(
        name="3. !subidx <subindex_name> or /subidx <subindex_name>",
        value=(
            "**Description:** Get details of a specific sub-index.\n"
            "**Usage:** Type `!subidx <subindex_name>` or `/subidx <subindex_name>` (e.g., `!subidx BANKING` or `/subidx BANKING`).\n"
            "**Note:** Use the abbreviations listed below (case insensitive):\n"
            " - **BANKING**: Banking SubIndex\n"
            " - **DEVBANK**: Development Bank Index\n"
            " - **FINANCE**: Finance Index\n"
            " - **HOTELS AND TOURISM**: Hotels And Tourism\n"
            " - **HYDROPOWER**: HydroPower Index\n"
            " - **INVESTMENT**: Investment\n"
            " - **LIFE INSURANCE**: Life Insurance\n"
            " - **MANUFACTURING AND PROCESSING**: Manufacturing And Processing\n"
            " - **MICROFINANCE**: Microfinance Index\n"
            " - **MUTUAL FUND**: Mutual Fund\n"
            " - **NONLIFE INSURANCE**: Non Life Insurance\n"
            " - **OTHERS**: Others Index\n"
            " - **TRADING**: Trading Index"
        ),
        inline=False
    )

    # !mktsum command
    embed.add_field(
        name="4. !mktsum or /mktsum",
        value=(
            "**Description:** Provides a Market summary of NEPSE's overall performance.\n"
            "**Data Provided:** Total Turnovers, Total Traded Shares, Total Transactions, Total Scrips Traded, Total Market Cap, and Floated Market Cap.\n"
            "**Usage:** Type `!mktsum` or `/mktsum`."
        ),
        inline=False
    )

    # !setalert command
    embed.add_field(
        name="5. !setalert <stock_name> <target_price> or /setalert <stock_name> <target_price>",
        value=(
            "**Description:** Sets an alert for a specific stock when it reaches a target price.\n"
            "`*The bot will send you a DM after your stock price reaches the target price.*`\n"
            "**Usage:** Type `!setalert <stock_name> <target_price>` or `/setalert <stock_name> <target_price>` (e.g., `!setalert NFS 5000` or `/setalert NFS 5000`)."
        ),
        inline=False
    )

    # !showalerts command
    embed.add_field(
        name="6. !showalerts or /showalerts",
        value=(
            "**Description:** Displays all active alerts for the user.\n"
            "**Usage:** Type `!showalerts` or `/showalerts`."
        ),
        inline=False
    )

    # !removealert command
    embed.add_field(
        name="7. !removealert <stock_name> or /removealert <stock_name>",
        value=(
            "**Description:** Removes an alert for a specific stock.\n"
            "**Usage:** Type `!removealert <stock_name>` or `/removealert <stock_name>` \n(e.g., `!removealert UNL` or `/removealert UNL`)."
        ),
        inline=False
    )

    # !topgl command
    embed.add_field(
        name="8. !topgl or /topgl",
        value=(
            "**Description:** Displays the top 10 gainers and top 10 losers in the market.\n"
            "**Usage:** Type `!topgl` or `/topgl`."
        ),
        inline=False
    )

    # !chart command
    embed.add_field(
        name="9. !chart <symbol> [days] or /chart <symbol> [days]",
        value=(
            "**Description:** Generate a candlestick chart for a stock symbol.\n"
            "**Usage:** Type `!chart PRIN 30` or `/chart PRIN 30` (e.g., `!chart NABIL 90` or `/chart NABIL 90`).\n"
            "**Parameters:** symbol (required), days (optional, 1-365, default: 7)\n"
            "**Features:** OHLC chart with volume, current price, and change %."
        ),
        inline=False
    )

    # !charthelp command
    embed.add_field(
        name="10. !charthelp or /charthelp",
        value=(
            "**Description:** Show detailed help for the chart command.\n"
            "**Usage:** Type `!charthelp` or `/charthelp`."
        ),
        inline=False
    )

    embed.set_footer(
        text="Both traditional commands (starting with !) and slash commands (starting with /) are supported. Use whichever you prefer!")

    await ctx.reply(embed=embed)


def get_stock_price(stock_name):
    response = requests.get(
        "https://www.sharesansar.com/live-trading", timeout=10)
    soup = BeautifulSoup(response.text, 'lxml')
    df = soup.find('tbody')
    stock_rows = df.find_all('tr')
    for row in stock_rows:
        row_data = row.find_all('td')  # All <td> in the current row
        # Use upper to match stock names
        if row_data[1].text.strip().upper() == stock_name.upper():
            return round(float(row_data[2].text.strip().replace(',', '')), 2)
    return None


@tasks.loop(seconds=30)
async def check_stock_alerts():
    for user_id, alerts in user_alerts.items():
        # Collect stocks to remove after checking prices
        stocks_to_remove = []
        for stock_name, target_prices in alerts.items():
            current_price = get_stock_price(stock_name)
            if current_price is not None:
                # Iterate over a copy of target_prices
                for target_price in target_prices[:]:
                    if current_price >= target_price:  # Check for exact price match
                        user = await client.fetch_user(user_id)
                        await user.send(f"🔔 **ALERT!** {stock_name} has reached your target price of Rs. {target_price}. Current price: Rs. {current_price}.")
                        # Remove the alerted price
                        target_prices.remove(target_price)

                # Check if no target prices are left for this stock
                if not target_prices:
                    stocks_to_remove.append(stock_name)

        # Remove stocks after the iteration is done
        for stock_name in stocks_to_remove:
            del alerts[stock_name]


def check_stock_exists(stock_name):
    response = requests.get(
        "https://www.sharesansar.com/live-trading", timeout=10)
    soup = BeautifulSoup(response.text, 'lxml')
    df = soup.find('tbody')
    stock_rows = df.find_all('tr')  # List of all stock rows
    for row in stock_rows:
        row_data = row.find_all('td')  # All <td> in the current row
        for td in row_data:
            if td.text.strip() == stock_name.upper():
                return True
    return None


@client.hybrid_command(name='setalert', description='set alert for stocks')
@app_commands.describe(
    stock_name='Stock symbol (e.g., NABIL, NICA)',
    target_price='Target price in Rs.'
)
@app_commands.autocomplete(stock_name=stock_autocomplete)
async def setalert(ctx, stock_name: str, target_price: float):
    await ctx.defer()
    user_id = ctx.author.id
    stock_name = stock_name.upper()
    
    if check_stock_exists(stock_name) is None:
        embed = discord.Embed(
            title="❌ Stock Not Found",
            description=f"Stock **{stock_name}** doesn't exist or there may be a typo.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)
        return
    
    # Get current price for comparison
    current_price = get_stock_price(stock_name)
    
    if user_id not in user_alerts:
        user_alerts[user_id] = {}
    if stock_name not in user_alerts[user_id]:
        user_alerts[user_id][stock_name] = []
    
    # Append to the list of target prices
    user_alerts[user_id][stock_name].append(target_price)
    
    # Calculate distance to target
    distance_text = ""
    status_emoji = "🎯"
    if current_price:
        diff = target_price - current_price
        percent = (diff / current_price) * 100
        distance_text = f"\n\n📊 **Distance to Target**\n{diff:+.2f} ({percent:+.2f}%)"
        
        if percent > 5:
            status_emoji = "🟠"
        elif percent > 2:
            status_emoji = "🟡"
        elif percent > 0:
            status_emoji = "🟢"
        else:
            status_emoji = "✅"
    
    # Count total alerts
    total_alerts = sum(len(prices) for prices in user_alerts[user_id].values())
    
    embed = discord.Embed(
        title="🔔 Alert Created Successfully",
        description=(
            f"📌 **Stock:** {stock_name}\n"
            f"🎯 **Target Price:** {format_rupees(target_price)}\n"
            f"💰 **Current Price:** {format_rupees(current_price) if current_price else 'N/A'}"
            f"{distance_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{status_emoji} You'll receive a DM when **{stock_name}** reaches your target price.\n\n"
            f"📊 **Your Active Alerts:** {total_alerts}/10"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="Alert system checks every 30 seconds")
    
    await ctx.reply(embed=embed)


@client.hybrid_command(name='showalerts', description='displays your stock alerts')
async def showalerts(ctx):
    await ctx.defer()
    user_id = ctx.author.id
    
    if user_id not in user_alerts or not user_alerts[user_id]:
        embed = discord.Embed(
            title="🔔 Your Stock Alerts",
            description="You have no active alerts.\n\nUse `/setalert <stock> <price>` to create one!",
            color=discord.Color.blue()
        )
        await ctx.reply(embed=embed)
        return
    
    embed = discord.Embed(
        title="🔔 Your Stock Alerts",
        description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        color=discord.Color.blue()
    )
    
    alert_count = 0
    for stock, prices in user_alerts[user_id].items():
        current_price = get_stock_price(stock)
        
        for target in prices:
            alert_count += 1
            
            # Calculate distance and status
            status = "🎯 Pending"
            distance_text = ""
            
            if current_price:
                diff = target - current_price
                percent = (diff / current_price) * 100
                distance_text = f" ({percent:+.2f}%)"
                
                if abs(percent) < 0.5:
                    status = "✅ Near Target!"
                elif percent < 0:
                    status = "📉 Below Target"
                elif percent > 5:
                    status = f"🟠 {abs(percent):.1f}% away"
                elif percent > 2:
                    status = f"🟡 {abs(percent):.1f}% away"
                else:
                    status = f"🟢 {abs(percent):.1f}% away"
            
            embed.add_field(
                name=f"📈 {stock}",
                value=(
                    f"**Target:** {format_rupees(target)}\n"
                    f"**Current:** {format_rupees(current_price) if current_price else 'N/A'}{distance_text}\n"
                    f"**Status:** {status}"
                ),
                inline=False
            )
    
    embed.add_field(
        name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        value=f"📊 **Total Alerts:** {alert_count}/10 | ⏱️ **Check Interval:** 30 seconds",
        inline=False
    )
    
    embed.set_footer(
        text="Use /removealert <stock> to remove alerts",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )
    
    await ctx.reply(embed=embed)


@client.hybrid_command(name='removealert', description='removes alert for your script')
@app_commands.describe(stock_name='Stock symbol to remove alerts for')
@app_commands.autocomplete(stock_name=stock_autocomplete)
async def removealert(ctx, stock_name: str):
    await ctx.defer()
    user_id = ctx.author.id
    stock_name = stock_name.upper()
    
    if user_id in user_alerts and stock_name in user_alerts[user_id]:
        removed_count = len(user_alerts[user_id][stock_name])
        del user_alerts[user_id][stock_name]
        
        # Count remaining alerts
        remaining = sum(len(prices) for prices in user_alerts[user_id].values())
        
        embed = discord.Embed(
            title="✅ Alerts Removed",
            description=(
                f"🗑️ Removed **{removed_count}** alert(s) for **{stock_name}**\n\n"
                f"📊 **Remaining Alerts:** {remaining}/10"
            ),
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ No Alerts Found",
            description=f"No active alerts found for **{stock_name}**.\n\nUse `/showalerts` to see your active alerts.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)


def scrape_top_gainers_losers():
    # Try to get from cache first
    cached_data = market_cache.get('top_gl', 'top_gainers_losers')
    if cached_data:
        return cached_data
    
    # Cache miss - scrape the data
    response5 = requests.get(
        "https://merolagani.com/LatestMarket.aspx", timeout=10)
    soup5 = BeautifulSoup(response5.text, 'html.parser')

    # Extracting gainers and losers data
    tgtl_col = soup5.find('div', class_="col-md-4 hidden-xs hidden-sm")
    tgtl_tables = tgtl_col.find_all('table')

    # Gainers table
    gainers = tgtl_tables[0]
    gainers_row = gainers.find_all('tr')

    # Losers table
    losers = tgtl_tables[1]
    losers_row = losers.find_all('tr')

    gainers_data = []
    losers_data = []

    # Top losers
    for tr in losers_row[1:]:
        tds = tr.find_all('td')
        losers_data.append({
            "symbol": tds[0].text,
            "ltp": tds[1].text,
            "%chg": tds[2].text,
            "high": tds[3].text,
            "low": tds[4].text,
            "open": tds[5].text,
            "qty": tds[6].text,
            "turnover": tds[7].text
        })

    # Top gainers
    for tr in gainers_row[1:]:
        tds = tr.find_all('td')
        gainers_data.append({
            "symbol": tds[0].text,
            "ltp": tds[1].text,
            "%chg": tds[2].text,
            "high": tds[3].text,
            "low": tds[4].text,
            "open": tds[5].text,
            "qty": tds[6].text,
            "turnover": tds[7].text
        })

    # Store in cache before returning
    result = (gainers_data, losers_data)
    market_cache.set('top_gl', 'top_gainers_losers', result)
    return result


# ============================================
# Top Gainers/Losers Pagination View
# ============================================

class TopGLPagination(discord.ui.View):
    """Pagination view for top gainers and losers"""
    def __init__(self, gainers_data, losers_data, timestamp):
        super().__init__(timeout=300)
        self.gainers_data = gainers_data
        self.losers_data = losers_data
        self.timestamp = timestamp
        self.current_page = 0
        self.max_page = 1  # 0 = Combined view, 1 = Full Gainers, 2 = Full Losers
    
    def create_combined_embed(self):
        """Create combined view showing top 5 gainers and losers"""
        embed = discord.Embed(
            title="🏆 MARKET LEADERS 📊",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.blue()
        )
        
        # Top 5 Gainers
        gainers_text = ""
        for index, stock in enumerate(self.gainers_data[:5]):
            medal = ["🥇", "🥈", "🥉", "  ", "  "][index]
            gainers_text += (
                f"{medal} **#{index+1} {stock['symbol']}** {stock['%chg']}% 📈\n"
                f"   Rs. {stock['ltp']} | Vol: {format_number(stock['qty'])}\n"
                f"   Range: {stock['low']} → {stock['high']}\n\n"
            )
        
        embed.add_field(
            name="📈 TOP 5 GAINERS",
            value=gainers_text or "No data available",
            inline=False
        )
        
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            value="",
            inline=False
        )
        
        # Top 5 Losers
        losers_text = ""
        for index, stock in enumerate(self.losers_data[:5]):
            losers_text += (
                f"  **#{index+1} {stock['symbol']}** {stock['%chg']}% 📉\n"
                f"   Rs. {stock['ltp']} | Vol: {format_number(stock['qty'])}\n"
                f"   Range: {stock['low']} → {stock['high']}\n\n"
            )
        
        embed.add_field(
            name="📉 TOP 5 LOSERS",
            value=losers_text or "No data available",
            inline=False
        )
        
        embed.set_footer(text=f"As of: {self.timestamp} • Page 1/3 - Combined View")
        return embed
    
    def create_full_gainers_embed(self):
        """Create full top 10 gainers view"""
        embed = discord.Embed(
            title="📈 TOP 10 GAINERS",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.green()
        )
        
        for index, stock in enumerate(self.gainers_data[:10]):
            medal = ["🥇", "🥈", "🥉"] + ["  "] * 7
            embed.add_field(
                name=f"{medal[index]} #{index+1} {stock['symbol']}",
                value=(
                    f"**Price:** Rs. {stock['ltp']} | **Change:** {stock['%chg']}% 📈\n"
                    f"**Range:** {stock['low']} → {stock['high']} | **Open:** {stock['open']}\n"
                    f"**Volume:** {format_number(stock['qty'])} | **Turnover:** {format_number(stock['turnover'])}"
                ),
                inline=False
            )
        
        embed.set_footer(text=f"As of: {self.timestamp} • Page 2/3 - Full Gainers List")
        return embed
    
    def create_full_losers_embed(self):
        """Create full top 10 losers view"""
        embed = discord.Embed(
            title="📉 TOP 10 LOSERS",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.red()
        )
        
        for index, stock in enumerate(self.losers_data[:10]):
            embed.add_field(
                name=f"#{index+1} {stock['symbol']}",
                value=(
                    f"**Price:** Rs. {stock['ltp']} | **Change:** {stock['%chg']}% 📉\n"
                    f"**Range:** {stock['low']} → {stock['high']} | **Open:** {stock['open']}\n"
                    f"**Volume:** {format_number(stock['qty'])} | **Turnover:** {format_number(stock['turnover'])}"
                ),
                inline=False
            )
        
        embed.set_footer(text=f"As of: {self.timestamp} • Page 3/3 - Full Losers List")
        return embed
    
    def get_current_embed(self):
        """Get the current page embed"""
        if self.current_page == 0:
            return self.create_combined_embed()
        elif self.current_page == 1:
            return self.create_full_gainers_embed()
        else:
            return self.create_full_losers_embed()
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        self.current_page = (self.current_page - 1) % 3
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="📊 Combined", style=discord.ButtonStyle.primary)
    async def combined_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to combined view"""
        self.current_page = 0
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        self.current_page = (self.current_page + 1) % 3
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.success)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the data"""
        await interaction.response.defer()
        market_cache.clear('top_gainers_losers')
        gainers, losers = scrape_top_gainers_losers()
        self.gainers_data = gainers
        self.losers_data = losers
        self.timestamp = get_latest_time()
        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            embed=self.get_current_embed(),
            view=self
        )


# Command to display top gainers and losers


@client.hybrid_command(name='topgl', description='top 10 gainers and losers')
async def topgl(ctx):
    await ctx.defer()

    gainers_data, losers_data = scrape_top_gainers_losers()
    timestamp = get_latest_time()
    
    # Create pagination view
    view = TopGLPagination(gainers_data, losers_data, timestamp)
    
    # Send the combined view first
    await ctx.reply(embed=view.get_current_embed(), view=view)


@client.hybrid_command(name='cachestats', description='View cache statistics (Admin only)')
async def cachestats(ctx):
    """Display cache statistics"""
    await ctx.defer()
    
    # Check if command is used in a guild (not DM)
    if ctx.guild is None:
        await ctx.reply('❌ This command can only be used in a server, not in DMs.')
        return
    
    # Check if user has admin permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.reply("❌ This command is only available to administrators.")
        return
    
    stats = market_cache.get_stats()
    
    embed = discord.Embed(
        title="📊 Cache Statistics",
        description="Current in-memory cache status",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Total Cached Items", value=stats['total'], inline=False)
    embed.add_field(name="Stock Details", value=stats['stock_details'], inline=True)
    embed.add_field(name="Market Summary", value=stats['market_summary'], inline=True)
    embed.add_field(name="Sub Indices", value=stats['sub_indices'], inline=True)
    embed.add_field(name="Top G/L", value=stats['top_gainers_losers'], inline=True)
    embed.add_field(name="Company Logos", value=stats['company_logo'], inline=True)
    embed.add_field(name="NEPSE Indices", value=stats['nepse_indices'], inline=True)
    
    embed.set_footer(text="Cache TTL: Stock(20s), Summary(60s), Logos(1h)")
    
    await ctx.reply(embed=embed)


@client.hybrid_command(name='clearcache', description='Clear cache (Admin only)')
async def clearcache(ctx, category: str = None):
    """Clear cache for optimization"""
    await ctx.defer()
    
    # Check if command is used in a guild (not DM)
    if ctx.guild is None:
        await ctx.reply('❌ This command can only be used in a server, not in DMs.')
        return
    
    # Check if user has admin permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.reply("❌ This command is only available to administrators.")
        return
    
    market_cache.clear(category)
    
    if category:
        await ctx.reply(f"✅ Cache cleared for category: `{category}`")
    else:
        await ctx.reply("✅ All cache cleared successfully!")


client.run(MY_BOT_TOKEN)
