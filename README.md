# Python Algorithmic Trading Bot for MetaTrader 4

This project provides a robust, modular, and production-ready framework for developing and running automated trading strategies in Python, connected to the MetaTrader 4 (MT4) terminal. It uses a file-based communication bridge to send commands to and receive data from MT4, allowing for complex strategies to be developed and executed with the power of Python's scientific and data analysis libraries.

The architecture is designed for rapid strategy development and safe, unattended operation, separating core trading logic from the complexities of data management, risk control, and broker communication.

## Key Features

- **Modular Architecture**: Clean separation of concerns between the connection client, trade manager, event handler, and the strategies themselves.
- **Dynamic "Plug-and-Play" Strategies**: A strategy factory allows you to activate any strategy just by changing its name in `main.py`. No more `if/elif` blocks or manual imports.
- **Advanced Risk Management**: A centralized `TradeManager` that handles sophisticated, percentage-based risk rules:
  - Dynamic position sizing based on account risk percentage.
  - Percentage-based Stop Loss and Take Profit.
  - Percentage-based Trailing Stop Loss.
  - Configurable multi-stage Partial Take Profits.
- **Broker-Aware Execution**: The bot dynamically queries the broker for instrument-specific rules (`stoplevel`, `lot_step`, `min/max_lot`) to ensure all trades are compliant and prevent rejections.
- **State Persistence**: The bot saves its trade management state (e.g., which partial profits have been taken) to a file, ensuring it can be stopped and restarted without making duplicate decisions.
- **Production-Ready Reliability**:
  - **Persistent Logging**: All actions and decisions are logged to a rotating file for easy debugging and auditing.
  - **Two-Way Heartbeat**: A mechanism that allows the MT4 Expert Advisor and the Python script to monitor each other. If the Python script crashes, the EA can safely close all open trades.
  - **Data Integrity Checks**: The system automatically detects and handles corrupted data (bad candles) and warns about potential gaps in the data stream.
- **Configuration Driven**: All key parameters—from broker paths to strategy settings and risk rules—are managed in a central `config.py` file for easy tuning.

## Project Structure

```
your_trading_bot/
├── main.py                  # Main entry point: Initializes and runs the bot.
├── config.py                # All settings, parameters, and credentials.
├── logger_setup.py          # Configures persistent file and console logging.
├── api/
│   └── dwx_client.py        # The client library for MT4 communication.
├── event_handler.py         # Routes events from the client to the TradeManager.
├── trade_manager.py         # The engine: Manages data, state, risk, and execution.
├── utils/
│   └── risk_manager.py      # Contains pure risk calculation functions.
└── strategies/
    ├── __init__.py
    ├── base_strategy.py     # Defines the interface that all strategies must follow.
    └── sma_crossover.py     # An example self-contained strategy file.
```

## Prerequisites

1.  **MetaTrader 4 Terminal**: You must have an MT4 terminal installed.
2.  **Python**: Python 3.8 or newer.
3.  **Required MQL4 Expert Advisor**: The enhanced `DWX_server_MT4.mq4` Expert Advisor from this repository must be placed in your MT4 terminal's `MQL4/Experts` directory.
4.  **Python Libraries**:
    ```bash
    pip install pandas
    ```

## Setup and Configuration

### Step 1: Configure MetaTrader 4

1.  **Install the Expert Advisor**:

    - Open your MT4 terminal, go to `File` -> `Open Data Folder`.
    - Navigate to the `MQL4/Experts` folder and copy the `DWX_server_MT4.mq4` file into it.
    - In MT4, right-click "Expert Advisors" in the Navigator and select "Refresh".

2.  **Enable AutoTrading & DLLs**:

    - In the MT4 toolbar, click the **"AutoTrading"** button so it turns green.
    - Go to `Tools` -> `Options` -> `Expert Advisors` tab.
    - Check **"Allow automated trading"**.
    - Check **"Allow DLL imports"**.

3.  **Attach and Configure the EA**:
    - Open a chart for the symbol and timeframe you wish to trade (e.g., `EURUSD, M15`).
    - Drag the `DWX_server_MT4` EA from the Navigator onto the chart.
    - In the `Inputs` tab of the EA's properties, **it is critical to update the default settings**:
      - `MaximumLotSize`: Set to a high value like `100.0` to give control to Python.
      - `MaximumOrders`: Set to a high value like `20`.
      - `SlippagePoints`: Increase to `30` or `50` for volatile instruments.
      - `MILLISECOND_TIMER`: Increase to `500` to reduce CPU load.
    - Ensure "Allow live trading" is checked in the `Common` tab. You should see a smiley face on the chart.

### Step 2: Configure the Python Project

1.  **Clone the Repository**:

    ```bash
    git clone https://github.com/Anu-bhav/mt4_trading_bot
    cd mt4_trading_bot
    ```

2.  **Edit `config.py`**:
    - **`METATRADER_DIR_PATH`**: Set this to the **full path of your MT4 Data Folder**.
    - **Strategy Settings**: Adjust `STRATEGY_SYMBOL`, `STRATEGY_TIMEFRAME`, and parameters in `STRATEGY_PARAMS`.
    - **Risk Settings**: Configure your desired rules in the `RISK_CONFIG` dictionary.

## How to Run the Bot

Once both MT4 and Python are configured, simply run the main script from your terminal:

```bash
python main.py
```

All output will be printed to the console and simultaneously saved to `trading_bot.log` for a permanent record.

## How to Create a New Strategy

Thanks to the dynamic strategy factory, adding new strategies is incredibly simple:

1.  **Define Parameters in `config.py`**: Add a new key and dictionary for your strategy inside `STRATEGY_PARAMS`.

    ```python
    'my_new_strategy': { 'lookback': 50, 'threshold': 3.14 }
    ```

2.  **Create the Strategy File**:

    - In the `strategies/` folder, create a file named `my_new_strategy.py`.
    - Inside, create a class named `MyNewStrategy` that inherits from `BaseStrategy`.
    - Implement your `__init__`, `get_signal`, and `reset` methods.

3.  **Activate the Strategy in `main.py`**:
    - Change **one single line** in `main.py`:
    ```python
    strategy_name_to_run = "my_new_strategy"
    ```

That's it! The factory handles the rest.

## Acknowledgements

This project's core communication layer is built upon the foundational work of the **Darwinex Labs** team and their open-source **`dwxconnect`** project.

- The **`DWX_server_MT4.mq4`** Expert Advisor and Python client (`api/dwx_client.py`) are based on their original library. We have extended them to include richer data, graceful shutdowns (via a `stop()` method), and a two-way heartbeat mechanism for enhanced reliability.

We are immensely grateful for their decision to open-source these essential tools.

The original repository can be found at:
**[darwinex/dwxconnect on GitHub](https://github.com/darwinex/dwxconnect)**
