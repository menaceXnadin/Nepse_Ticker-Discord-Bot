import discord
import regex
from discord.ext import commands
import requests
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
MY_BOT_TOKEN = str(os.getenv("DISCORD_BOT_TOK"))
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

response3 = requests.get("https://www.sharesansar.com/market-summary")
soup3 = BeautifulSoup(response3.text, "lxml")
summary_cont = soup3.find("div", id="market_symmary_data")
last_mktsum = ""
if summary_cont is not None:
    msdate = summary_cont.find("h5").find("span")
    if msdate is not None:
        last_mktsum = msdate.text
data_sum = soup3.find_all("td")


def extract_stock_name(stock_info):
    return regex.sub(r"\s*\(\s*.*?\s*\)", "", stock_info).strip()


@client.command()
async def index(ctx):
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
    embed.set_footer(text=f"As of:{last_mktsum}")

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


@client.command()
async def subidx(ctx, *, subindex_name: str):
    sub_index_details = get_sub_index_details(subindex_name)
    o = float(sub_index_details["Open"].replace(",", ""))
    h = float(sub_index_details["High"].replace(",", ""))
    c = float(sub_index_details["close"].replace(",", ""))
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
    embed.set_footer(text=f"As of: {last_mktsum}")
    await ctx.reply(embed=embed)


def get_stock_details(stock_name):
    response = requests.get("https://www.sharesansar.com/live-trading")
    response2 = requests.get(f"https://www.sharesansar.com/company/{stock_name}")

    soup = BeautifulSoup(response.text, "lxml")
    soup2 = BeautifulSoup(response2.text, "lxml")
    all_rows = soup2.find_all("div", class_="row")
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

    return None


@client.event
async def on_ready():
    print("Our Bot is Ready to use")
    print("-----------------------")


def get_market_summary():
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
    stock_details = get_stock_details(stock_name)
    Embedcolor = discord.Color.default()
    ud_emoji = ""
    pt_prefix = ""
    if stock_details:
        company_name = extract_stock_name(stock_details["Company fullform"])
        if stock_details:
            try:
                last_traded_price = float(
                    stock_details["Last Traded Price"].replace(",", "")
                )
                prev_closing = float(stock_details["Prev.Closing"].replace(",", ""))

                if last_traded_price > prev_closing:
                    ud_emoji = "🔼"
                    pt_prefix = "+"
                    Embedcolor = discord.Color.green()
                else:
                    ud_emoji = "🔽"
                    Embedcolor = discord.Color.red()
            except (KeyError, ValueError) as e:
                await ctx.reply(
                    "Error processing stock data. Please ensure the stock name is correct."
                )
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
async def helpnepse(ctx):
    embed = discord.Embed(title="NEPSE Command Help", color=discord.Color(0x00FFFF))

    # !index command
    embed.add_field(
        name="1. !index",
        value=(
            "**Description:** Retrieves the latest NEPSE indices data.\n"
            "**Data Provided:** NEPSE Index, Sensitive Index, Float Index, Sensitive Float Index.\n"
            "**Usage:** Type `!index`."
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
        inline=True
    )

    await ctx.reply(embed=embed)

client.run(MY_BOT_TOKEN)
