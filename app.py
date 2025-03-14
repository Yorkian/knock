import socket
import threading
import datetime
import csv
import json  # Still needed for API responses
from pathlib import Path
import paramiko
import requests
import time
from typing import Optional, Dict, Any, List
from flask import Flask, render_template_string, jsonify, request
from collections import Counter
from datetime import timedelta
import os

# Flask application initialization
app = Flask(__name__)
app.static_folder = 'static'

# Ensure the static directory exists
os.makedirs('static', exist_ok=True)

# Language translations
TRANSLATIONS = {
    'en': {
        'title': 'Who is Knocking at My Window',
        'refresh': 'Refresh',
        'total_attempts': 'Total Attempts',
        'unique_ips': 'Unique IPs',
        'attempt_cities': 'Attempt Cities',
        'attempt_countries': 'Attempt Countries',
        'global_distribution': 'Global Distribution',
        'ip_ranking': 'IP Address Ranking',
        'city_ranking': 'City Ranking',
        'hour_trend': '24-Hour Trend',
        'attempts': ' attempts',
        'loading': 'Loading data...',
        'last_update': 'Last Update',
        'time_range_all': 'All',
        'time_range_24h': '24h',
        'attack_times': 'attacks',
        'country_region': 'Country',
        'province_state': 'Province/State',
        'switch_to_24h': '24h',
        'switch_to_all': 'All',
        'switch_to_zh': '中文',
        'switch_to_en': 'English',
        'attempt_times': ' attempts'
    },
    'zh': {
        'title': '是谁在敲打我窗',
        'refresh': '刷新',
        'total_attempts': '总尝试次数',
        'unique_ips': '独立IP数量',
        'attempt_cities': '尝试城市数量',
        'attempt_countries': '尝试国家数量',
        'global_distribution': '全球尝试分布图',
        'ip_ranking': 'IP 地址排行榜',
        'city_ranking': '城市排行榜',
        'hour_trend': '24小时趋势',
        'attempts': '次',
        'loading': '正在加载数据...',
        'last_update': '最后更新时间',
        'time_range_all': '全部',
        'time_range_24h': '24小时',
        'attack_times': '次攻击',
        'country_region': '国家',
        'province_state': '省/州',
        'switch_to_24h': '24小时',
        'switch_to_all': '全部',
        'switch_to_zh': '中文',
        'switch_to_en': 'English',
        'attempt_times': '次尝试'
    }
}

# Predefine the coordinates and country information of major cities
KNOWN_LOCATIONS = {
    "Moscow": {"lat": 55.7558, "lon": 37.6173, "country": "Russia", "admin_area": "Moscow"},
    "Taichung": {"lat": 24.144, "lon": 120.6844, "country": "China", "admin_area": "Taiwan"},
    "Taipei": {"lat": 25.0289, "lon": 121.521, "country": "China", "admin_area": "Taiwan"},
    "New Taipei City": {"lat": 25.062, "lon": 121.457, "country": "China", "admin_area": "Taiwan"},
    "Kaohsiung": {"lat": 22.6148, "lon": 120.3139, "country": "China", "admin_area": "Taiwan"},
    "Tainan": {"lat": 22.9908, "lon": 120.2133, "country": "China", "admin_area": "Taiwan"},
    "Hsinchu": {"lat": 24.8036, "lon": 120.9686, "country": "China", "admin_area": "Taiwan"},
    "Keelung": {"lat": 25.1283, "lon": 121.7419, "country": "China", "admin_area": "Taiwan"},
    "Chiayi": {"lat": 23.4800, "lon": 120.4491, "country": "China", "admin_area": "Taiwan"},
    "Changhua": {"lat": 24.0734, "lon": 120.5134, "country": "China", "admin_area": "Taiwan"},
    "Taoyuan": {"lat": 24.9937, "lon": 121.3010, "country": "China", "admin_area": "Taiwan"},
    "Pingtung": {"lat": 22.6762, "lon": 120.4929, "country": "China", "admin_area": "Taiwan"},
    "Yilan": {"lat": 24.7570, "lon": 121.7533, "country": "China", "admin_area": "Taiwan"},
    "Hualien": {"lat": 23.9910, "lon": 121.6111, "country": "China", "admin_area": "Taiwan"},
    "Taitung": {"lat": 22.7583, "lon": 121.1444, "country": "China", "admin_area": "Taiwan"},
    "Miaoli": {"lat": 24.5657, "lon": 120.8214, "country": "China", "admin_area": "Taiwan"},
    "Nantou": {"lat": 23.9157, "lon": 120.6869, "country": "China", "admin_area": "Taiwan"}
}

COUNTRY_INFO = {
    "Moscow": "Russia"
}

class GeoData:
    def __init__(self):
        self.geo_file = Path('geo_data.csv')
        self.geo_data = self._load_geo_data()
        self.verify_cache()
        # Add cache hit record collection
        self.cache_hits = set()

    def _load_geo_data(self):
        """Load cached geographical location data from CSV"""
        geo_data = {}
        if self.geo_file.exists():
            try:
                with open(self.geo_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Convert lat/lon to float
                        city = row['city']
                        geo_data[city] = {
                            'lat': float(row['lat']),
                            'lon': float(row['lon']),
                            'country': row['country'],
                            'admin_area': row['admin_area'],
                            'last_updated': row['last_updated']
                        }
                return geo_data
            except Exception as e:
                print(f"Error loading geo_data.csv: {e}")
                return {}
        return {}

    def _save_geo_data(self):
        """Save geographical location data to CSV file"""
        try:
            fieldnames = ['city', 'lat', 'lon', 'country', 'admin_area', 'last_updated']
            
            with open(self.geo_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for city, data in self.geo_data.items():
                    row = {
                        'city': city,
                        'lat': data['lat'],
                        'lon': data['lon'],
                        'country': data['country'],
                        'admin_area': data['admin_area'],
                        'last_updated': data['last_updated']
                    }
                    writer.writerow(row)
        except Exception as e:
            print(f"Error saving geo data: {e}")

    def verify_cache(self):
        """Verify the accuracy of the cached data"""
        verified_data = {}
        for city, location in self.geo_data.items():
            if self._verify_location(city, location):
                verified_data[city] = location
            else:
                print(f"Removing invalid cache entry for {city}")
        self.geo_data = verified_data
        self._save_geo_data()
        
    def _verify_location(self, city, location):
        """Verify the accuracy of the location data"""
        if city in KNOWN_LOCATIONS:
            known = KNOWN_LOCATIONS[city]
            return abs(location['lat'] - known['lat']) < 1 and abs(location['lon'] - known['lon']) < 1
            
        if city in COUNTRY_INFO:
            return location.get('country', '') == COUNTRY_INFO[city]
            
        return True
            
    def get_city_location(self, city):
        """Get the geographical location of the city"""
        # For the same instance, each city prints the cache hit information only once.
        if city in KNOWN_LOCATIONS:
            if city not in self.cache_hits:
                print(f"Using predefined location for {city}")
                self.cache_hits.add(city)
            return KNOWN_LOCATIONS[city]
            
        if city in self.geo_data:
            if city not in self.cache_hits:
                print(f"Using cached data for {city}")
                self.cache_hits.add(city)
            return self.geo_data[city]
            
        try:
            print(f"Fetching location for {city} from Bing Maps API")
            url = f"http://dev.virtualearth.net/REST/v1/Locations"
            
            params = {
                'query': city,
                'key': BING_API_KEY,
                'maxResults': 5,
                'culture': 'zh-CN',
                'includeNeighborhood': 1,
                'include': 'queryParse'
            }
            
            if city in COUNTRY_INFO:
                params['query'] = f"{city}, {COUNTRY_INFO[city]}"
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if data['statusCode'] == 200 and data['resourceSets'] and data['resourceSets'][0]['resources']:
                    for resource in data['resourceSets'][0]['resources']:
                        location = resource['point']['coordinates']
                        country = resource.get('address', {}).get('countryRegion', '')
                        admin_area = resource.get('address', {}).get('adminDistrict', '')
                        
                        if city in COUNTRY_INFO and country != COUNTRY_INFO[city]:
                            continue
                            
                        result = {
                            'lat': location[0],
                            'lon': location[1],
                            'country': country,
                            'admin_area': admin_area,
                            'last_updated': datetime.datetime.now().isoformat()
                        }
                        
                        if self._verify_location(city, result):
                            self.geo_data[city] = result
                            self._save_geo_data()
                            print(f"Successfully found and cached location for {city}: {result}")
                            return result
                    
            print(f"Could not find valid location for {city}")
            return None
            
        except Exception as e:
            print(f"Error getting location for {city}: {e}")
            return None

class SSHMonitor(paramiko.ServerInterface):
    def __init__(self, host='0.0.0.0', port=22):
        self.host = host
        self.port = port
        self.ssh_log_file = Path('ssh_attempts.csv')
        self.city_data_file = Path('city_data.csv')
        
        # Initialize or load data files
        self.attempts = self._load_attempts()
        self.city_data = self._load_city_data()
        
        # Generate server keys
        self.key = paramiko.RSAKey.generate(2048)
        
        # Add a connection counter
        self.connection_count = 0
        self.last_cleanup = time.time()

    def _load_attempts(self) -> List[Dict]:
        """Load SSH attempt logs from CSV"""
        attempts = []
        if self.ssh_log_file.exists():
            try:
                with open(self.ssh_log_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        attempts.append(row)
                return attempts
            except Exception as e:
                print(f"Error loading ssh_attempts.csv: {e}")
                return []
        return []
    
    def _save_attempts(self) -> None:
        """Save SSH attempt logs to CSV"""
        try:
            # Get all field names from attempts
            fieldnames = ['timestamp', 'ip', 'password', 'city']
            
            with open(self.ssh_log_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for attempt in self.attempts:
                    writer.writerow(attempt)
        except Exception as e:
            print(f"Error saving attempts data: {e}")
    
    def _load_city_data(self) -> Dict[str, str]:
        """Load IP to city mapping from CSV"""
        city_data = {}
        if self.city_data_file.exists():
            try:
                with open(self.city_data_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        city_data[row['ip']] = row['city']
                return city_data
            except Exception as e:
                print(f"Error loading city_data.csv: {e}")
                return {}
        return {}
    
    def _save_city_data(self) -> None:
        """Save IP to city mapping to CSV"""
        try:
            with open(self.city_data_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['ip', 'city'])
                writer.writeheader()
                for ip, city in self.city_data.items():
                    writer.writerow({'ip': ip, 'city': city})
        except Exception as e:
            print(f"Error saving city data: {e}")

    def _get_location_data(self, ip: str) -> Optional[Dict]:
        """Get the geographical location information of the IP address"""
        if ip in self.city_data:
            city = self.city_data[ip]
            return {"city": city}

        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon"
            response = requests.get(url)
            data = response.json()
            
            if data["status"] != "success":
                return None

            self.city_data[ip] = data["city"]
            self._save_city_data()

            # Create a GeoData instance to save geo data
            geo = GeoData()
            if data["city"] not in geo.geo_data:
                geo.geo_data[data["city"]] = {
                    "lat": data["lat"],
                    "lon": data["lon"],
                    "country": data["country"],
                    "admin_area": data["regionName"],
                    "last_updated": datetime.datetime.now().isoformat()
                }
                geo._save_geo_data()

            return {
                "city": data["city"]
            }

        except Exception as e:
            print(f"Error getting location data for IP {ip}: {e}")
            return None

    def check_auth_password(self, username: str, password: str) -> int:
        """Record the authentication attempt and reject"""
        time.sleep(4)
        
        location_data = self._get_location_data(self.client_ip)
        if location_data is None:
            return paramiko.AUTH_FAILED

        attempt = {
            "timestamp": datetime.datetime.now().isoformat(),
            "ip": self.client_ip,
            "password": password,
            "city": location_data["city"]
        }
        
        self.attempts.append(attempt)
        self._save_attempts()
        
        print(f"Knocking - IP: {self.client_ip}, City: {location_data['city']}")
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        """Allow password authentication"""
        return 'password'

    def _handle_connection(self, client_socket: socket.socket, address: tuple) -> None:
        """Process a single connection"""
        transport = None
        try:
            self.client_ip = address[0]
            self.client_port = address[1]
            
            client_socket.settimeout(10)
            
            # Check if it is an SSH connection
            try:
                initial_data = client_socket.recv(4, socket.MSG_PEEK)
                # SSH connections typically start with "SSH-"
                if not initial_data.startswith(b'SSH-'):
                    print(f"[{datetime.datetime.now()}] Non-SSH connection attempt from {self.client_ip}:{self.client_port}")
                    return
            except (socket.timeout, ConnectionResetError, EOFError):
                print(f"[{datetime.datetime.now()}] Quick disconnect from {self.client_ip}:{self.client_port}")
                return
            except Exception as e:
                print(f"[{datetime.datetime.now()}] Error checking connection type: {e}")
                return
                
            transport = paramiko.Transport(client_socket)
            transport.local_version = "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.1"
            transport.add_server_key(self.key)
            
            try:
                transport.start_server(server=self)
                channel = transport.accept(timeout=10)
                if channel is not None:
                    channel.close()
            except paramiko.SSHException as e:
                # Stop printing detailed stack traces
                print(f"[{datetime.datetime.now()}] SSH negotiation failed with {self.client_ip}:{self.client_port} - {str(e)}")
                return
            except Exception as e:
                print(f"[{datetime.datetime.now()}] Unexpected error in SSH negotiation with {self.client_ip}:{self.client_port}: {str(e)}")
                return

        except Exception as e:
            print(f"[{datetime.datetime.now()}] Connection handler error with {self.client_ip}:{self.client_port}: {str(e)}")
        finally:
            if transport:
                try:
                    transport.close()
                except:
                    pass
            try:
                client_socket.close()
            except:
                pass
            
            self.connection_count += 1
            if self.connection_count % 1000 == 0:
                self._cleanup()

    def _cleanup(self):
        """Regular cleaning and maintenance"""
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:
            import gc
            gc.collect()
            self.last_cleanup = current_time

    def start(self) -> None:
        """Start the SSH monitoring server"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # TCP keepalive option
        server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        server.settimeout(5)
        
        try:
            server.bind((self.host, self.port))
            server.listen(10)
            
            print(f"Start monitoring SSH attempts, listening address {self.host}:{self.port}")
            
            while True:
                try:
                    client, address = server.accept()
                    # Set the TCP keepalive option for the client socket
                    client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    thread = threading.Thread(
                        target=self._handle_connection,
                        args=(client, address)
                    )
                    thread.daemon = True
                    thread.start()
                    
                    time.sleep(0.05)
                    
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    print("\nShutting down the monitoring system...")
                    break
                except Exception as e:
                    print(f"[{datetime.datetime.now()}] Error occurred when accepting connection: {e}")
                    time.sleep(1)
                    
        finally:
            try:
                server.close()
            except:
                pass

def load_attempts():
    """Load SSH attempt logs from CSV"""
    attempts = []
    try:
        with open('ssh_attempts.csv', 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                attempts.append(row)
        return attempts
    except (FileNotFoundError, csv.Error):
        return []

def get_stats(time_range='all'):
    """Obtain statistical data"""
    attempts = load_attempts()
    
    # If the time range is 24 hours, filter the data.
    if time_range == '24h':
        now = datetime.datetime.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        attempts = [attempt for attempt in attempts if datetime.datetime.fromisoformat(attempt['timestamp']) >= twenty_four_hours_ago]
    
    # Create a single GeoData instance outside the loop
    geo = GeoData()
    
    # Initialize the counter
    ip_counts = Counter()
    city_counts = Counter()
    country_counts = Counter()
    hourly_counts = Counter()
    now = datetime.datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    ip_city_map = {}
    
    # Process each record
    for attempt in attempts:
        ip = attempt['ip']
        city = attempt.get('city', 'Unknown')
        ip_city_map[ip] = city
        
        # Get geographical location information
        location = geo.get_city_location(city)
        if location and 'country' in location:
            country = location['country']
            country_counts[country] += 1
            
        # Processing time trend data
        try:
            timestamp = datetime.datetime.fromisoformat(attempt['timestamp'])
            if timestamp >= twenty_four_hours_ago:
                hour = timestamp.strftime('%H:00')
                hourly_counts[hour] += 1
        except:
            pass
            
        ip_counts[ip] += 1
        city_counts[city] += 1

    # Get the top 10 IPs
    top_ips = [(ip, ip_city_map[ip], count) for ip, count in ip_counts.most_common(10)]
    # Get the top 10 ranked cities
    top_cities = city_counts.most_common(10)
    
    # Generate 24-hour trend data
    hours = []
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    for i in range(24):
        hour = current_hour - timedelta(hours=i)
        hour_str = hour.strftime('%H:00')
        hours.append({
            'hour': hour_str,
            'count': hourly_counts.get(hour_str, 0)
        })
    hours.reverse()

    # Return the statistical results
    return {
        'top_ips': top_ips,
        'top_cities': top_cities,
        'hourly_trend': hours,
        'total_attempts': len(attempts),
        'unique_ips': len(ip_counts),
        'unique_cities': len(city_counts),
        'unique_countries': len(country_counts)
    }

@app.route('/api/map_data')
def map_data():
    """Provide map data API"""
    time_range = request.args.get('time_range', 'all')
    geo = GeoData()
    attempts = load_attempts()
    
    if time_range == '24h':
        now = datetime.datetime.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        attempts = [attempt for attempt in attempts if datetime.datetime.fromisoformat(attempt['timestamp']) >= twenty_four_hours_ago]
    
    city_counts = Counter()
    for attempt in attempts:
        city = attempt.get('city', 'Unknown')
        if city != 'Unknown':
            city_counts[city] += 1
    
    map_points = []
    for city, count in city_counts.items():
        location = geo.get_city_location(city)
        if location:
            point_data = {
                'city': city,
                'count': count,
                'lat': location['lat'],
                'lon': location['lon']
            }
            if 'country' in location:
                point_data['country'] = location['country']
            if 'admin_area' in location:
                point_data['admin_area'] = location['admin_area']
            map_points.append(point_data)
    
    return jsonify(map_points)

# HTML template content
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ t.title }}</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f2f5;
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 0 20px;
        }
        .refresh-btn {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .refresh-btn:hover {
            background-color: #45a049;
        }
        .language-selector {
            margin-left: 10px;
            padding: 8px 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .language-selector:hover {
            background-color: #45a049;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 20px;
            padding: 0 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }
        .container {
            display: flex;
            gap: 20px;
            margin-top: 20px;
            padding: 0 20px;
        }
        .column {
            flex: 1;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .rank-list {
            list-style-type: none;
            padding: 0;
        }
        .rank-item {
            padding: 10px;
            margin: 5px 0;
            background: #f8f9fa;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
        }
        .rank-number {
            display: inline-block;
            width: 24px;
            height: 24px;
            background: #4CAF50;
            color: white;
            text-align: center;
            line-height: 24px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .map-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px;
            overflow: hidden;
        }
        .map-wrapper {
            position: relative;
            width: 100%;
            padding-top: 42%;
            overflow: hidden;
        }
        .map-content {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }
        #world-map {
            width: 100%;
            height: 100%;
            background-image: url('/static/defaultMap.jpg');
            background-size: 100% 100%;
            background-repeat: no-repeat;
            background-position: center;
            position: relative;
        }
        .attack-point {
            fill: #ff4444;
            opacity: 0.6;
            transition: all 0.3s;
            filter: url(#glow);
        }
        .attack-point:hover {
            opacity: 1;
            cursor: pointer;
        }
        .tooltip {
            position: fixed;
            padding: 8px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            white-space: pre-line;
            max-width: 200px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .trend-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px;
            position: relative;
        }
        .trend-chart {
            width: 100%;
            padding: 20px 0;
        }
        .chart-wrapper {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            height: 200px;
            width: 100%;
            padding: 0 10px;
        }
        .bar-wrapper {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 20px;
            margin: 0 1px;
        }
        .bar {
            width: 15px;
            background-color: #4CAF50;
            border-radius: 2px 2px 0 0;
            transition: all 0.3s;
            cursor: pointer;
        }
        .hour-label {
            margin-top: 5px;
            font-size: 11px;
            color: #666;
            transform: rotate(-45deg);
            transform-origin: top right;
            white-space: nowrap;
        }
        #loading-indicator {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px 30px;
            border-radius: 5px;
            display: none;
            z-index: 1000;
        }
        .button-group {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .custom-button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
            font-size: 14px;
            min-width: 100px;
            text-align: center;
        }
        
        .custom-button:hover {
            background-color: #45a049;
        }
        
        .custom-button.active {
            background-color: #357a38;
        }
    </style>
</head>
<body>
    <div id="loading-indicator">{{ t.loading }}</div>
    <div class="header">
        <h1>{{ t.title }}</h1>
        <div class="button-group">
            <button class="custom-button" onclick="refreshData()">{{ t.refresh }}</button>
            <button class="custom-button" id="timeRangeToggle" onclick="toggleTimeRange()">
                {% if time_range == 'all' %}
                    {{ t.switch_to_24h }}
                {% else %}
                    {{ t.switch_to_all }}
                {% endif %}
            </button>
            <button class="custom-button" onclick="toggleLanguage()">
                {% if lang == 'en' %}
                    {{ t.switch_to_zh }}
                {% else %}
                    {{ t.switch_to_en }}
                {% endif %}
            </button>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <h3>{{ t.total_attempts }}</h3>
            <div class="stat-number">{{ stats.total_attempts }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ t.unique_ips }}</h3>
            <div class="stat-number">{{ stats.unique_ips }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ t.attempt_cities }}</h3>
            <div class="stat-number">{{ stats.unique_cities }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ t.attempt_countries }}</h3>
            <div class="stat-number">{{ stats.unique_countries }}</div>
        </div>
    </div>

    <div class="map-container">
        <h2>{{ t.global_distribution }}</h2>
        <div class="map-wrapper">
            <div class="map-content">
                <div id="tooltip" class="tooltip"></div>
                <svg id="world-map" viewBox="0 0 360 180" preserveAspectRatio="xMidYMid meet">
                    <defs>
                        <filter id="glow">
                            <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                            <feMerge>
                                <feMergeNode in="coloredBlur"/>
                                <feMergeNode in="SourceGraphic"/>
                            </feMerge>
                        </filter>
                    </defs>
                </svg>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="column">
            <h2>{{ t.ip_ranking }}</h2>
            <ul class="rank-list">
                {% for ip, city, count in stats.top_ips %}
                <li class="rank-item">
                    <span>
                        <span class="rank-number">{{ loop.index }}</span>
                        {{ ip }} ({{ city }})
                    </span>
                    <span>{{ count }}{{ t.attempts }}</span>
                </li>
                {% endfor %}
            </ul>
        </div>
        <div class="column">
            <h2>{{ t.city_ranking }}</h2>
            <ul class="rank-list">
                {% for city, count in stats.top_cities %}
                <li class="rank-item">
                    <span>
                        <span class="rank-number">{{ loop.index }}</span>
                        {{ city }}
                    </span>
                    <span>{{ count }}{{ t.attempts }}</span>
                </li>
                {% endfor %}
            </ul>
        </div>
    </div>


    <div class="trend-container">
        <h2>{{ t.hour_trend }}</h2>
        <div class="trend-chart">
            <div id="trend-tooltip" class="tooltip"></div>
            <div class="chart-wrapper">
                {% set max_count = namespace(value=0) %}
                {% for item in stats.hourly_trend %}
                    {% if item.count > max_count.value %}
                        {% set max_count.value = item.count %}
                    {% endif %}
                {% endfor %}
                
                {% set height_factor = 180 %}
                {% for item in stats.hourly_trend %}
                    {% set height = 0 %}
                    {% if max_count.value > 0 %}
                        {% set height = (item.count / max_count.value * height_factor)|round|int %}
                    {% endif %}
                    <div class="bar-wrapper">
                        <div class="bar" 
                             style="height: {{ height }}px;"
                             data-hour="{{ item.hour }}"
                             data-count="{{ item.count }}">
                        </div>
                        <div class="hour-label">{{ item.hour }}</div>
                    </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        // Get current time range
        function getCurrentTimeRange() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('time_range') || 'all';
        }

        // Get current language
        function getCurrentLanguage() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('lang') || 'en';  // Default to English
        }

        // Get button text based on current state
        function getTimeRangeButtonText(currentTimeRange, lang) {
            if (currentTimeRange === 'all') {
                return lang === 'zh' ? '24小时' : '24h';
            }
            return lang === 'zh' ? '全部' : 'All';
        }

        function getLanguageButtonText(currentLang) {
            return currentLang === 'en' ? '中文' : 'English';
        }

        // Toggle time range
        function toggleTimeRange() {
            const currentTimeRange = getCurrentTimeRange();
            const newTimeRange = currentTimeRange === 'all' ? '24h' : 'all';
            const lang = getCurrentLanguage();
            window.location.href = `/?lang=${lang}&time_range=${newTimeRange}`;
        }

        // Toggle language
        function toggleLanguage() {
            const currentLang = getCurrentLanguage();
            const newLang = currentLang === 'en' ? 'zh' : 'en';
            const timeRange = getCurrentTimeRange();
            window.location.href = `/?lang=${newLang}&time_range=${timeRange}`;
        }

        // Show loading indicator
        function showLoading() {
            document.getElementById('loading-indicator').style.display = 'block';
        }

        // Hide loading indicator
        function hideLoading() {
            document.getElementById('loading-indicator').style.display = 'none';
        }

        // Normalize coordinates for map
        function normalizeCoordinates(lon, lat) {
            const mapWidth = 360;
            const mapHeight = 180;
            const x = ((parseFloat(lon) * 1.2 + 180) / 360) * mapWidth;
            const y = ((90 - parseFloat(lat)) / 180) * mapHeight;
            return { x, y };
        }

        // Refresh all data
        function refreshData() {
            const timeRange = getCurrentTimeRange();
            const lang = getCurrentLanguage();
            window.location.href = `/?lang=${lang}&time_range=${timeRange}`;
        }

        // Update map data
        function updateMap() {
            showLoading();
            const tooltip = document.getElementById('tooltip');
            const svg = document.getElementById('world-map');
            const timeRange = getCurrentTimeRange();
            const lang = getCurrentLanguage();
            
            fetch(`/api/map_data?time_range=${timeRange}`)
                .then(response => response.json())
                .then(data => {
                    // Clear existing points
                    document.querySelectorAll('.attack-point').forEach(el => el.remove());
                    
                    // Add new points
                    data.forEach(point => {
                        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                        const coords = normalizeCoordinates(point.lon, point.lat);
                        
                        circle.setAttribute('cx', coords.x);
                        circle.setAttribute('cy', coords.y);
                        
                        const radius = Math.log(point.count + 1) * 1.5;
                        circle.setAttribute('r', radius);
                        circle.setAttribute('class', 'attack-point');
                        
                        circle.addEventListener('mousemove', (e) => {
                            const translations = {
                                'zh': {
                                    'attack_times': '次攻击',
                                    'country_region': '国家/地区',
                                    'province_state': '省/州'
                                },
                                'en': {
                                    'attack_times': 'attacks',
                                    'country_region': 'Country/Region',
                                    'province_state': 'Province/State'
                                }
                            };
                            
                            const t = translations[lang];
                            
                            tooltip.style.display = 'block';
                            
                            let tooltipText = `${point.city}: ${point.count} ${t.attack_times}`;
                            if (point.country) {
                                tooltipText += `\n${t.country_region}: ${point.country}`;
                            }
                            if (point.admin_area) {
                                tooltipText += `\n${t.province_state}: ${point.admin_area}`;
                            }
                            tooltip.textContent = tooltipText;
                            
                            // Position tooltip
                            let tooltipX = e.pageX + 10;
                            let tooltipY = e.pageY - 10;
                            
                            if (tooltipX + tooltip.offsetWidth > window.innerWidth) {
                                tooltipX = e.pageX - tooltip.offsetWidth - 10;
                            }
                            
                            tooltip.style.left = tooltipX + 'px';
                            tooltip.style.top = tooltipY + 'px';
                        });
                        
                        circle.addEventListener('mouseout', () => {
                            tooltip.style.display = 'none';
                        });
                        
                        svg.appendChild(circle);
                    });
                    hideLoading();
                })
                .catch(error => {
                    console.error('Error updating map:', error);
                    hideLoading();
                });
        }

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            const timeRange = getCurrentTimeRange();
            const lang = getCurrentLanguage();
            
            // Update button texts
            const timeRangeButton = document.getElementById('timeRangeToggle');
            const languageButton = document.querySelector('.button-group button:last-child');
            
            // Set initial button texts to show target states
            timeRangeButton.textContent = getTimeRangeButtonText(timeRange, lang);
            languageButton.textContent = getLanguageButtonText(lang);
            
            // Initialize trend chart tooltips
            const trendTooltip = document.getElementById('trend-tooltip');
            const bars = document.querySelectorAll('.bar');
            
            bars.forEach(bar => {
                bar.addEventListener('mousemove', (e) => {
                    const hour = bar.getAttribute('data-hour');
                    const count = bar.getAttribute('data-count');
                    const attemptText = lang === 'zh' ? '次尝试' : 'attempts';
                    
                    trendTooltip.textContent = `${hour}: ${count} ${attemptText}`;
                    trendTooltip.style.display = 'block';
                    
                    const rect = bar.getBoundingClientRect();
                    const tooltipX = rect.left + (rect.width / 2);
                    const tooltipY = rect.top - 10;
                    
                    trendTooltip.style.left = tooltipX + 'px';
                    trendTooltip.style.top = tooltipY + 'px';
                });
                
                bar.addEventListener('mouseout', () => {
                    trendTooltip.style.display = 'none';
                });
            });

            // Initial map update
            updateMap();
        });

        // Update map periodically
        setInterval(updateMap, 30000);
        
        // Handle window resize
        window.addEventListener('resize', updateMap);
    </script>

    <div style="text-align: center; margin-top: 20px; color: #666; display: flex; justify-content: center; align-items: center; gap: 20px;">
        <span>{{ t.last_update }}: {{ current_time }}</span>
        <a href="https://github.com/Yorkian/knock" target="_blank" style="color: #666; text-decoration: none; font-size: 24px;">
            <i class="bi bi-github"></i>
        </a>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Homepage route with language support"""
    time_range = request.args.get('time_range', 'all')
    lang = request.args.get('lang', 'en')
    if lang not in TRANSLATIONS:
        lang = 'en'
    
    stats = get_stats(time_range)
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        current_time=current_time,
        t=TRANSLATIONS[lang],
        lang=lang,
        time_range=time_range
    )


def init_app():
    """Initialize application"""
    os.makedirs('static', exist_ok=True)
    
    if not os.path.exists('static/defaultMap.jpg'):
        print("Warning: Map file not found at static/defaultMap.jpg")
        
    GeoData()

def main():
    """Main program entry"""
    # Initialize SSH monitor
    ssh_monitor = SSHMonitor(port=22)
    
    # Start SSH monitor thread
    monitor_thread = threading.Thread(target=ssh_monitor.start)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Initialize Flask application
    init_app()
    
    # Start web server
    try:
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nShutting down service...")
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == '__main__':
    main()
