# NEPSE Ticker Discord Bot

👋 Welcome to the NEPSE Ticker Bot! This bot is designed to provide you with real-time updates from the Nepal Stock Exchange (NEPSE) directly in your Discord server. Whether you're tracking specific stocks or monitoring overall market performance, this bot has you covered with a range of handy commands and **interactive features**.

## ✨ New UI Enhancements

**Latest Update:** The bot now features a completely redesigned user interface with:
- 🎨 **Rich Embeds** - Beautiful, organized information displays
- 🔘 **Interactive Buttons** - View charts, set alerts, and refresh data with one click
- 📊 **Pagination** - Navigate through top gainers/losers with ease
- 📈 **Smart Formatting** - Numbers displayed as 5.23B, 12.45M for better readability
- 🎯 **Progress Indicators** - See how close your alerts are to triggering
- 💎 **Enhanced Visuals** - Color-coded trends, emojis, and better organization

## Features

- Retrieves real-time NEPSE indices data with trend indicators
- Provides detailed information about specific stocks with **interactive action buttons**
- Allows users to check details of various sub-indices
- Offers market summary insights with grouped sections
- Enables users to set alerts for specific stock prices with **modal dialogs**
- Displays all active alerts with **progress tracking**
- Interactive **pagination** for top gainers and losers
- **Smart caching** for improved performance
  
## Commands

### 📊 Market Data Commands
- `/nepse` - Retrieve the latest NEPSE indices data with color-coded trends
- `/stonk <stock_symbol>` - Get detailed info about a specific stock with action buttons
  - 📊 View Chart button
  - 🔔 Set Alert button  
  - 🔄 Refresh button
- `/subidx <subindex_name>` - Get details of a specific sub-index
- `/mktsum` - Provides a market summary of NEPSE's overall performance
- `/topgl` - Shows top 10 gainers/losers with **interactive pagination**
  - Combined view (top 5 each)
  - Full gainers view (top 10)
  - Full losers view (top 10)
  - Navigation and refresh buttons

### 📈 Chart Commands
- `/chart <symbol> [days]` - Generate candlestick charts (1-365 days)
- `/charthelp` - Show detailed help for chart command

### 🔔 Alert Commands
- `/setalert <stock_name> <target_price>` - Set an alert with **rich feedback**
  - Shows current price vs target
  - Calculates distance to target
  - Displays alert counter (X/10)
- `/showalerts` - Displays all active alerts with **progress indicators**
  - Status badges (🟢 Near, 🟡 Close, 🟠 Far)
  - Current price comparison
  - Distance percentage
- `/removealert <stock_name>` - Removes alerts for a specific stock

### ℹ️ Help Commands
- `/helpntb` - Complete command guide
- `/sync` - Sync slash commands (Admin only)
- `/cachestats` - View cache statistics (Admin only)
- `/clearcache` - Clear cache (Admin only)

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
     python main.py
     ```

## Using the Bot

Once the bot is running, you can type commands in your Discord server where the bot is present. Start with `!helpnepse` to see all available commands and begin interacting with the NEPSE Ticker Bot!

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue.
