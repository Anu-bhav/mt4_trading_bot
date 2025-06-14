# api/dwx_client.py
import json
import logging  # <-- FIX 1: Import the logging library
import os
import time
from datetime import datetime, timedelta, timezone
from os.path import exists, join
from threading import Lock, Thread
from time import sleep
from traceback import print_exc


class dwx_client:
    def __init__(
        self,
        event_handler=None,
        metatrader_dir_path="",
        sleep_delay=0.005,
        max_retry_command_seconds=10,
        load_orders_from_file=True,
        verbose=True,
    ):
        self.event_handler = event_handler
        self.sleep_delay = sleep_delay
        self.max_retry_command_seconds = max_retry_command_seconds
        self.load_orders_from_file = load_orders_from_file
        self.verbose = verbose
        self.command_id = 0

        if not exists(metatrader_dir_path):
            logging.error(f"ERROR: metatrader_dir_path does not exist! Path: {metatrader_dir_path}")
            exit()

        self.path_orders = join(metatrader_dir_path, "DWX", "DWX_Orders.txt")
        self.path_messages = join(metatrader_dir_path, "DWX", "DWX_Messages.txt")
        self.path_market_data = join(metatrader_dir_path, "DWX", "DWX_Market_Data.txt")
        self.path_bar_data = join(metatrader_dir_path, "DWX", "DWX_Bar_Data.txt")
        self.path_historic_data = join(metatrader_dir_path, "DWX", "DWX_Historic_Data.txt")
        self.path_historic_trades = join(metatrader_dir_path, "DWX", "DWX_Historic_Trades.txt")
        self.path_orders_stored = join(metatrader_dir_path, "DWX", "DWX_Orders_Stored.txt")
        self.path_messages_stored = join(metatrader_dir_path, "DWX", "DWX_Messages_Stored.txt")
        self.path_execution_receipts = join(metatrader_dir_path, "DWX", "DWX_Execution_Receipts.txt")
        self.path_python_heartbeat = join(metatrader_dir_path, "DWX", "DWX_Python_Heartbeat.txt")
        self.path_commands_prefix = join(metatrader_dir_path, "DWX", "DWX_Commands_")

        self.num_command_files = 50
        self._last_messages_millis = 0
        self._last_open_orders_str = ""
        self._last_messages_str = ""
        self._last_market_data_str = ""
        self._last_bar_data_str = ""
        self._last_historic_data_str = ""
        self._last_historic_trades_str = ""

        self.open_orders = {}
        self.account_info = {}
        self.market_data = {}
        self.bar_data = {}
        self.historic_data = {}
        self.historic_trades = {}
        self._last_bar_data = {}
        self._last_market_data = {}

        self.ACTIVE: bool = True
        self.START: bool = False
        self.lock = Lock()
        self.load_messages()
        if self.load_orders_from_file:
            self.load_orders()

        # Start all background threads
        self.messages_thread = Thread(target=self.check_messages, args=())
        self.messages_thread.daemon = True
        self.messages_thread.start()
        self.market_data_thread = Thread(target=self.check_market_data, args=())
        self.market_data_thread.daemon = True
        self.market_data_thread.start()
        self.bar_data_thread = Thread(target=self.check_bar_data, args=())
        self.bar_data_thread.daemon = True
        self.bar_data_thread.start()
        self.open_orders_thread = Thread(target=self.check_open_orders, args=())
        self.open_orders_thread.daemon = True
        self.open_orders_thread.start()
        self.historic_data_thread = Thread(target=self.check_historic_data, args=())
        self.historic_data_thread.daemon = True
        self.historic_data_thread.start()

        self.reset_command_ids()
        if self.event_handler is None:
            self.start()

    def start(self):
        self.START = True

    def stop(self):
        logging.info("DWX Client stop() method called. Shutting down threads.")
        self.ACTIVE = False

    def try_read_file(self, file_path):
        try:
            if exists(file_path):
                with open(file_path, "r") as f:
                    return f.read()
        except (IOError, PermissionError):
            pass
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
        return ""

    def try_remove_file(self, file_path):
        try:
            if exists(file_path):
                os.remove(file_path)
        except (IOError, PermissionError):
            pass
        except Exception as e:
            logging.error(f"Error removing file {file_path}: {e}")

    # --- ALL 'check' METHODS ARE NOW WRAPPED IN ROBUST TRY/EXCEPT BLOCKS ---
    def check_open_orders(self):
        while self.ACTIVE:
            sleep(self.sleep_delay)
            if not self.START:
                continue
            text = self.try_read_file(self.path_orders)
            if not text or text == self._last_open_orders_str:
                continue

            try:
                data = json.loads(text)
                self._last_open_orders_str = text
                new_event = False
                # Use .get() for safe access
                current_orders = data.get("orders", {})
                if list(self.open_orders.keys()) != list(current_orders.keys()):
                    new_event = True

                self.account_info = data.get("account_info", {})
                self.open_orders = current_orders

                if self.load_orders_from_file:
                    with open(self.path_orders_stored, "w") as f:
                        f.write(json.dumps(data))
                if self.event_handler and new_event:
                    self.event_handler.on_order_event()
            except json.JSONDecodeError:
                logging.warning(f"Corrupted JSON in {self.path_orders}, content: '{text[:200]}'")
            except Exception as e:
                logging.error(f"Error in check_open_orders: {e}")

    def check_messages(self):
        while self.ACTIVE:
            sleep(self.sleep_delay)
            if not self.START:
                continue
            text = self.try_read_file(self.path_messages)
            if not text or text == self._last_messages_str:
                continue

            try:
                data = json.loads(text)
                self._last_messages_str = text
                for millis, message in sorted(data.items()):
                    if int(millis) > self._last_messages_millis:
                        self._last_messages_millis = int(millis)
                        if self.event_handler:
                            self.event_handler.on_message(message)
                with open(self.path_messages_stored, "w") as f:
                    f.write(json.dumps(data))
            except json.JSONDecodeError:
                logging.warning(f"Corrupted JSON in {self.path_messages}, content: '{text[:200]}'")
            except Exception as e:
                logging.error(f"Error in check_messages: {e}")

    def check_market_data(self):
        while self.ACTIVE:
            sleep(self.sleep_delay)
            if not self.START:
                continue
            text = self.try_read_file(self.path_market_data)
            if not text or text == self._last_market_data_str:
                continue

            try:
                data = json.loads(text)
                self._last_market_data_str = text
                if data != self.market_data:
                    self.market_data = data
                    if self.event_handler:
                        for symbol, values in data.items():
                            self.event_handler.on_tick(symbol, values.get("bid", 0), values.get("ask", 0))
            except json.JSONDecodeError:
                logging.warning(f"Corrupted JSON in {self.path_market_data}, content: '{text[:200]}'")
            except Exception as e:
                logging.error(f"Error in check_market_data: {e}")

    def check_bar_data(self):
        while self.ACTIVE:
            sleep(self.sleep_delay)
            if not self.START:
                continue
            text = self.try_read_file(self.path_bar_data)
            if not text or text == self._last_bar_data_str:
                continue

            try:
                data = json.loads(text)
                self._last_bar_data_str = text
                if data != self.bar_data:
                    self.bar_data = data
                    if self.event_handler:
                        for st, values in data.items():
                            symbol, time_frame = st.split("_")
                            self.event_handler.on_bar_data(
                                symbol,
                                time_frame,
                                values.get("time", 0),
                                values.get("open", 0),
                                values.get("high", 0),
                                values.get("low", 0),
                                values.get("close", 0),
                                values.get("tick_volume", 0),
                            )
            except json.JSONDecodeError:
                logging.warning(f"Corrupted JSON in {self.path_bar_data}, content: '{text[:200]}'")
            except Exception as e:
                logging.error(f"Error in check_bar_data: {e}")

    def check_historic_data(self):
        while self.ACTIVE:
            sleep(self.sleep_delay)
            if not self.START:
                continue

            text_hist_data = self.try_read_file(self.path_historic_data)
            try:
                if text_hist_data and text_hist_data != self._last_historic_data_str:
                    data = json.loads(text_hist_data)
                    self._last_historic_data_str = text_hist_data
                    for st, values in data.items():
                        self.historic_data[st] = values
                        if self.event_handler:
                            symbol, time_frame = st.split("_")
                            self.event_handler.on_historic_data(symbol, time_frame, values)
                    self.try_remove_file(self.path_historic_data)
            except json.JSONDecodeError:
                logging.warning(f"Corrupted JSON in {self.path_historic_data}, content: '{text_hist_data[:200]}'")
            except Exception as e:
                logging.error(f"Error in check_historic_data (data): {e}")

            text_hist_trades = self.try_read_file(self.path_historic_trades)
            try:
                if text_hist_trades and text_hist_trades != self._last_historic_trades_str:
                    data = json.loads(text_hist_trades)
                    self._last_historic_trades_str = text_hist_trades
                    self.historic_trades = data
                    if self.event_handler:
                        self.event_handler.on_historic_trades()
                    self.try_remove_file(self.path_historic_trades)
            except json.JSONDecodeError:
                logging.warning(f"Corrupted JSON in {self.path_historic_trades}, content: '{text_hist_trades[:200]}'")
            except Exception as e:
                logging.error(f"Error in check_historic_data (trades): {e}")

    def load_orders(self):
        text = self.try_read_file(self.path_orders_stored)
        if text:
            try:
                data = json.loads(text)
                self.account_info = data.get("account_info", {})
                self.open_orders = data.get("orders", {})
            except json.JSONDecodeError:
                logging.warning(f"Could not load stored orders, file is corrupted.")

    def load_messages(self):
        text = self.try_read_file(self.path_messages_stored)
        if text:
            try:
                data = json.loads(text)
                for millis in data.keys():
                    if int(millis) > self._last_messages_millis:
                        self._last_messages_millis = int(millis)
            except (json.JSONDecodeError, ValueError):
                logging.warning(f"Could not load stored messages, file is corrupted.")

    # --- ALL TRADE ACTION METHODS ARE THE SAME ---
    def open_order(
        self,
        symbol="EURUSD",
        order_type="buy",
        lots=0.01,
        price=0.0,
        stop_loss=0.0,
        take_profit=0.0,
        magic=0,
        comment="",
        expiration=0,
    ):
        data = [symbol, order_type, lots, price, stop_loss, take_profit, magic, comment, expiration]
        return self.send_command("OPEN_ORDER", ",".join(str(p) for p in data))

    # ... (modify_order, close_order, etc. are the same)
    def modify_order(self, ticket, price=0, stop_loss=0, take_profit=0, expiration=0):
        data = [ticket, price, stop_loss, take_profit, expiration]
        return self.send_command("MODIFY_ORDER", ",".join(str(p) for p in data))

    def close_order(self, ticket, lots=0.0):
        data = [ticket, lots]
        return self.send_command("CLOSE_ORDER", ",".join(str(p) for p in data))

    def close_all_orders(self):
        return self.send_command("CLOSE_ALL_ORDERS", "")

    def close_orders_by_symbol(self, symbol):
        return self.send_command("CLOSE_ORDERS_BY_SYMBOL", symbol)

    def close_orders_by_magic(self, magic):
        return self.send_command("CLOSE_ORDERS_BY_MAGIC", str(magic))

    def subscribe_symbols(self, symbols):
        self.send_command("SUBSCRIBE_SYMBOLS", ",".join(symbols))

    def subscribe_symbols_bar_data(self, symbols=[["EURUSD", "M1"]]):
        data = [f"{st[0]},{st[1]}" for st in symbols]
        return self.send_command("SUBSCRIBE_SYMBOLS_BAR_DATA", ",".join(str(p) for p in data))

    def get_historic_data(self, symbol="EURUSD", time_frame="D1", start=0, end=0):
        data = [symbol, time_frame, int(start), int(end)]
        return self.send_command("GET_HISTORIC_DATA", ",".join(str(p) for p in data))

    def get_historic_trades(self, lookback_days=30):
        return self.send_command("GET_HISTORIC_TRADES", str(lookback_days))

    def reset_command_ids(self):
        self.command_id = 0
        self.send_command("RESET_COMMAND_IDS", "")
        sleep(0.5)

    def send_command(self, command, content):
        self.lock.acquire()
        self.command_id = (self.command_id + 1) % 100000
        end_time = datetime.now(timezone.utc) + timedelta(seconds=self.max_retry_command_seconds)
        while datetime.now(timezone.utc) < end_time:
            success = False
            for i in range(self.num_command_files):
                file_path = f"{self.path_commands_prefix}{i}.txt"
                if not exists(file_path):
                    try:
                        with open(file_path, "w") as f:
                            f.write(f"<:{self.command_id}|{command}|{content}:>")
                        success = True
                        break
                    except Exception as e:
                        logging.error(f"Error writing command file: {e}")
            if success:
                break
            sleep(self.sleep_delay)
        self.lock.release()
        return self.command_id

    def wait_for_receipt(self, command_id: int, timeout_seconds: int = 5) -> bool:
        """
        Waits for a specific command ID to appear in the execution receipt file.
        This confirms the MT4 server has processed the command.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            text = self.try_read_file(self.path_execution_receipts)
            if text:
                try:
                    receipt_id, _ = text.split("|")
                    if int(receipt_id) == command_id:
                        print(f"[Receipt] Confirmed execution for command ID: {command_id}")
                        return True
                except (ValueError, IndexError):
                    print(f"[Receipt] WARN: Could not parse receipt file content: {text}")

            time.sleep(self.sleep_delay)

        print(f"[Receipt] ERROR: Timed out waiting for receipt for command ID: {command_id}")
        return False

    def _send_heartbeat(self):
        """Writes the current UTC timestamp to a file for the MQL4 EA to read."""
        try:
            with open(self.path_python_heartbeat, "w") as f:
                f.write(str(int(datetime.now(timezone.utc).timestamp())))
        except Exception as e:
            logging.error(f"Error sending heartbeat: {e}")
