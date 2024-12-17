import socket
import threading
import datetime
import json
from pathlib import Path
import paramiko
import requests
import time

class SSHMonitor(paramiko.ServerInterface):
    def __init__(self, host='0.0.0.0', port=22):
        self.host = host
        self.port = port
        self.log_file = Path('ssh_attempts.json')
        self.city_file = Path('city_data.json')
        self.attempts = self._load_attempts()
        self.city_data = self._load_city_data()
        self.key = paramiko.RSAKey.generate(2048)
        
    def _load_attempts(self):
        """Load existing attempts from log file"""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                return json.load(f)
        return []

    def _load_city_data(self):
        """Load existing city data from file"""
        if self.city_file.exists():
            with open(self.city_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_attempts(self):
        """Save attempts to log file"""
        with open(self.log_file, 'w') as f:
            json.dump(self.attempts, f, indent=2)

    def _save_city_data(self):
        """Save city data to file"""
        with open(self.city_file, 'w') as f:
            json.dump(self.city_data, f, indent=2)

    def _get_city(self, ip):
        """Get city for IP address"""
        # Check if we already have this IP in our cache
        if ip in self.city_data:
            return self.city_data[ip]

        # If not, query the API
        try:
            # Add delay to respect rate limits
            time.sleep(1)
            response = requests.get(f'http://ip-api.com/json/{ip}?fields=status,city')
            data = response.json()
            
            if data['status'] == 'success':
                # Cache the result
                self.city_data[ip] = data['city']
                self._save_city_data()
                return data['city']
            return None
            
        except Exception as e:
            print(f"Error getting city for IP {ip}: {e}")
            return None

    def check_auth_password(self, username, password):
        """Record authentication attempt and reject it"""
        city = self._get_city(self.client_ip)
        
        # Only record if we successfully got the city
        if city is not None:
            attempt = {
                'timestamp': datetime.datetime.now().isoformat(),
                'ip': self.client_ip,
                'password': password,
                'city': city
            }
            self.attempts.append(attempt)
            self._save_attempts()
            print(f"Recorded attempt from {self.client_ip} ({city})")
            
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        """Allow password authentication only"""
        return 'password'

    def _handle_connection(self, client_socket, address):
        """Handle individual connection attempt"""
        try:
            self.client_ip = address[0]
            
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(self.key)
            transport.start_server(server=self)
            
            # Wait for authentication attempts
            channel = transport.accept(20)
            if channel is not None:
                channel.close()

        except Exception as e:
            print(f"Error handling connection: {e}")
        finally:
            try:
                transport.close()
            except:
                pass
            client_socket.close()

    def start(self):
        """Start the SSH monitoring server"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        
        print(f"Monitoring SSH attempts on {self.host}:{self.port}")
        print(f"Loaded {len(self.city_data)} cached city records")
        
        try:
            while True:
                client, address = server.accept()
                thread = threading.Thread(
                    target=self._handle_connection,
                    args=(client, address)
                )
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print("\nShutting down monitor...")
        finally:
            server.close()

if __name__ == '__main__':
    # Note: Running on port 22 requires root/admin privileges
    monitor = SSHMonitor(port=22)
    monitor.start()