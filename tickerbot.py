import discord
import regex
from discord.ext import commands
import requests
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()
MY_BOT_TOKEN=str(os.getenv('DISCORD_BOT_TOKEN'))
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix='!', intents=intents)
def extract_stock_name(stock_info):
    return regex.sub(r'\s*\(\s*.*?\s*\)', '', stock_info).strip()

def get_stock_details(stock_name):
    response = requests.get("https://www.sharesansar.com/live-trading")
    response2 = requests.get(f"https://www.sharesansar.com/company/{stock_name}")
    
    soup = BeautifulSoup(response.text, 'lxml')
    soup2=BeautifulSoup(response2.text,'lxml')
    all_rows = soup2.find_all('div',class_='row')
    info_row = all_rows[5]
    second_row = info_row.find_all('div',class_='col-md-12')
    shareinfo = second_row[1]
    heading_list = shareinfo.find_all('h4');
    company_full_form_tag = soup2.find('h1',style="color: #333;font-size: 20px;font-weight: 600;");
    company_fullform=""
    if company_full_form_tag is not None:
        company_fullform = company_full_form_tag.text
    else:
        print("NO details Found")

    company_details = {'sector':heading_list[1].find('span',class_="text-org").text,"share registrar":heading_list[2].find('span',class_="text-org").text,"company fullform":company_fullform}
    stock_rows = soup.find_all('tr') 
    time_stamp = soup.find(id='dDate')
    # print(time_stamp)
    if time_stamp is not None:
        last_updated = time_stamp.text 
    else:
        last_updated = "Date not Found";

    upper_stonk = stock_name.upper()
    
    for row in stock_rows[1:]:
        row_data = row.find_all('td') 

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
                "As of":last_updated,
                "Sector":company_details['sector'],
                "Share Registrar":company_details['share registrar'],
                "Company fullform":company_details['company fullform']
            }
            return stock_details

    return None

@client.event
async def on_ready():
    print("Our Bot is Ready to use")
    print("-----------------------")


@client.command()
async def stonk(ctx,*,stock_name:str):
    stock_details=get_stock_details(stock_name)
    Embedcolor = discord.Color.default()
    ud_emoji=""
    pt_prefix=""
    if stock_details:
        company_name=extract_stock_name(stock_details['Company fullform'])
        if stock_details:
            try:
                last_traded_price = float(stock_details['Last Traded Price'].replace(',', ''))
                prev_closing = float(stock_details['Prev.Closing'].replace(',', ''))


                if last_traded_price > prev_closing:
                    ud_emoji="🔼"
                    pt_prefix="+"
                    Embedcolor = discord.Color.green()
                else:
                    ud_emoji="🔽"
                    Embedcolor = discord.Color.red()
            except (KeyError, ValueError) as e:
                await ctx.send("Error processing stock data. Please ensure the stock name is correct.")
                return
            
        embed = discord.Embed(title=f"Details of {stock_name.upper()}(*Click for more info*)",description=f"**Company**:{company_name}\n**Sector**:{stock_details['Sector']}\n**Share Registrar**:{stock_details['Share Registrar']}\n *[Click here to view technical chart](https://nepsealpha.com/trading/chart?symbol={stock_details['Symbol']})*",color=Embedcolor,url=f"https://merolagani.com/CompanyDetail.aspx?symbol={stock_details['Symbol']}")
        embed.add_field(name= list(stock_details.keys())[0],value=stock_details['Symbol'],inline=True)
        embed.add_field(name= list(stock_details.keys())[1],value=f"{stock_details['Last Traded Price']} {ud_emoji}",inline=True)
        embed.add_field(name= list(stock_details.keys())[2],value=f"{pt_prefix}{stock_details['Pt Change']}",inline=True)
        embed.add_field(name= list(stock_details.keys())[4],value=stock_details['Open'],inline=True)
        embed.add_field(name= list(stock_details.keys())[5],value=stock_details['High'],inline=True)
        embed.add_field(name= list(stock_details.keys())[6],value=stock_details['Low'],inline=True)
        embed.add_field(name= list(stock_details.keys())[3],value=stock_details['% Change'],inline=True)
        embed.add_field(name= list(stock_details.keys())[7],value=stock_details['Volume'],inline=True)
        embed.add_field(name= list(stock_details.keys())[8],value=stock_details['Prev.Closing'],inline=True)
        embed.set_footer(text=f"Last updated:{stock_details['As of']}")
        
    
        await ctx.send(embed=embed)
        

client.run(MY_BOT_TOKEN)

