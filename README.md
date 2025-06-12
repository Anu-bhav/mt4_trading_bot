# Python Algorithmic Trading Bot for MetaTrader 4

This project provides a robust, modular framework for developing and running automated trading strategies in Python, connected to the MetaTrader 4 (MT4) terminal. It uses a file-based communication bridge to send commands to and receive data from MT4, allowing for complex strategies to be developed and executed with the power of Python's scientific and data analysis libraries.

The architecture is designed for rapid strategy development, separating core trading logic from the complexities of data management, state handling, and broker communication.

## Key Features

- **Modular Architecture**: Clean separation of concerns between the connection client, trade manager, event handler, and the strategies themselves.
- **Pluggable Strategies**: Strategy logic is self-contained in its own file. To test a new strategy, you only need to change a single line in the main script.
- **Historical Data Preloading**: The bot automatically preloads historical data upon startup, allowing strategies to make decisions from the very first moment without a "warm-up" period.
- **Stateful Logic**: Strategies are designed to be stateful, firing signals only on new crossover or trigger events, preventing signal spamming.
- **Configuration Driven**: All key parameters—from broker connection paths to strategy settings—are managed in a central `config.py` file for easy tuning.
- **Extensible**: Easily integrate powerful libraries like `pandas` and `TA-Lib` for sophisticated indicator calculations within your strategy files.

## Project Structure

```
your_trading_bot/
├── main.py                  # Main entry point: Initializes and runs the bot.
├── config.py                # All your settings, parameters, and credentials.
├── api/
│   └── dwx_client.py        # The client library for MT4 communication.
├── event_handler.py         # Routes events from the client to the TradeManager.
├── trade_manager.py         # The engine: Manages data, state, and executes trades.
└── strategies/
    ├── __init__.py
    ├── base_strategy.py     # Defines the interface that all strategies must follow.
    └── sma_crossover.py     # An example self-contained strategy file.
```

## Prerequisites

1.  **MetaTrader 4 Terminal**: You must have an MT4 terminal installed.
2.  **Python**: Python 3.8 or newer.
3.  **Required MQL4 Expert Advisor**: The `DWX_server_MT4.mq4` Expert Advisor must be placed in your MT4 terminal's `MQL4/Experts` directory. This EA acts as the server that communicates with the Python client.
4.  **Python Libraries**:
    ```bash
    pip install pandas
    ```

## Setup and Configuration

### Step 1: Configure MetaTrader 4

1.  **Install the Expert Advisor**:

    - Open your MT4 terminal.
    - Go to `File` -> `Open Data Folder`.
    - Navigate to the `MQL4/Experts` folder.
    - Copy the `DWX_server_MT4.mq4` file into this directory.
    - Return to your MT4 terminal, open the "Navigator" window, right-click on "Expert Advisors" and select "Refresh". You should now see `DWX_server_MT4`.

2.  **Enable AutoTrading**:

    - In the MT4 toolbar, click the **"AutoTrading"** button so it turns green.
    - Go to `Tools` -> `Options` -> `Expert Advisors` tab.
    - Check the box for **"Allow automated trading"**.
    - Check the box for **"Allow DLL imports"**. This is required by the server EA.

3.  **Attach the EA to a Chart**:
    - Open a chart for any symbol (e.g., EURUSD). The timeframe does not matter for the server itself.
    - Drag the `DWX_server_MT4` EA from the Navigator onto the chart.
    - In the "Common" tab of the EA's properties, ensure **"Allow live trading"** is checked.
    - You should see a smiley face in the top-right corner of the chart, indicating the EA is running.

### Step 2: Configure the Python Project

1.  **Clone the Repository**:

    ```bash
    git clone https://github.com/Anu-bhav/mt4_trading_bot
    cd mt4_trading_bot
    ```

2.  **Edit `config.py`**:
    - Open the `config.py` file.
    - **`METATRADER_DIR_PATH`**: This is the most critical setting. Set it to the **full path of your MT4 Data Folder** (the same one you opened in Step 1.1).
    - **Strategy Settings**: Adjust `STRATEGY_SYMBOL`, `STRATEGY_TIMEFRAME`, and any parameters inside `STRATEGY_PARAMS` to tune your strategy.
    - **Risk Settings**: Configure `LOT_SIZE` and `MAGIC_NUMBER`. The magic number must be unique to this strategy to avoid interfering with other EAs or manual trades.

## How to Run the Bot

Once both MT4 and the Python project are configured, simply run the main script from your terminal:

```bash
python main.py
```

The console will display logs showing the bot's status, including data preloading, indicator calculations, and trade execution decisions.

## How to Create a New Strategy

The framework is designed to make adding new strategies simple:

1.  **Define Parameters in `config.py`**: Add a new dictionary of parameters for your strategy inside the `STRATEGY_PARAMS` variable.

    ```python
    STRATEGY_PARAMS = {
        # ... existing strategies
        'my_new_strategy': {
            'param1': 'value1',
            'param2': 123
        }
    }
    ```

2.  **Create the Strategy File**:

    - In the `strategies/` folder, create a new file (e.g., `my_new_strategy.py`).
    - Inside this file, create a class that inherits from `BaseStrategy`.
    - Implement the `__init__` method to accept your parameters and the `get_signal` method to contain your trading logic. The `get_signal` method must accept a pandas DataFrame and return a string signal (`'BUY'`, `'SELL'`, or `'HOLD'`).

3.  **Activate the Strategy in `main.py`**:

    - Change the import statement to bring in your new strategy class.
    - Change the line where the strategy is instantiated to use your new class and its corresponding parameters from the config.

    ```python
    # In main.py
    from strategies.my_new_strategy import MyNewStrategy

    # ...

    strategy_params = cfg.STRATEGY_PARAMS['my_new_strategy']
    my_strategy_logic = MyNewStrategy(**strategy_params)
    ```

4.  **Run the bot!** Your new strategy is now live.

## Acknowledgements

This project's core communication layer is built upon the foundational work of the **Darwinex Labs** team and their open-source **`dwxconnect`** project.

- The **`DWX_server_MT4.mq4`** Expert Advisor, which acts as the server-side bridge in MetaTrader 4, is used directly from this library.
- The Python client (`api/dwx_client.py`) is based on their original client, with modifications made to enhance graceful shutdowns. Notably, a `stop()` method was added to allow for better encapsulation and reliable termination of the background threads.

We are immensely grateful for their decision to open-source these essential tools, which provide a vital link between the Python ecosystem and the MetaTrader platform.

The original repository can be found at:
**[darwinex/dwxconnect on GitHub](https://github.com/darwinex/dwxconnect)**
