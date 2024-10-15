# NEPSE Ticker Discord Bot

👋 Welcome to the NEPSE Ticker Bot! This bot is designed to provide you with real-time updates from the Nepal Stock Exchange (NEPSE) directly in your Discord server. Whether you're tracking specific stocks or monitoring overall market performance, this bot has you covered with a range of handy commands.

## Features

- Retrieves real-time NEPSE indices data.
- Provides detailed information about specific stocks.
- Allows users to check details of various sub-indices.
- Offers market summary insights.
- Enables users to set alerts for specific stock prices.
- Displays all active alerts for users.
- Removes alerts as needed.
  
- **Commands:**
  - `/nepse`: Retrieve the latest NEPSE indices data.
  - `/stonk <stock_symbol>`: Get detailed info about a specific stock listed on NEPSE.
  - `/subidx <subindex_name>`: Get details of a specific sub-index.
  - `/mktsum`: Provides a market summary of NEPSE's overall performance.
  - `/setalert <stock_name> <target_price>`: Set an alert for a specific stock when it reaches a target price. The bot will send you a DM after your stock price reaches the target price.
  - `/showalerts`: Displays all active alerts for the user.
  - `/removealert <stock_name>`: Removes an alert for a specific stock.
  - `/topgl`: Shows the top 10 gainers/losers

## Data Source

The data is sourced from [Sharesansar](https://www.sharesansar.com/) and [Mero Lagani](https://www.merolagani.com), two well-regarded platforms that provides real-time stock market information in Nepal. The bot accesses stock prices, indices, and other market information available on their website, making it a valuable resource for anyone interested in the Nepal Stock Exchange.

## Prerequisites

1. **Python 3.8 or higher**
2. **Discord Account**

## Steps to Set Up the Bot

1. **Create a Discord Application**
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications).
   - Click on "New Application" and follow the prompts to create your bot.
   - Once created, navigate to the "Bot" tab and click "Add Bot."
   - Copy the **Bot Token**; you will need it later.

2. **Clone the Repository**
   - Open your terminal and run:
     ```bash
     git clone https://github.com/menaceXnadin/Nepse_Ticker-Discord-Bot.git
     ```

3. **Navigate to the Project Directory**
   - Change to the project directory:
     ```bash
     cd Nepse_Ticker-Discord-Bot
     ```

4. **Install Required Packages**
   - Install the required packages using pip:
     ```bash
     pip install -r requirements.txt
     ```

5. **Create a `.env` File for Bot Token**
   - In your project directory, create a file named `.env` and add the following line:
     ```
     DISCORD_BOT_TOK=your_bot_token_here
     ```
   - Replace `your_bot_token_here` with the token you copied from the Discord Developer Portal.

6. **Invite the Bot to Your Server**
   - Generate an OAuth2 URL in the Discord Developer Portal and use it to invite the bot to your server.

7. **Run the Bot**
   - Start the bot by running:
     ```bash
     python tickerbot.py
     ```

## Using the Bot

Once the bot is running, you can type commands in your Discord server where the bot is present. Start with `!helpnepse` to see all available commands and begin interacting with the NEPSE Ticker Bot!

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue.
