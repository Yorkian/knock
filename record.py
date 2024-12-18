import socket
import threading
import datetime
import json
from pathlib import Path
import paramiko
import requests
import time
from typing import Optional, Dict, Any

class SSHMonitor(paramiko.ServerInterface):
    def __init__(self, host='0.0.0.0', port=22):
        self.host = host
        self.port = port
        self.ssh_log_file = Path('ssh_attempts.json')
        self.city_data_file = Path('city_data.json')
        self.geo_data_file = Path('geo_data.json')
        
        # 初始化或加载数据文件
        self.attempts = self._load_json(self.ssh_log_file, [])
        self.city_data = self._load_json(self.city_data_file, {})
        self.geo_data = self._load_json(self.geo_data_file, {})
        
        # 生成服务器密钥
        self.key = paramiko.RSAKey.generate(2048)

    def _load_json(self, file_path: Path, default: Any) -> Any:
        """加载JSON文件，如果文件不存在则返回默认值"""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default

    def _save_json(self, file_path: Path, data: Any) -> None:
        """保存数据到JSON文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_location_data(self, ip: str) -> Optional[Dict]:
        """获取IP地址的地理位置信息"""
        # 首先检查是否已有城市信息
        if ip in self.city_data:
            city = self.city_data[ip]
            return {"city": city}

        # 如果没有，则从API获取
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon"
            response = requests.get(url)
            data = response.json()
            
            if data["status"] != "success":
                return None

            # 更新city_data.json
            self.city_data[ip] = data["city"]
            self._save_json(self.city_data_file, self.city_data)

            # 如果geo_data中没有这个城市的信息，则添加
            if data["city"] not in self.geo_data:
                self.geo_data[data["city"]] = {
                    "lat": data["lat"],
                    "lon": data["lon"],
                    "country": data["country"],
                    "admin_area": data["regionName"],
                    "last_updated": datetime.datetime.now().isoformat()
                }
                self._save_json(self.geo_data_file, self.geo_data)

            return {
                "city": data["city"]
            }

        except Exception as e:
            print(f"Error getting location data for IP {ip}: {e}")
            return None

    def check_auth_password(self, username: str, password: str) -> int:
        """记录认证尝试并拒绝"""
        # 添加4秒延时
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
        self._save_json(self.ssh_log_file, self.attempts)
        
        print(f"记录登录尝试 - IP: {self.client_ip}, 城市: {location_data['city']}")
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        """允许密码认证"""
        return 'password'

    def _handle_connection(self, client_socket: socket.socket, address: tuple) -> None:
        """处理单个连接"""
        try:
            self.client_ip = address[0]
            self.client_port = address[1]
            
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(self.key)
            transport.start_server(server=self)
            
            # 等待认证尝试
            channel = transport.accept(20)
            if channel is not None:
                channel.close()

        except Exception as e:
            print(f"处理连接时出错: {e}")
        finally:
            try:
                transport.close()
            except:
                pass
            client_socket.close()

    def start(self) -> None:
        """启动SSH监控服务器"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        
        print(f"开始监控SSH尝试，监听地址 {self.host}:{self.port}")
        
        try:
            while True:
                client, address = server.accept()
                thread = threading.Thread(
                    target=self._handle_connection,
                    args=(client, address)
                )
                thread.daemon = True
                thread.start()
                
                # 添加短暂延时以避免API请求限制
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n正在关闭监控...")
        finally:
            server.close()

if __name__ == '__main__':
    # 注意：在22端口运行需要root/管理员权限
    monitor = SSHMonitor(port=22)
    monitor.start()