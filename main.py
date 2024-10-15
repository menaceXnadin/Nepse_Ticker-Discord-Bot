import discord
import regex
from discord.ext import commands,tasks
import requests
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
MY_BOT_TOKEN = str(os.getenv("DISCORD_BOT_TOK"))
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

user_alerts = {}  # dict style: user_alerts = {'user_id': {'stock_name': [target_price1, target_price2]}}

def get_latest_time():
    response = requests.get("https://www.sharesansar.com/live-trading")
    soup = BeautifulSoup(response.text, "lxml")
    stock_rows = soup.find_all("tr")
    time_stamp = soup.find(id="dDate")
    if time_stamp is not None:
        last_updated = time_stamp.text
    else:
        last_updated = "Date not Found" 
    return last_updated





def extract_stock_name(stock_info):
    return regex.sub(r"\s*\(\s*.*?\s*\)", "", stock_info).strip()


@client.command()
async def nepse(ctx):
    # Fetch the webpage content
    url = "https://www.sharesansar.com/market"  # URL to scrape
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "lxml")

    # Find the table that contains the indices data
    all_tables = soup.find_all(
        "table", class_="table table-bordered table-striped table-hover"
    )
    main_indices = all_tables[0]  # Assuming the first table is the main indices

    # Extract all the rows (skipping the header)
    main_indices_rows = main_indices.find_all("tr")[1:]

    # Create an embed object
    embed = discord.Embed(title="NEPSE Index Data", color=discord.Color.yellow())
    embed.set_footer(text=f"As of:{get_latest_time()}")

    # Iterate through each row and extract the data
    for tr in main_indices_rows:
        tds = tr.find_all("td")
        index_details = {
            "Index Name": tds[0].text.strip(),
            "Open": tds[1].text.strip(),
            "High": tds[2].text.strip(),
            "Low": tds[3].text.strip(),
            "Close": tds[4].text.strip(),
            "Point Change": tds[5].text.strip(),
            "% Change": tds[6].text.strip(),
            "Turnover": tds[7].text.strip(),
        }

        # Add each index's data as a field in the embed
        embed.add_field(
            name=index_details["Index Name"],
            value=(
                f"**Open**: {index_details['Open']}\n"
                f"**High**: {index_details['High']}\n"
                f"**Low**: {index_details['Low']}\n"
                f"**Close**: {index_details['Close']}\n"
                f"**Point Change**: {index_details['Point Change']}\n"
                f"**% Change**: {index_details['% Change']}\n"
                f"**Turnover**: {index_details['Turnover']}"
            ),
            inline=True,  # False to display the fields vertically
        )

    # Send the embed to the channel
    await ctx.reply(embed=embed)


def get_sub_index_details(subindex_name):
    subindex_name = subindex_name.upper()
    response4 = requests.get("https://www.sharesansar.com/market")
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
            "HOTEL": "Hotels And Tourism",
            "HYDRO": "HydroPower Index",
            "INVESTMENT": "Investment",
            "LIFE": "Life Insurance",
            "MANU": "Manufacturing And Processing",
            "MICRO": "Microfinance Index",
            "MF": "Mutual Fund",
            "NONLIFE": "Non Life Insurance",
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
            return sub_index_details
    return None
    


@client.command()
async def subidx(ctx, *, subindex_name: str):
    sub_index_details = get_sub_index_details(subindex_name)
    if sub_index_details is None:
        await ctx.reply(f"The particular subindex : `{subindex_name}` doesn't exist or there might be a typo.🤔\nPlease use `!helpntb` to see the correct format! 📜")
        return
    o = round(float(sub_index_details["Open"].replace(",", "")),2)
    h = round(float(sub_index_details["High"].replace(",", "")),2)
    c = round(float(sub_index_details["close"].replace(",", "")),2)
    if o > c or o > h or o > c:
        embedcolor = discord.Color.red()
    else:
        embedcolor = discord.Color.green()
    embed = discord.Embed(
        title=f"Data for {sub_index_details['Sub Index']}", color=embedcolor
    )
    embed.add_field(
        name=list(sub_index_details.keys())[1],
        value=sub_index_details["Open"],
        inline=True,
    )
    embed.add_field(
        name=list(sub_index_details.keys())[2],
        value=sub_index_details["High"],
        inline=True,
    )
    embed.add_field(
        name=list(sub_index_details.keys())[3],
        value=sub_index_details["Low"],
        inline=True,
    )
    embed.add_field(
        name=list(sub_index_details.keys())[4],
        value=sub_index_details["close"],
        inline=True,
    )
    embed.add_field(
        name=list(sub_index_details.keys())[5],
        value=sub_index_details["Pt.Change"],
        inline=True,
    )
    embed.add_field(
        name=list(sub_index_details.keys())[6],
        value=sub_index_details["% change"],
        inline=True,
    )
    embed.add_field(
        name=list(sub_index_details.keys())[7],
        value=sub_index_details["Turnover"],
        inline=True,
    )
    embed.set_footer(text=f"As of: {get_latest_time()}")
    await ctx.reply(embed=embed)

def get_stock_details(stock_name):
    # if stock_name.upper()=="NEPSE":
    #     return None
    response = requests.get("https://www.sharesansar.com/live-trading")
    response2 = requests.get(f"https://www.sharesansar.com/company/{stock_name}")

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
            return stock_details

    return None  # Return None if the stock was not found



@client.event
async def on_ready():
    check_stock_alerts.start()  # Start the background task
    print(f"Logged in as {client.user}")
    print("Our Bot is Ready to use")
    print("-----------------------")


def get_market_summary():
    response3 = requests.get("https://www.sharesansar.com/market-summary")
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
    return market_summary


@client.command()
async def mktsum(ctx):
    market_summary = get_market_summary()

    # Create an embed message for market summary
    embed = discord.Embed(title="Market Summary Of NEPSE", color=discord.Color.blue())

    if market_summary:
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
        embed.set_footer(text=f"As of:{market_summary['As of']}")
    else:
        embed.description = "No market summary data found."

    await ctx.reply(embed=embed)


@client.command()
async def stonk(ctx, *, stock_name: str):
    if stock_name.upper() == "NEPSE":
        await ctx.reply("📊 For details on NEPSE, use `!nepse` or use `!mktsum` to get the market summary. 📈")
        return
    stock_details = get_stock_details(stock_name)
    Embedcolor = discord.Color.default()
    ud_emoji = ""
    pt_prefix = ""

    # Check if stock details were found
    if stock_details is None:
        await ctx.reply(f"⚠️ Stock '{stock_name.upper()}' not found. Please ensure the stock name is correct.")
        return

    company_name = extract_stock_name(stock_details["Company fullform"])
    try:
        last_traded_price = round(float(stock_details["Last Traded Price"].replace(",", "")),2)
        prev_closing = round(float(stock_details["Prev.Closing"].replace(",", "")),2)

        if last_traded_price > prev_closing:
            ud_emoji = "🔼"
            pt_prefix = "+"
            Embedcolor = discord.Color.green()
        else:
            ud_emoji = "🔽"
            Embedcolor = discord.Color.red()
    except (KeyError, ValueError) as e:
        await ctx.reply("Error processing stock data. Please ensure the stock name is correct.")
        return

    embed = discord.Embed(
        title=f"Details of {stock_name.upper()}(*Click for more info*)",
        description=f"**Company**:{company_name}\n**Sector**:{stock_details['Sector']}\n**Share Registrar**:{stock_details['Share Registrar']}\n *[Click here to view technical chart](https://nepsealpha.com/trading/chart?symbol={stock_details['Symbol']})*",
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
        name=list(stock_details.keys())[4], value=stock_details["Open"], inline=True
    )
    embed.add_field(
        name=list(stock_details.keys())[5], value=stock_details["High"], inline=True
    )
    embed.add_field(
        name=list(stock_details.keys())[6], value=stock_details["Low"], inline=True
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
    embed.set_footer(text=f"Last updated:{stock_details['As of']}")

    await ctx.reply(embed=embed)



@client.command()
async def helpntb(ctx):
    embed = discord.Embed(title="NEPSE Command Help", color=discord.Color(0x00FFFF))

    # !nepse command
    embed.add_field(
        name="1. !nepse",
        value=(        
            "**Description:** Retrieves the latest NEPSE indices data.\n"
            "**Data Provided:** NEPSE Index, Sensitive Index, Float Index, Sensitive Float Index.\n"
            "**Usage:** Type `!nepse`."
        ),
        inline=False
    )

    # !stonk command
    embed.add_field(
        name="2. !stonk <stock_symbol>",
        value=( 
            "**Description:** Provides detailed info about a specific stock listed on NEPSE.\n"
            "**Usage:** Type `!stonk <stock_symbol>` (e.g., `!stonk UNL`).\n"
            "**Note:** stock_symbols are case-insensitive."
        ),
        inline=False
    )

    # !subidx command
    embed.add_field(
        name="3. !subidx <subindex_name>",
        value=( 
            "**Description:** Get details of a specific sub-index.\n"
            "**Usage:** Type `!subidx <subindex_name>` (e.g., `!subidx BANKING`).\n"
            "**Note:** Use the abbreviations listed below (case insensitive):\n"
            " - **BANKING**: Banking SubIndex\n"
            " - **DEVBANK**: Development Bank Index\n"
            " - **FINANCE**: Finance Index\n"
            " - **HOTEL**: Hotels And Tourism\n"
            " - **HYDRO**: HydroPower Index\n"
            " - **INVESTMENT**: Investment\n"
            " - **LIFE**: Life Insurance\n"
            " - **MANU**: Manufacturing And Processing\n"
            " - **MICRO**: Microfinance Index\n"
            " - **MF**: Mutual Fund\n"
            " - **NONLIFE**: Non Life Insurance\n"
            " - **OTHERS**: Others Index\n"
            " - **TRADING**: Trading Index"
        ),
        inline=False
    )

    # !mktsum command
    embed.add_field(
        name="4. !mktsum",
        value=( 
            "**Description:** Provides a Market summary of NEPSE's overall performance.\n"
            "**Data Provided:** Total Turnovers, Total Traded Shares, Total Transactions, Total Scrips Traded, Total Market Cap, and Floated Market Cap.\n"
            "**Usage:** Type `!mktsum`."
        ),
        inline=False
    )

    # !setalert command
    embed.add_field(
        name="5. !setalert <stock_name> <target_price>",
        value=( 
            "**Description:** Sets an alert for a specific stock when it reaches a target price.\n"
            "`*The bot will send you a DM after your stock price reaches the target price.*`\n"
            "**Usage:** Type `!setalert <stock_name> <target_price>` (e.g., `!setalert NFS 5000`)."
        ),
        inline=False
    )

    # !showalerts command
    embed.add_field(
        name="6. !showalerts",
        value=( 
            "**Description:** Displays all active alerts for the user.\n"
            "**Usage:** Type `!showalerts`."
        ),
        inline=False
    )

    # !removealert command
    embed.add_field(
        name="7. !removealert <stock_name>",
        value=( 
            "**Description:** Removes an alert for a specific stock.\n"
            "**Usage:** Type `!removealert <stock_name>` \n(e.g., `!removealert UNL`)."
        ),
        inline=False
    )

    # !topgl command
    embed.add_field(
        name="8. !topgl",
        value=( 
            "**Description:** Displays the top 10 gainers and top 10 losers in the market.\n"
            "**Usage:** Type `!topgl`."
        ),
        inline=False
    )

    await ctx.reply(embed=embed)


def get_stock_price(stock_name):
    response = requests.get(f"https://www.sharesansar.com/live-trading")
    soup = BeautifulSoup(response.text, 'lxml')
    df = soup.find('tbody')
    stock_rows = df.find_all('tr')
    for row in stock_rows:
        row_data = row.find_all('td')  # All <td> in the current row
        if row_data[1].text.strip().upper() == stock_name.upper():  # Use upper to match stock names
            return round(float(row_data[2].text.strip().replace(',', '')),2)
    return None

@tasks.loop(seconds=30)
async def check_stock_alerts():
    for user_id, alerts in user_alerts.items():
        # Collect stocks to remove after checking prices
        stocks_to_remove = []
        for stock_name, target_prices in alerts.items():
            current_price = get_stock_price(stock_name)
            if current_price is not None:
                for target_price in target_prices[:]:  # Iterate over a copy of target_prices
                    if current_price == target_price:  # Check for exact price match
                        user = await client.fetch_user(user_id)
                        await user.send(f"🔔 **ALERT!** {stock_name} has reached your target price of Rs. {target_price}. Current price: Rs. {current_price}.")
                        target_prices.remove(target_price)  # Remove the alerted price

                # Check if no target prices are left for this stock
                if not target_prices:
                    stocks_to_remove.append(stock_name)

        # Remove stocks after the iteration is done
        for stock_name in stocks_to_remove:
            del alerts[stock_name]
def check_stock_exists(stock_name):
    response = requests.get(f"https://www.sharesansar.com/live-trading")
    soup = BeautifulSoup(response.text, 'lxml')    
    df = soup.find('tbody')
    stock_rows = df.find_all('tr')  # List of all stock rows
    for row in stock_rows:
        row_data = row.find_all('td')  # All <td> in the current row
        for td in row_data:
            if td.text.strip() == stock_name.upper():
                return True
    return None
@client.command()
async def setalert(ctx, stock_name: str, target_price: float):
    user_id = ctx.author.id
    stock_name = stock_name.upper()
    if check_stock_exists(stock_name) is None:
        await ctx.reply(f"😵‍💫Stock : {stock_name} doesn't exist or there may be a **Typo**")
        return 
    if user_id not in user_alerts:
        user_alerts[user_id] = {}
    if stock_name not in user_alerts[user_id]:
        user_alerts[user_id][stock_name] = []
    user_alerts[user_id][stock_name].append(target_price)  # Append to the list of target prices
    await ctx.reply(f"✅ Alert set for {stock_name} at Rs.{target_price}.")

@client.command()
async def showalerts(ctx):
    user_id = ctx.author.id
    if user_id in user_alerts and user_alerts[user_id]:
        alert_list = "\n".join([f"{stock}: Rs. {', Rs. '.join(map(str, prices))}" for stock, prices in user_alerts[user_id].items()])
        await ctx.reply(f"Your alerts:\n{alert_list}")
    else:
        await ctx.reply("You have no active alerts.")

@client.command()
async def removealert(ctx, stock_name: str):
    user_id = ctx.author.id
    stock_name = stock_name.upper()
    if user_id in user_alerts and stock_name in user_alerts[user_id]:
        del user_alerts[user_id][stock_name]
        await ctx.reply(f"❌ Alert removed for {stock_name}.")
    else:
        await ctx.reply(f"No active alert found for {stock_name}.")
        
def scrape_top_gainers_losers():
    response5 = requests.get("https://merolagani.com/LatestMarket.aspx")
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
    
    return gainers_data, losers_data

# Command to display top gainers and losers
@client.command()
async def topgl(ctx):
    gainers_data, losers_data = scrape_top_gainers_losers()
    
    # Create the embed for top gainers
    embed_gainers = discord.Embed(title="Top 10 Gainers", color=discord.Color.green())
    for index,stock in enumerate(gainers_data[:10]):
        embed_gainers.add_field(
            name=f"{index+1}.{stock['symbol']}",
            value=(
                f"**LTP**: {stock['ltp']}   **%Change**: {stock['%chg']}%\n"
                f"**Open**: {stock['open']}  **High**: {stock['high']}  **Low**: {stock['low']}\n"
                f"**Qty**: {stock['qty']}  **Turnover**: {stock['turnover']}\n"
            ),
            inline=False  # Set this to True if you want to display fields in the same row.
        )
    embed_gainers.set_footer(text=f"As of: {get_latest_time()}")
    # Create the embed for top losers
    embed_losers = discord.Embed(title="Top 10 Losers", color=discord.Color.red())
    for index,stock in enumerate(losers_data[:10]):
        embed_losers.add_field(
            name=f"{index+1}.{stock['symbol']}",
            value=(
                f"**LTP**: {stock['ltp']}   **%Change**: {stock['%chg']}%\n"
                f"**Open**: {stock['open']}  **High**: {stock['high']}  **Low**: {stock['low']}\n"
                f"**Qty**: {stock['qty']}  **Turnover**: {stock['turnover']}\n"
            ),
            inline=False  # Set to True if you want to place fields in a row.
        )
    embed_losers.set_footer(text=f"As of: {get_latest_time()}")
    
    # Send both embeds separately
    await ctx.reply(embed=embed_gainers)
    await ctx.reply(embed=embed_losers)
client.run(MY_BOT_TOKEN)
