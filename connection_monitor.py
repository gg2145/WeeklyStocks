#!/usr/bin/env python3
"""
IBKR Connection Monitor with Auto-Reconnection
Provides robust connection management for the Weekly ER Trading System
"""

import asyncio
import logging
import smtplib
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable, Any
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from dataclasses import dataclass
from pathlib import Path

try:
    from ib_insync import IB, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False

LOG = logging.getLogger(__name__)

@dataclass
class ConnectionConfig:
    """Configuration for IBKR connection"""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 7
    timeout: int = 10
    heartbeat_interval: int = 30  # seconds
    max_reconnect_attempts: int = 5
    reconnect_delay: int = 10  # seconds between attempts
    
@dataclass
class AlertConfig:
    """Configuration for alerts"""
    email_enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_user: str = ""
    email_password: str = ""
    alert_recipients: list = None
    
    def __post_init__(self):
        if self.alert_recipients is None:
            self.alert_recipients = []

class ConnectionMonitor:
    """Monitors IBKR connection health and handles reconnection"""
    
    def __init__(self, connection_config: ConnectionConfig = None, 
                 alert_config: AlertConfig = None):
        self.conn_config = connection_config or ConnectionConfig()
        self.alert_config = alert_config or AlertConfig()
        
        self.ib: Optional[IB] = None
        self.is_monitoring = False
        self.connection_healthy = False
        self.last_heartbeat = None
        self.reconnect_attempts = 0
        self.connection_stats = {
            'total_connections': 0,
            'total_disconnections': 0,
            'total_reconnections': 0,
            'uptime_start': None,
            'last_disconnect': None,
            'longest_uptime': timedelta(0)
        }
        
        # Callbacks for connection events
        self.on_connected_callback: Optional[Callable] = None
        self.on_disconnected_callback: Optional[Callable] = None
        self.on_reconnected_callback: Optional[Callable] = None
        
        # Load configuration from file if available
        self._load_config()
        
    def _load_config(self):
        """Load configuration from config.json"""
        try:
            config_path = Path("config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Update connection config
                self.conn_config.host = config.get("ib_host", self.conn_config.host)
                self.conn_config.port = int(config.get("ib_port", self.conn_config.port))
                self.conn_config.client_id = int(config.get("ib_client_id", self.conn_config.client_id))
                
                # Update alert config if present
                if "alerts" in config:
                    alert_cfg = config["alerts"]
                    self.alert_config.email_enabled = alert_cfg.get("email_enabled", False)
                    self.alert_config.smtp_server = alert_cfg.get("smtp_server", self.alert_config.smtp_server)
                    self.alert_config.smtp_port = int(alert_cfg.get("smtp_port", self.alert_config.smtp_port))
                    self.alert_config.email_user = alert_cfg.get("email_user", "")
                    self.alert_config.email_password = alert_cfg.get("email_password", "")
                    self.alert_config.alert_recipients = alert_cfg.get("recipients", [])
                    
        except Exception as e:
            LOG.warning(f"Could not load config: {e}")
    
    def set_callbacks(self, on_connected: Callable = None, 
                     on_disconnected: Callable = None,
                     on_reconnected: Callable = None):
        """Set callback functions for connection events"""
        self.on_connected_callback = on_connected
        self.on_disconnected_callback = on_disconnected
        self.on_reconnected_callback = on_reconnected
    
    async def connect(self) -> bool:
        """Establish initial connection to IBKR"""
        if not IB_AVAILABLE:
            LOG.error("ib-insync not available")
            return False
            
        try:
            if self.ib is None:
                self.ib = IB()
                
            LOG.info(f"Connecting to IBKR at {self.conn_config.host}:{self.conn_config.port}")
            
            await self.ib.connectAsync(
                host=self.conn_config.host,
                port=self.conn_config.port,
                clientId=self.conn_config.client_id,
                timeout=self.conn_config.timeout
            )
            
            if self.ib.isConnected():
                self.connection_healthy = True
                self.last_heartbeat = datetime.now()
                self.reconnect_attempts = 0
                self.connection_stats['total_connections'] += 1
                self.connection_stats['uptime_start'] = datetime.now()
                
                LOG.info("Successfully connected to IBKR")
                await self._send_alert("IBKR Connection Established", 
                                     f"Successfully connected to IBKR at {datetime.now()}")
                
                if self.on_connected_callback:
                    try:
                        await self.on_connected_callback(self.ib)
                    except Exception as e:
                        LOG.error(f"Error in connected callback: {e}")
                
                return True
            else:
                LOG.error("Connection failed - not connected after connect call")
                return False
                
        except Exception as e:
            LOG.error(f"Connection failed: {e}")
            await self._send_alert("IBKR Connection Failed", 
                                 f"Failed to connect to IBKR: {e}")
            return False
    
    async def disconnect(self):
        """Gracefully disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            try:
                self.ib.disconnect()
                LOG.info("Disconnected from IBKR")
            except Exception as e:
                LOG.error(f"Error during disconnect: {e}")
        
        self.connection_healthy = False
        self.is_monitoring = False
    
    async def start_monitoring(self):
        """Start connection monitoring loop"""
        if not self.ib or not self.ib.isConnected():
            LOG.error("Cannot start monitoring - not connected")
            return
            
        self.is_monitoring = True
        LOG.info(f"Starting connection monitoring (heartbeat every {self.conn_config.heartbeat_interval}s)")
        
        while self.is_monitoring:
            try:
                await self._heartbeat_check()
                await asyncio.sleep(self.conn_config.heartbeat_interval)
            except Exception as e:
                LOG.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying
    
    async def stop_monitoring(self):
        """Stop connection monitoring"""
        self.is_monitoring = False
        LOG.info("Connection monitoring stopped")
    
    async def _heartbeat_check(self):
        """Perform heartbeat check and handle reconnection if needed"""
        if not self.ib:
            return
            
        try:
            # Check if connection is still alive
            if self.ib.isConnected():
                # Try a simple API call to verify connection health
                accounts = self.ib.managedAccounts()
                if accounts:
                    self.last_heartbeat = datetime.now()
                    if not self.connection_healthy:
                        # Connection was restored
                        self.connection_healthy = True
                        self.reconnect_attempts = 0
                        LOG.info("Connection health restored")
                else:
                    LOG.warning("Heartbeat check failed - no accounts returned")
                    await self._handle_connection_loss()
            else:
                LOG.warning("Connection lost - attempting reconnection")
                await self._handle_connection_loss()
                
        except Exception as e:
            LOG.error(f"Heartbeat check failed: {e}")
            await self._handle_connection_loss()
    
    async def _handle_connection_loss(self):
        """Handle connection loss and attempt reconnection"""
        if self.connection_healthy:
            # First time detecting the loss
            self.connection_healthy = False
            self.connection_stats['total_disconnections'] += 1
            self.connection_stats['last_disconnect'] = datetime.now()
            
            # Calculate uptime
            if self.connection_stats['uptime_start']:
                uptime = datetime.now() - self.connection_stats['uptime_start']
                if uptime > self.connection_stats['longest_uptime']:
                    self.connection_stats['longest_uptime'] = uptime
            
            LOG.error("Connection lost - starting reconnection attempts")
            await self._send_alert("IBKR Connection Lost", 
                                 f"Connection lost at {datetime.now()}. Attempting reconnection...")
            
            if self.on_disconnected_callback:
                try:
                    await self.on_disconnected_callback()
                except Exception as e:
                    LOG.error(f"Error in disconnected callback: {e}")
        
        # Attempt reconnection
        if self.reconnect_attempts < self.conn_config.max_reconnect_attempts:
            self.reconnect_attempts += 1
            LOG.info(f"Reconnection attempt {self.reconnect_attempts}/{self.conn_config.max_reconnect_attempts}")
            
            try:
                # Disconnect cleanly first
                if self.ib and self.ib.isConnected():
                    self.ib.disconnect()
                
                await asyncio.sleep(self.conn_config.reconnect_delay)
                
                # Attempt reconnection
                success = await self.connect()
                if success:
                    self.connection_stats['total_reconnections'] += 1
                    LOG.info("Reconnection successful")
                    await self._send_alert("IBKR Reconnection Successful", 
                                         f"Successfully reconnected at {datetime.now()}")
                    
                    if self.on_reconnected_callback:
                        try:
                            await self.on_reconnected_callback(self.ib)
                        except Exception as e:
                            LOG.error(f"Error in reconnected callback: {e}")
                else:
                    LOG.error(f"Reconnection attempt {self.reconnect_attempts} failed")
                    
            except Exception as e:
                LOG.error(f"Reconnection attempt failed: {e}")
        else:
            LOG.critical("Maximum reconnection attempts exceeded - giving up")
            await self._send_alert("IBKR Reconnection Failed", 
                                 f"Failed to reconnect after {self.conn_config.max_reconnect_attempts} attempts. Manual intervention required.")
            self.is_monitoring = False
    
    async def _send_alert(self, subject: str, message: str):
        """Send alert via email if configured"""
        if not self.alert_config.email_enabled or not self.alert_config.alert_recipients:
            return
            
        try:
            msg = MimeMultipart()
            msg['From'] = self.alert_config.email_user
            msg['To'] = ', '.join(self.alert_config.alert_recipients)
            msg['Subject'] = f"[Trading System] {subject}"
            
            body = f"""
Trading System Alert

{message}

Connection Statistics:
- Total Connections: {self.connection_stats['total_connections']}
- Total Disconnections: {self.connection_stats['total_disconnections']}
- Total Reconnections: {self.connection_stats['total_reconnections']}
- Longest Uptime: {self.connection_stats['longest_uptime']}
- Current Status: {'Connected' if self.connection_healthy else 'Disconnected'}

Time: {datetime.now()}
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.alert_config.smtp_server, self.alert_config.smtp_port)
            server.starttls()
            server.login(self.alert_config.email_user, self.alert_config.email_password)
            text = msg.as_string()
            server.sendmail(self.alert_config.email_user, self.alert_config.alert_recipients, text)
            server.quit()
            
            LOG.info(f"Alert sent: {subject}")
            
        except Exception as e:
            LOG.error(f"Failed to send alert: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = self.connection_stats.copy()
        stats['connection_healthy'] = self.connection_healthy
        stats['is_monitoring'] = self.is_monitoring
        stats['last_heartbeat'] = self.last_heartbeat
        stats['reconnect_attempts'] = self.reconnect_attempts
        
        if self.connection_stats['uptime_start'] and self.connection_healthy:
            stats['current_uptime'] = datetime.now() - self.connection_stats['uptime_start']
        else:
            stats['current_uptime'] = timedelta(0)
            
        return stats
    
    def get_ib_instance(self) -> Optional[IB]:
        """Get the IB instance for trading operations"""
        return self.ib if self.connection_healthy else None

class RobustIBConnection:
    """Wrapper class that provides a robust IB connection with automatic monitoring"""
    
    def __init__(self, connection_config: ConnectionConfig = None, 
                 alert_config: AlertConfig = None):
        self.monitor = ConnectionMonitor(connection_config, alert_config)
        self._monitoring_task: Optional[asyncio.Task] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        success = await self.monitor.connect()
        if not success:
            raise ConnectionError("Failed to establish IBKR connection")
        
        # Start monitoring in background
        self._monitoring_task = asyncio.create_task(self.monitor.start_monitoring())
        return self.monitor.get_ib_instance()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._monitoring_task:
            await self.monitor.stop_monitoring()
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        await self.monitor.disconnect()
    
    def set_callbacks(self, **kwargs):
        """Set connection event callbacks"""
        self.monitor.set_callbacks(**kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return self.monitor.get_connection_stats()

# Example usage and testing
async def example_trading_loop():
    """Example of how to use the robust connection in a trading loop"""
    
    # Configure connection and alerts
    conn_config = ConnectionConfig(
        host="127.0.0.1",
        port=7497,
        client_id=7,
        heartbeat_interval=30,
        max_reconnect_attempts=5
    )
    
    alert_config = AlertConfig(
        email_enabled=False,  # Set to True and configure for real alerts
        email_user="your_email@gmail.com",
        email_password="your_app_password",
        alert_recipients=["trader@example.com"]
    )
    
    async def on_connected(ib):
        LOG.info("Trading system connected - ready to trade")
        # Initialize trading components here
    
    async def on_disconnected():
        LOG.warning("Trading system disconnected - pausing operations")
        # Pause trading operations here
    
    async def on_reconnected(ib):
        LOG.info("Trading system reconnected - resuming operations")
        # Resume trading operations here
    
    # Use robust connection
    async with RobustIBConnection(conn_config, alert_config) as ib:
        # Set up callbacks
        monitor = RobustIBConnection(conn_config, alert_config).monitor
        monitor.set_callbacks(
            on_connected=on_connected,
            on_disconnected=on_disconnected,
            on_reconnected=on_reconnected
        )
        
        # Main trading loop
        while True:
            try:
                if ib and ib.isConnected():
                    # Perform trading operations
                    accounts = ib.managedAccounts()
                    LOG.info(f"Active accounts: {accounts}")
                    
                    # Your trading logic here
                    await asyncio.sleep(60)  # Example: check every minute
                else:
                    LOG.warning("No connection available - waiting...")
                    await asyncio.sleep(10)
                    
            except KeyboardInterrupt:
                LOG.info("Shutting down trading system...")
                break
            except Exception as e:
                LOG.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)

def main():
    """Main function for testing"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if not IB_AVAILABLE:
        print("ib-insync not available - install with: pip install ib-insync")
        return
    
    print("Starting IBKR Connection Monitor Test...")
    print("Press Ctrl+C to stop")
    
    try:
        asyncio.run(example_trading_loop())
    except KeyboardInterrupt:
        print("\nShutdown complete")

if __name__ == "__main__":
    main()
